"""
Envío de emails HTML con fallback a texto plano.

Todos los envíos de notificaciones pasan por send_html_mail: loguea el fallo
y devuelve False en vez de romper el flujo de negocio (una aprobación de
vacaciones no puede fallar porque el SMTP esté caído).
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_html_mail(subject, template_name, context, to):
    """Renderiza employees/templates/emails/<template_name> y envía.

    Returns True si se envió, False si falló (ya logueado)."""
    if not to:
        return False
    if isinstance(to, str):
        to = [to]

    try:
        html = render_to_string(f"emails/{template_name}", context)
        text = strip_tags(html)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        msg = EmailMultiAlternatives(subject, text, from_email, to)
        msg.attach_alternative(html, 'text/html')
        msg.send()
        logger.info("Email '%s' enviado a %s", subject, ', '.join(to))
        return True
    except Exception:
        logger.exception("Fallo enviando email '%s' a %s", subject, ', '.join(to))
        return False
