"""
Cierre de mes: generación de recibos de nómina (snapshots inmutables).

El recibo congela el desglose de calculate_salary en JSON. El PDF y la
planilla de meses cerrados se construyen SIEMPRE desde ese JSON, nunca
recalculando, para que el histórico no cambie al cambiar reglas.
"""
import logging
from datetime import date
from decimal import Decimal

import httpx
from django.db.models import Q
from django.utils import timezone

from .dolibarr_api import DolibarrApiError, crear_salario
from .models import DolibarrInstance, Employee, ReciboNomina

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


def enviar_recibos_dolibarr(year, month):
    """Envía a Dolibarr los recibos del período como salarios (paye=0).

    Idempotente: omite recibos ya sincronizados (con dolibarr_salary_id).
    Nunca aborta el lote: cada fallo queda en recibo.dolibarr_error y sigue.
    Devuelve un dict con cuatro listas:
        {'enviados': [recibos], 'ya_sincronizados': [recibos],
         'sin_mapeo': [employees], 'con_error': [(recibo, mensaje)]}
    """
    instancias_push = DolibarrInstance.objects.exclude(
        api_base_url='').exclude(api_key='')
    recibos = ReciboNomina.objects.filter(
        year=year, month=month).select_related('employee').order_by('employee__name')

    enviados, ya_sincronizados, sin_mapeo, con_error = [], [], [], []

    def _marcar_error(recibo, mensaje):
        recibo.dolibarr_error = mensaje[:2000]
        recibo.save(update_fields=['dolibarr_error'])
        con_error.append((recibo, mensaje))

    for recibo in recibos:
        if recibo.dolibarr_salary_id is not None:
            ya_sincronizados.append(recibo)
            continue

        identidades = list(recibo.employee.dolibarr_identities.filter(
            dolibarr_instance__in=instancias_push).select_related('dolibarr_instance'))

        if not identidades:
            sin_mapeo.append(recibo.employee)
            continue
        if len(identidades) > 1:
            _marcar_error(recibo,
                          "Empleado mapeado en varias instancias Dolibarr con push "
                          "habilitado; deja solo una con api_key o elimina mapeos duplicados.")
            continue

        identidad = identidades[0]
        try:
            salary_id = crear_salario(
                recibo, identidad.dolibarr_instance, identidad.dolibarr_user_id)
        except (DolibarrApiError, httpx.HTTPError) as exc:
            logger.warning("Error enviando recibo #%s a Dolibarr: %s", recibo.pk, exc)
            _marcar_error(recibo, str(exc))
            continue

        recibo.dolibarr_salary_id = salary_id
        recibo.dolibarr_synced_at = timezone.now()
        recibo.dolibarr_error = ''
        recibo.save(update_fields=['dolibarr_salary_id', 'dolibarr_synced_at', 'dolibarr_error'])
        enviados.append(recibo)

    logger.info("Push Dolibarr %s-%02d: %d enviados, %d ya sync, %d sin mapeo, %d errores",
                year, month, len(enviados), len(ya_sincronizados), len(sin_mapeo), len(con_error))
    return {
        'enviados': enviados,
        'ya_sincronizados': ya_sincronizados,
        'sin_mapeo': sin_mapeo,
        'con_error': con_error,
    }
