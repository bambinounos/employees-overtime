"""
Sugerencias inteligentes para mejorar el bono del mes.

Construye recomendaciones accionables por KPI a partir de los datos reales
del empleado (tareas, errores manuales, productos creados). Las consultas
espejan las de Employee.calculate_performance_bonus para que lo que se
sugiere coincida exactamente con lo que se mide.

Se consume desde 'Mi panel' y desde el email semanal de coaching
(management command coaching_semanal).
"""
import calendar
from datetime import date
from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone

from .models import BonusRule, KPI, ManualKpiEntry, ProductCreationLog, Task


def _bonus_at_stake(kpi):
    """Mayor monto posible del KPI: BonusRule o el tier más alto."""
    amounts = [tier.bonus_amount for tier in kpi.tiers.all()]
    rule = BonusRule.objects.filter(kpi=kpi).first()
    if rule:
        amounts.append(rule.bonus_amount)
    return max(amounts) if amounts else Decimal('0')


def _business_days_left(year, month):
    """Días hábiles restantes del mes; None si el período no es el mes en curso."""
    today = timezone.localtime(timezone.now()).date()
    if (year, month) != (today.year, today.month):
        return None
    last = calendar.monthrange(year, month)[1]
    return sum(1 for d in range(today.day, last + 1)
               if date(year, month, d).weekday() < 5)


def _business_days_elapsed(year, month):
    """Días hábiles transcurridos del mes (mínimo 1), como en calculate_ipac."""
    today = timezone.localtime(timezone.now()).date()
    last_day = calendar.monthrange(year, month)[1]
    if (year, month) == (today.year, today.month):
        last_day = min(last_day, today.day)
    return max(1, sum(1 for d in range(1, last_day + 1)
                      if date(year, month, d).weekday() < 5))


def _money_phrase(monto):
    if monto <= 0:
        return ""
    d = monto.normalize()
    if d == d.to_integral_value():
        d = d.quantize(Decimal(1))
    return f" (bono de ${d:n})"


def _errores_txt(n):
    return f"{n} error" if n == 1 else f"{n} errores"


