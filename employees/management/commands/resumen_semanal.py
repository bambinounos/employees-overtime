"""
Resumen semanal para administradores (superusers con email).

Pensado para cron los lunes (ver scripts/crontab.example).
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from employees.emails import send_html_mail
from employees.models import SolicitudAusencia, Task


class Command(BaseCommand):
    help = "Envía a los superusers el resumen semanal: tareas, ausencias y evaluaciones pendientes."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra el resumen sin enviar emails.')

    def handle(self, *args, **options):
        from psicoevaluacion.models import Evaluacion

        now = timezone.now()
        hasta = timezone.localtime(now)
        desde = hasta - timedelta(days=7)
        base_url = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')

        tareas_completadas = Task.objects.filter(
            completed_at__gte=desde, completed_at__lte=hasta).count()

        vencidas_qs = Task.objects.filter(
            status='pending', is_recurring=False,
            due_date__isnull=False, due_date__lt=now,
        ).select_related('assigned_to')
        tareas_vencidas = vencidas_qs.count()
        detalle_vencidas = [
            {'nombre': fila['assigned_to__name'], 'cantidad': fila['cantidad']}
            for fila in vencidas_qs.values('assigned_to__name')
                                   .annotate(cantidad=Count('id'))
                                   .order_by('-cantidad')[:10]
        ]

        ausencias_pendientes = SolicitudAusencia.objects.filter(estado='PENDIENTE').count()
        evaluaciones_sin_revisar = Evaluacion.objects.filter(estado='COMPLETADA').count()

        contexto = {
            'desde': desde, 'hasta': hasta,
            'tareas_completadas': tareas_completadas,
            'tareas_vencidas': tareas_vencidas,
            'detalle_vencidas': detalle_vencidas,
            'ausencias_pendientes': ausencias_pendientes,
            'evaluaciones_sin_revisar': evaluaciones_sin_revisar,
            'dashboard_url': f"{base_url}/dashboard/",
            'aprobaciones_url': f"{base_url}/ausencias/aprobar/",
        }

        destinatarios = list(
            User.objects.filter(is_superuser=True, is_active=True)
            .exclude(email='').values_list('email', flat=True))

        if options['dry_run']:
            self.stdout.write(f"[dry-run] Resumen: {contexto}")
            self.stdout.write(f"[dry-run] Destinatarios: {destinatarios}")
            return

        if not destinatarios:
            self.stdout.write(self.style.WARNING("Ningún superuser tiene email configurado."))
            return

        ok = send_html_mail(
            subject="Resumen semanal — tareas, ausencias y evaluaciones",
            template_name='resumen_semanal.html',
            context=contexto,
            to=destinatarios,
        )
        if ok:
            self.stdout.write(self.style.SUCCESS(f"Resumen enviado a {len(destinatarios)} admin(s)."))
        else:
            self.stdout.write(self.style.ERROR("Fallo el envío (ver logs)."))
