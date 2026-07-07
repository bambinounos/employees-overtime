"""
Aviso diario por email de tareas que vencen hoy o están vencidas.

Idempotente: usa Task.reminder_sent_at — si el cron corre dos veces el mismo
día, no re-envía. Pensado para cron diario (ver scripts/crontab.example).
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from employees.emails import send_html_mail
from employees.models import Employee, Task


class Command(BaseCommand):
    help = "Envía a cada empleado un email con sus tareas vencidas o que vencen hoy."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra qué se enviaría sin enviar ni marcar nada.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        hoy = timezone.localtime(now).date()
        base_url = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')

        activos = Employee.objects.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=hoy),
            user__isnull=False,
        ).select_related('user')

        enviados = 0
        for employee in activos:
            pendientes = Task.objects.filter(
                assigned_to=employee,
                status='pending',
                is_recurring=False,
                due_date__isnull=False,
                due_date__date__lte=hoy,
            ).filter(
                # Idempotencia: sin aviso previo, o aviso de un día anterior
                Q(reminder_sent_at__isnull=True) | Q(reminder_sent_at__date__lt=hoy)
            ).order_by('due_date')

            if not pendientes:
                continue

            tareas = []
            for task in pendientes:
                task.vencida = timezone.localtime(task.due_date).date() < hoy
                tareas.append(task)

            destinatario = employee.user.email or employee.email
            if dry_run:
                self.stdout.write(f"[dry-run] {employee.name}: {len(tareas)} tarea(s) → {destinatario}")
                continue

            ok = send_html_mail(
                subject=f"Tienes {len(tareas)} tarea(s) por vencer o vencidas",
                template_name='tareas_vencidas.html',
                context={'employee': employee, 'tareas': tareas,
                         'board_url': f"{base_url}/board/"},
                to=destinatario,
            )
            if ok:
                Task.objects.filter(pk__in=[t.pk for t in tareas]).update(reminder_sent_at=now)
                enviados += 1

        self.stdout.write(self.style.SUCCESS(f"{enviados} email(s) de recordatorio enviados."))