def build_sugerencias(employee, year, month):
    """Devuelve una lista de sugerencias ordenadas por urgencia:
    {'tipo': warning|action|lost|ok|info, 'titulo', 'detalle', 'monto'}.
    """
    if not employee.profile:
        return []

    sugerencias = []
    days_left = _business_days_left(year, month)
    left_phrase = f" Quedan {days_left} días hábiles." if days_left else ""

    for kpi in employee.profile.kpis.all():
        monto = _bonus_at_stake(kpi)
        titulo = kpi.name

        if kpi.internal_code == 'PRODUCT_CREATION':
            creados = ProductCreationLog.objects.filter(
                employee=employee,
                created_at__year=year,
                created_at__month=month,
                is_suspect_duplicate=False,
            ).count()
            meta = int(kpi.target_value)
            if creados >= meta:
                sugerencias.append({'tipo': 'ok', 'titulo': titulo,
                                    'detalle': f"Meta alcanzada con {creados} productos (meta {meta}){_money_phrase(monto)}.",
                                    'monto': monto})
            else:
                sugerencias.append({'tipo': 'action', 'titulo': titulo,
                                    'detalle': f"Te faltan {meta - creados} productos para la meta de {meta}.{_money_phrase(monto)}.{left_phrase}",
                                    'monto': monto})
            continue

        if kpi.measurement_type == 'percentage':
            tasks = Task.objects.filter(
                assigned_to=employee, kpi=kpi,
                due_date__year=year, due_date__month=month)
            total = tasks.count()
            completadas = tasks.filter(
                completed_at__isnull=False, list__name__iexact="Hecho").count()
            if total == 0:
                sugerencias.append({'tipo': 'info', 'titulo': titulo,
                                    'detalle': "Sin tareas asignadas con este KPI este mes.",
                                    'monto': monto})
            elif completadas < total:
                pct = int(completadas / total * 100)
                sugerencias.append({'tipo': 'action', 'titulo': titulo,
                                    'detalle': f"Te quedan {total - completadas} de {total} tareas por completar ({pct}% avanzado). Completarlas todas asegura el bono{_money_phrase(monto)}.{left_phrase}",
                                    'monto': monto})
            else:
                sugerencias.append({'tipo': 'ok', 'titulo': titulo,
                                    'detalle': f"Tus {total} tareas están completadas: bono asegurado{_money_phrase(monto)}.",
                                    'monto': monto})

        elif kpi.measurement_type == 'count_lt':
            errores = int(ManualKpiEntry.objects.filter(
                employee=employee, kpi=kpi,
                date__year=year, date__month=month)
                .aggregate(total=Sum('value'))['total'] or 0)
            permitidos = max(int(kpi.target_value) - 1, 0)
            if errores > permitidos:
                sugerencias.append({'tipo': 'lost', 'titulo': titulo,
                                    'detalle': f"Con {_errores_txt(errores)} el bono de este mes se perdió (se permiten menos de {kpi.target_value:n}){_money_phrase(monto)}.",
                                    'monto': monto})
            elif errores == permitidos:
                sugerencias.append({'tipo': 'warning', 'titulo': titulo,
                                    'detalle': f"Al límite: {_errores_txt(errores)} y el máximo es {permitidos}. Un error más pierde el bono{_money_phrase(monto)}.",
                                    'monto': monto})
            else:
                sugerencias.append({'tipo': 'ok', 'titulo': titulo,
                                    'detalle': f"Llevas {_errores_txt(errores)} de {permitidos} permitidos: bono asegurado por ahora{_money_phrase(monto)}.",
                                    'monto': monto})

        elif kpi.measurement_type == 'count_gt':
            hechas = Task.objects.filter(
                assigned_to=employee, kpi=kpi,
                completed_at__year=year, completed_at__month=month).count()
            meta = int(kpi.target_value)
            if hechas >= meta:
                sugerencias.append({'tipo': 'ok', 'titulo': titulo,
                                    'detalle': f"Meta alcanzada con {hechas} (meta {meta}){_money_phrase(monto)}.",
                                    'monto': monto})
            else:
                sugerencias.append({'tipo': 'action', 'titulo': titulo,
                                    'detalle': f"Te faltan {meta - hechas} para la meta de {meta}{_money_phrase(monto)}.{left_phrase}",
                                    'monto': monto})

        elif kpi.measurement_type == 'composite_ipac':
            completadas = Task.objects.filter(
                assigned_to=employee,
                completed_at__year=year, completed_at__month=month)
            n = completadas.count()
            if n == 0:
                continue
            con_fecha = completadas.exclude(due_date__isnull=True)
            nf = con_fecha.count()
            on_time = con_fecha.filter(completed_at__date__lte=F('due_date')).count() if nf else 0
            pct = int(on_time / nf * 100) if nf else 100
            bd = _business_days_elapsed(year, month)
            error_kpis = KPI.objects.filter(measurement_type='count_lt')
            num_errors = ManualKpiEntry.objects.filter(
                employee=employee, kpi__in=error_kpis,
                date__year=year, date__month=month,
            ).aggregate(total=Sum('value'))['total'] or 0
            quality = max(Decimal('0'), Decimal('1') - Decimal(num_errors) / Decimal(n))
            ipac_actual = employee.calculate_ipac(year, month)
            ipac_potencial = (Decimal(n) * quality / Decimal(bd)).quantize(Decimal('0.01'))
            if pct >= 80:
                sugerencias.append({'tipo': 'ok', 'titulo': titulo,
                                    'detalle': f"Puntualidad {pct}%: tu IPAC va en {ipac_actual:n} (tareas efectivas por día hábil).",
                                    'monto': monto})
            else:
                sugerencias.append({'tipo': 'action', 'titulo': titulo,
                                    'detalle': f"Completaste {pct}% de tus tareas a tiempo. Completándolas el día del vencimiento tu IPAC subiría de {ipac_actual:n} a ~{ipac_potencial:n}.",
                                    'monto': monto})

    prioridad = {'warning': 0, 'action': 1, 'lost': 2, 'ok': 3, 'info': 4}
    sugerencias.sort(key=lambda s: (prioridad.get(s['tipo'], 9), -s['monto']))
    return sugerencias
