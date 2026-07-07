"""
Cierre de mes: generación de recibos de nómina (snapshots inmutables).

El recibo congela el desglose de calculate_salary en JSON. El PDF y la
planilla de meses cerrados se construyen SIEMPRE desde ese JSON, nunca
recalculando, para que el histórico no cambie al cambiar reglas.
"""
import logging
from datetime import date
from decimal import Decimal

from django.db.models import Q

from .models import Employee, ReciboNomina

logger = logging.getLogger(__name__)


def _jsonable(value):
    """Convierte el dict de calculate_salary a algo serializable en JSON.
    Los Decimal se guardan como str para no perder precisión."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def generar_recibo(employee, year, month, generado_por=None):
    """Genera (o regenera) el recibo de un empleado. Devuelve el recibo o
    None si el empleado no tiene salario configurado para ese mes."""
    salary = employee.calculate_salary(year, month)
    if salary is None:
        return None
    recibo, _created = ReciboNomina.objects.update_or_create(
        employee=employee, year=year, month=month,
        defaults={
            'datos': _jsonable(salary),
            'total': salary['total_salary'],
            'generado_por': generado_por,
        }
    )
    return recibo


def generar_recibos_mes(year, month, generado_por=None):
    """Genera recibos para todos los empleados activos en el mes objetivo.
    Devuelve (generados, omitidos): omitidos = sin salario configurado."""
    ultimo_dia = date(year, month, 1)
    activos = Employee.objects.filter(
        Q(end_date__isnull=True) | Q(end_date__gte=ultimo_dia)
    ).order_by('name')

    generados, omitidos = [], []
    for employee in activos:
        recibo = generar_recibo(employee, year, month, generado_por=generado_por)
        if recibo is None:
            omitidos.append(employee)
            logger.warning("Recibo omitido para %s (%s-%02d): sin salario configurado",
                           employee.name, year, month)
        else:
            generados.append(recibo)
    logger.info("Cierre %s-%02d: %d recibos generados, %d omitidos",
                year, month, len(generados), len(omitidos))
    return generados, omitidos
