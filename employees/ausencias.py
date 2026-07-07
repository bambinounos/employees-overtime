"""
Servicio de aprobación/rechazo de solicitudes de ausencia.

La nómina paga por WorkLogs (Employee.calculate_salary), así que aprobar una
ausencia remunerada materializa un WorkLog de 8 horas por día hábil. Revertir
una aprobación elimina solo los WorkLogs creados por esa solicitud (FK
`ausencia`), nunca registros cargados a mano.

Se usa un servicio explícito (no signals) para mantener el control
transaccional: o se aprueba con todos sus efectos o no se aprueba.
"""
import logging
from datetime import timedelta, datetime, time

from django.db import transaction
from django.utils import timezone

from .emails import send_html_mail
from .models import WorkLog

logger = logging.getLogger(__name__)


def _notificar_decision(solicitud):
    """Email al empleado con la decisión, tras el commit (send_html_mail nunca
    lanza: SMTP caído no bloquea la aprobación)."""
    destinatario = solicitud.employee.email
    if not destinatario:
        return
    saldo = solicitud.employee.saldo_vacaciones(solicitud.fecha_inicio.year)
    transaction.on_commit(lambda: send_html_mail(
        subject=f"Tu solicitud de {solicitud.tipo.nombre} fue {solicitud.get_estado_display().lower()}",
        template_name='ausencia_decidida.html',
        context={'solicitud': solicitud, 'saldo': saldo},
        to=destinatario,
    ))


def _dias_habiles_de(solicitud):
    dia = solicitud.fecha_inicio
    while dia <= solicitud.fecha_fin:
        if dia.weekday() < 5:
            yield dia
        dia += timedelta(days=1)


def _sync_evento_calendario(solicitud):
    """Crea/actualiza el evento CalDAV de la ausencia aprobada (mismo patrón
    que sync_task_to_calendar en signals.py). Sin usuario Django no hay
    calendario que alimentar."""
    from caldav.models import CalendarEvent

    user = getattr(solicitud.employee, 'user', None)
    if not user:
        return
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(solicitud.fecha_inicio, time(9, 0)), tz)
    end = timezone.make_aware(datetime.combine(solicitud.fecha_fin, time(18, 0)), tz)
    CalendarEvent.objects.update_or_create(
        uid=f"ausencia-{solicitud.pk}@payroll",
        defaults={
            'user': user,
            'title': f"{solicitud.tipo.nombre} — {solicitud.employee.name}",
            'start_date': start,
            'end_date': end,
            'description': solicitud.motivo or '',
            'is_personal': False,
        }
    )


def _borrar_evento_calendario(solicitud):
    from caldav.models import CalendarEvent
    CalendarEvent.objects.filter(uid=f"ausencia-{solicitud.pk}@payroll").delete()


@transaction.atomic
def aprobar_solicitud(solicitud, aprobador, comentario=''):
    """Aprueba una solicitud PENDIENTE: crea los WorkLogs remunerados (sin
    pisar días ya registrados) y el evento de calendario."""
    if solicitud.estado != 'PENDIENTE':
        raise ValueError(f"Solo se pueden aprobar solicitudes pendientes (estado actual: {solicitud.estado}).")

    solicitud.estado = 'APROBADA'
    solicitud.decidida_por = aprobador
    solicitud.comentario_decision = comentario
    solicitud.decidida_en = timezone.now()
    solicitud.save()

    if solicitud.tipo.es_remunerada:
        for dia in _dias_habiles_de(solicitud):
            # unique_together (employee, date): un día ya cargado a mano gana
            WorkLog.objects.get_or_create(
                employee=solicitud.employee,
                date=dia,
                defaults={'hours_worked': 8, 'overtime_hours': 0, 'ausencia': solicitud},
            )

    _sync_evento_calendario(solicitud)
    _notificar_decision(solicitud)
    logger.info("Ausencia #%s aprobada por %s (%s días hábiles)",
                solicitud.pk, aprobador, solicitud.dias_habiles)
    return solicitud


@transaction.atomic
def rechazar_solicitud(solicitud, aprobador, comentario=''):
    """Rechaza una solicitud PENDIENTE."""
    if solicitud.estado != 'PENDIENTE':
        raise ValueError(f"Solo se pueden rechazar solicitudes pendientes (estado actual: {solicitud.estado}).")
    solicitud.estado = 'RECHAZADA'
    solicitud.decidida_por = aprobador
    solicitud.comentario_decision = comentario
    solicitud.decidida_en = timezone.now()
    solicitud.save()
    _notificar_decision(solicitud)
    logger.info("Ausencia #%s rechazada por %s", solicitud.pk, aprobador)
    return solicitud


@transaction.atomic
def cancelar_solicitud(solicitud, actor, comentario=''):
    """Cancela una solicitud PENDIENTE (el empleado) o revierte una APROBADA
    (solo superuser): elimina los WorkLogs generados y el evento."""
    if solicitud.estado not in ('PENDIENTE', 'APROBADA'):
        raise ValueError(f"No se puede cancelar una solicitud en estado {solicitud.estado}.")

    if solicitud.estado == 'APROBADA':
        WorkLog.objects.filter(ausencia=solicitud).delete()
        _borrar_evento_calendario(solicitud)

    solicitud.estado = 'CANCELADA'
    solicitud.decidida_por = actor if actor.is_authenticated else None
    if comentario:
        solicitud.comentario_decision = comentario
    solicitud.decidida_en = timezone.now()
    solicitud.save()
    logger.info("Ausencia #%s cancelada por %s", solicitud.pk, actor)
    return solicitud
