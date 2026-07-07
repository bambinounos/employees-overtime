"""
Generador del recibo de nómina en PDF.

Renderiza SIEMPRE desde ReciboNomina.datos (snapshot JSON del cierre de mes),
nunca recalculando, para que un recibo histórico no cambie aunque cambien las
reglas de bonos o comisiones.
"""
import io
from decimal import Decimal, InvalidOperation

from django.contrib.staticfiles import finders

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    Image,
)

MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
         'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

AZUL = colors.HexColor('#1e3a5f')
GRIS = colors.HexColor('#555555')
ROJO_HELLBAM = colors.HexColor('#8b1a1a')

EMPRESA_NOMBRE = 'IMPORTADORA HELLBAM S.A.'
EMPRESA_RUC = 'RUC: 2290350487001'
EMPRESA_LINKS = [
    ('www.hellbam.com', 'https://www.hellbam.com'),
    ('www.hellbam.store', 'https://www.hellbam.store'),
    ('kama.hellbam.store', 'https://kama.hellbam.store'),
]


def _bloque_empresa(styles):
    """Logo + datos de la empresa con links clicables. Si el logo no está
    disponible (p.ej. static sin desplegar), degrada a solo texto."""
    links = ' &nbsp;·&nbsp; '.join(
        f'<a href="{url}" color="#2563eb"><u>{texto}</u></a>'
        for texto, url in EMPRESA_LINKS)
    info = Paragraph(
        f'<font size="13"><b>{EMPRESA_NOMBRE}</b></font><br/>'
        f'<font size="9" color="#555555">{EMPRESA_RUC}</font><br/>'
        f'<font size="9">{links}</font>',
        styles['Normal'])

    logo_path = finders.find('employees/img/logo_hellbam.png')
    if not logo_path:
        return info

    # 834x299 px -> mantener proporción (~2.79) a 1.9" de ancho
    logo = Image(logo_path, width=1.9 * inch, height=1.9 * inch * 299 / 834)
    tabla = Table([[logo, info]], colWidths=[2.1 * inch, 4.7 * inch])
    tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ]))
    return tabla


def _dec(datos, clave):
    """Lee un valor del snapshot como Decimal ('--' tolerante a ausencias)."""
    valor = datos.get(clave)
    if valor is None:
        return Decimal('0')
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _money(valor):
    return f"$ {valor:,.2f}"


def generar_recibo_pdf(recibo):
    """Genera el PDF de un ReciboNomina. Returns: bytes."""
    datos = recibo.datos
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('SubInfo', parent=styles['Normal'], fontSize=9, textColor=GRIS))
    styles.add(ParagraphStyle('SectionTitle', parent=styles['Heading2'], fontSize=12,
                              spaceAfter=6, spaceBefore=14, textColor=AZUL))

    elements = []

    # ── Encabezado corporativo ──
    elements.append(_bloque_empresa(styles))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width='100%', thickness=2, color=ROJO_HELLBAM))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph('RECIBO DE NÓMINA', styles['Title']))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width='100%', thickness=1, color=AZUL))
    elements.append(Spacer(1, 12))

    periodo = f"{MESES[recibo.month]} {recibo.year}"
    info = [
        ['Empleado:', recibo.employee.name, 'Período:', periodo],
        ['Correo:', recibo.employee.email, 'Emitido:',
         recibo.generado_en.strftime('%Y-%m-%d %H:%M')],
    ]
    tabla_info = Table(info, colWidths=[1.1 * inch, 2.9 * inch, 0.9 * inch, 1.9 * inch])
    tabla_info.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(tabla_info)

    # ── Desglose ──
    elements.append(Paragraph('Desglose', styles['SectionTitle']))

    horas = datos.get('total_hours_worked', '0')
    extras = datos.get('total_overtime_hours', '0')
    filas = [
        ['Concepto', 'Detalle', 'Monto'],
        ['Sueldo base del período', '', _money(_dec(datos, 'base_salary'))],
        ['Pago por horas trabajadas', f"{horas} h", _money(_dec(datos, 'work_pay'))],
        ['Horas extra (1.5x)', f"{extras} h", _money(_dec(datos, 'overtime_pay'))],
        ['Bono por desempeño (KPIs)', '', _money(_dec(datos, 'performance_bonus'))],
    ]

    pct = _dec(datos, 'commission_percentage')
    if pct > 0:
        filas.append(['Comisiones confirmadas',
                      f"{pct}% sobre {_money(_dec(datos, 'net_confirmed'))} neto",
                      _money(_dec(datos, 'commission_amount'))])
        notas_credito = _dec(datos, 'credit_notes_amount')
        if notas_credito > 0:
            filas.append(['   Notas de crédito descontadas',
                          f"{datos.get('credit_note_count', 0)} nota(s)",
                          f"- {_money(notas_credito)}"])
        arrastre = _dec(datos, 'carry_forward_applied')
        if arrastre != 0:
            filas.append(['   Saldo arrastrado de meses previos', '', _money(arrastre)])

    filas.append(['TOTAL A PAGAR', '', _money(recibo.total)])

    tabla = Table(filas, colWidths=[3.3 * inch, 2.2 * inch, 1.3 * inch])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), AZUL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#eef2f7')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(tabla)

    # ── Comisiones provisionales (informativas) ──
    provisional = _dec(datos, 'provisional_invoiced')
    if provisional > 0:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            f"Informativo: {_money(provisional)} en facturas emitidas aún no cobradas "
            f"({datos.get('provisional_count', 0)} factura(s)). Se comisionan al confirmarse el pago.",
            styles['SubInfo']))

    deuda = _dec(datos, 'remaining_debt')
    if deuda < 0:
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            f"Saldo pendiente por notas de crédito que se descontará de comisiones futuras: {_money(abs(deuda))}.",
            styles['SubInfo']))

    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=GRIS))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Documento generado automáticamente por el sistema de gestión de salarios. '
        'Las cifras corresponden al cierre del período indicado.', styles['SubInfo']))

    doc.build(elements)
    return buf.getvalue()
