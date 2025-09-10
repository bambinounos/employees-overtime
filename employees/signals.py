from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import ManualKpiEntry, Task, TaskList
from datetime import date
from dateutil.relativedelta import relativedelta

@receiver(post_save, sender=Task)
def handle_recurring_task(sender, instance, created, **kwargs):
    """
    Creates the next task in a recurring series when one is marked as complete.
    """
    if created or not instance.is_recurring or not instance.completed_at:
        return

    # Check if a child task has already been generated for this instance
    if instance.children.exists():
        return

    next_due_date = None
    if not instance.due_date:
        return

    if instance.recurrence_frequency == 'daily':
        next_due_date = instance.due_date + relativedelta(days=1)
    elif instance.recurrence_frequency == 'monthly':
        next_due_date = instance.due_date + relativedelta(months=1)
    elif instance.recurrence_frequency == 'yearly':
        next_due_date = instance.due_date + relativedelta(years=1)

    if not next_due_date or (instance.recurrence_end_date and next_due_date > instance.recurrence_end_date):
        return

    try:
        todo_list = TaskList.objects.get(board=instance.list.board, name__iexact="Pendiente")
    except TaskList.DoesNotExist:
        return

    Task.objects.create(
        parent_task=instance,
        list=todo_list,
        assigned_to=instance.assigned_to,
        created_by=instance.created_by,
        kpi=instance.kpi,
        title=instance.title,
        description=instance.description,
        order=instance.order,
        due_date=next_due_date,
        is_recurring=True,
        recurrence_frequency=instance.recurrence_frequency,
        recurrence_end_date=instance.recurrence_end_date
    )

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
