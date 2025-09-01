from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import ManualKpiEntry

@receiver(post_save, sender=ManualKpiEntry)
def send_warning_notification(sender, instance, created, **kwargs):
    """
    Send an email notification if a ManualKpiEntry for a warning KPI is created.
    """
    if created and instance.kpi.is_warning_kpi:
        employee = instance.employee
        subject = f"Notificación de Advertencia Disciplinaria - {employee.name}"
        message = f"""
        Hola {employee.name},

        Este es un aviso formal para informarle que se ha registrado una advertencia disciplinaria en su expediente el día {instance.date.strftime('%Y-%m-%d')}.

        Motivo/Notas:
        {instance.notes}

        Esta advertencia está relacionada con el indicador de rendimiento: "{instance.kpi.name}".
        Por favor, asegúrese de cumplir con el reglamento interno para evitar futuras incidencias.

        Atentamente,
        Recursos Humanos
        """
        from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com'
        recipient_list = [employee.email]

        send_mail(subject, message, from_email, recipient_list)
        print(f"Sent warning email to {employee.email}") # For logging in console
