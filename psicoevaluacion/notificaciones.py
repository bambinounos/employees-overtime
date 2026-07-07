"""Envío del link de evaluación al candidato por correo."""
import logging

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from employees.emails import send_html_mail

logger = logging.getLogger(__name__)


def enviar_link_evaluacion(evaluacion, request=None):
    """Envía el link de la evaluación al correo del candidato y estampa
    link_enviado_en. Returns (ok, mensaje)."""
    if not evaluacion.correo:
        return False, "El candidato no tiene correo registrado."
    if evaluacion.estado not in ('PENDIENTE', 'EN_CURSO'):
        return False, f"La evaluación está {evaluacion.get_estado_display().lower()}; no tiene sentido reenviar el link."
    if evaluacion.esta_expirada():
        return False, "El link ya expiró. Extiende la fecha de expiración antes de reenviar."

    path = reverse('psicoevaluacion:inicio_evaluacion', args=[evaluacion.token])
    if request is not None:
        link = request.build_absolute_uri(path)
    else:
        base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
        link = f"{base}{path}"

    ok = send_html_mail(
        subject="Evaluación psicológica — proceso de selección",
        template_name='link_evaluacion.html',
        context={'evaluacion': evaluacion, 'link': link},
        to=evaluacion.correo,
    )
    if not ok:
        return False, "No se pudo enviar el correo (ver logs)."

    evaluacion.link_enviado_en = timezone.now()
    evaluacion.save(update_fields=['link_enviado_en'])
    return True, f"Link enviado a {evaluacion.correo}."
