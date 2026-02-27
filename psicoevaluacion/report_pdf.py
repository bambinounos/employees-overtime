"""
Generador de informe PDF de evaluación psicológica.
Usa reportlab para generar el documento.
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)


def _fmt(value, decimals=1, suffix=''):
    """Format a numeric value, returning '--' if None."""
    if value is None:
        return '--'
    if isinstance(value, float):
        return f'{value:.{decimals}f}{suffix}'
    return f'{value}{suffix}'


def _color_veredicto(veredicto):
    if veredicto == 'APTO':
        return colors.HexColor('#16a34a')
    elif veredicto == 'NO_APTO':
        return colors.HexColor('#dc2626')
    return colors.HexColor('#d97706')


def generar_informe_pdf(evaluacion, resultado):
    """
    Genera un PDF con el informe completo de la evaluación.
    Returns: bytes del PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        'SectionTitle', parent=styles['Heading2'],
        fontSize=13, spaceAfter=8, spaceBefore=16,
        textColor=colors.HexColor('#1e3a5f'),
    ))
    styles.add(ParagraphStyle(
        'SubInfo', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#555555'),
    ))
    styles.add(ParagraphStyle(
        'CellText', parent=styles['Normal'],
        fontSize=9, leading=12,
    ))
    styles.add(ParagraphStyle(
        'Veredicto', parent=styles['Heading1'],
        fontSize=18, alignment=1, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        'InterpText', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#444444'),
        leading=10, spaceBefore=2,
    ))

    elements = []

    # ── Header ──
    elements.append(Paragraph('INFORME DE EVALUACION PSICOLOGICA', styles['Title']))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1e3a5f')))
    elements.append(Spacer(1, 12))

    # ── Candidate data ──
    elements.append(Paragraph('Datos del Candidato', styles['SectionTitle']))

    perfil_nombre = evaluacion.perfil_objetivo.nombre if evaluacion.perfil_objetivo else 'Sin perfil'
    metodo = ''
    if evaluacion.perfil_objetivo:
        metodo = evaluacion.perfil_objetivo.get_metodo_veredicto_display()

    info_data = [
        ['Nombres:', evaluacion.nombres, 'Cedula:', evaluacion.cedula],
        ['Correo:', evaluacion.correo, 'Telefono:', evaluacion.telefono or '-'],
        ['Cargo postulado:', evaluacion.cargo_postulado or '-', 'Estado:', evaluacion.get_estado_display()],
        ['Perfil objetivo:', perfil_nombre, 'Metodo veredicto:', metodo or '-'],
        ['Fecha inicio:', _fmt_date(evaluacion.fecha_inicio), 'Fecha fin:', _fmt_date(evaluacion.fecha_finalizacion)],
    ]

    info_table = Table(info_data, colWidths=[1.3 * inch, 2.2 * inch, 1.3 * inch, 2.2 * inch])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#555')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8))

    if not resultado:
        elements.append(Paragraph(
            'No hay resultados calculados para esta evaluacion.',
            styles['Normal']
        ))
        doc.build(elements)
        return buf.getvalue()

    # ── Veredicto ──
    veredicto = resultado.veredicto_final or resultado.veredicto_automatico
    veredicto_color = _color_veredicto(veredicto)
    veredicto_display = veredicto.replace('_', ' ')

    elements.append(Spacer(1, 8))
    vdata = [[Paragraph(
        f'<font color="{veredicto_color.hexval()}">{veredicto_display}</font>',
        styles['Veredicto']
    )]]
    vtable = Table(vdata, colWidths=[7 * inch])
    vtable.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, veredicto_color),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(vtable)
    elements.append(Spacer(1, 12))

    # ── Big Five ──
    elements.append(Paragraph('Big Five (OCEAN)', styles['SectionTitle']))
    bf_data = [
        ['Dimension', 'Puntaje', 'Escala'],
        ['Responsabilidad', _fmt(resultado.puntaje_responsabilidad), '1-5'],
        ['Amabilidad', _fmt(resultado.puntaje_amabilidad), '1-5'],
        ['Neuroticismo', _fmt(resultado.puntaje_neuroticismo), '1-5'],
        ['Apertura', _fmt(resultado.puntaje_apertura), '1-5'],
        ['Extroversion', _fmt(resultado.puntaje_extroversion), '1-5'],
    ]
    elements.append(_make_table(bf_data))

    # ── Compromiso ──
    elements.append(Paragraph('Compromiso Organizacional (Allen & Meyer)', styles['SectionTitle']))
    co_data = [
        ['Subdimension', 'Puntaje', 'Escala'],
        ['Afectivo', _fmt(resultado.puntaje_compromiso_afectivo), '1-5'],
        ['Continuidad', _fmt(resultado.puntaje_compromiso_continuidad), '1-5'],
        ['Normativo', _fmt(resultado.puntaje_compromiso_normativo), '1-5'],
        ['Total', _fmt(resultado.puntaje_compromiso_total), '1-5'],
    ]
    elements.append(_make_table(co_data))

    # ── Otras pruebas ──
    elements.append(Paragraph('Pruebas Complementarias', styles['SectionTitle']))
    other_data = [
        ['Prueba', 'Puntaje', 'Detalle'],
        ['Obediencia', _fmt(resultado.puntaje_obediencia), 'Escala 1-5'],
        ['Memoria', _fmt(resultado.puntaje_memoria, 0, '%'),
         f'Max span: {_fmt(resultado.max_secuencia_memoria, 0)}'],
        ['Matrices (IQ)', _fmt(resultado.puntaje_matrices, 0, '%'), 'Ponderado por dificultad'],
        ['Situacional', _fmt(resultado.puntaje_situacional, 0, '%'), 'Normalizado 0-100'],
    ]
    elements.append(_make_table(other_data))

    # ── Proyectivas ──
    elements.append(Paragraph('Pruebas Proyectivas', styles['SectionTitle']))
    proy_data = [
        ['Prueba', 'Puntaje', 'Escala'],
        ['Test del Arbol', _fmt(resultado.puntaje_arbol, 0), '1-10'],
        ['Persona bajo la Lluvia', _fmt(resultado.puntaje_persona_lluvia, 0), '1-10'],
        ['Frases Incompletas', _fmt(resultado.puntaje_frases, 0), '1-10'],
        ['Test de Colores', _fmt_colores(resultado.puntaje_colores), '1-10'],
    ]
    elements.append(_make_table(proy_data))

    # Interpretations from observaciones
    if resultado.observaciones:
        elements.append(Spacer(1, 4))
        elements.append(Paragraph('Interpretaciones:', styles['SubInfo']))
        for line in resultado.observaciones.split('\n'):
            line = line.strip()
            if line and line != '---':
                clean = line.replace('**', '')
                elements.append(Paragraph(clean, styles['InterpText']))

    # ── Indices combinados ──
    elements.append(Paragraph('Indices Combinados', styles['SectionTitle']))
    idx_data = [
        ['Indice', 'Valor', 'Descripcion'],
        ['Responsabilidad Total', _fmt(resultado.indice_responsabilidad_total),
         'Big Five 50% + Situacional 30% + Memoria 20%'],
        ['Lealtad', _fmt(resultado.indice_lealtad),
         'Compromiso 60% + Responsabilidad 20% + Obediencia 20%'],
        ['Obediencia Total', _fmt(resultado.indice_obediencia_total),
         'Obediencia 60% + Situacional 40%'],
    ]
    elements.append(_make_table(idx_data, col_widths=[1.5 * inch, 1 * inch, 4.5 * inch]))

    # ── Confiabilidad ──
    elements.append(Paragraph('Confiabilidad de la Evaluacion', styles['SectionTitle']))
    conf_data = [
        ['Indicador', 'Valor', 'Criterio'],
        ['Deseabilidad Social', _fmt(resultado.puntaje_deseabilidad_social),
         'Sospechoso si > 4.0'],
        ['Consistencia', _fmt(resultado.indice_consistencia, 0, '%'),
         'Baja si < 60%'],
        ['Evaluacion Confiable',
         'Si' if resultado.evaluacion_confiable else 'NO',
         ''],
    ]
    conf_table = _make_table(conf_data)
    elements.append(conf_table)

    if not resultado.evaluacion_confiable:
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            '<font color="#dc2626"><b>ATENCION:</b> Esta evaluacion presenta indicadores '
            'de baja confiabilidad. Los resultados deben interpretarse con precaucion.</font>',
            styles['SubInfo']
        ))

    # ── Footer ──
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#cccccc')))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        f'Informe generado el {datetime.now().strftime("%d/%m/%Y %H:%M")} | '
        f'Calculo: {resultado.fecha_calculo.strftime("%d/%m/%Y %H:%M") if resultado.fecha_calculo else "-"}',
        styles['SubInfo']
    ))

    doc.build(elements)
    return buf.getvalue()


def _fmt_date(dt):
    if dt is None:
        return '-'
    return dt.strftime('%d/%m/%Y %H:%M')


def _fmt_colores(value):
    if value is None:
        return '--'
    if isinstance(value, dict):
        return _fmt(value.get('puntuacion'), 0)
    return str(value)


def _make_table(data, col_widths=None):
    """Create a styled table from data rows (first row = header)."""
    if col_widths is None:
        col_widths = None  # auto

    table = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        # Body
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
        # Grid
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#1e3a5f')),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
    ]
    table.setStyle(TableStyle(style))
    return table
