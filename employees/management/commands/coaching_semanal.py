"""
Coaching semanal: email por empleado con sugerencias para mejorar su bono.

Pensado para cron los lunes (ver scripts/crontab.example), después del
resumen semanal de administradores. Usa employees.sugerencias, la misma
lógica que la tarjeta "Cómo mejorar tu bono" de Mi panel.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from employees.emails import send_html_mail
from employees.models import BonusRule, Employee
from employees.sugerencias import build_sugerencias

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


class Command(BaseCommand):
    help = ("Envía a cada empleado activo un email con el estado de su bono "
            "del mes y sugerencias accionables para mejorarlo.")

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra el resumen sin enviar emails.')
        parser.add_argument('--employee-id', type=int,
                            help='Envía solo a este empleado (pruebas).')

    def handle(self, *args, **options):
        hoy = timezone.localtime(timezone.now()).date()
        year, month = hoy.year, hoy.month
        periodo = f"{MESES[month - 1]} {year}"
        base_url = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')

        empleados = Employee.objects.filter(
            profile__isnull=False,
            end_date__isnull=True,
        )
        if options['employee_id']:
            empleados = empleados.filter(pk=options['employee_id'])

        enviados = 0
        for empleado in empleados:
            sugerencias = build_sugerencias(empleado, year, month)
            if not sugerencias:
                continue

            profile_kpis = empleado.profile.kpis.all()
            bono_potencial = BonusRule.objects.filter(
                kpi__in=profile_kpis).aggregate(
                total=Sum('bonus_amount'))['total'] or 0
            bono_actual = empleado.calculate_performance_bonus(year, month)

            contexto = {
                'empleado': empleado,
                'periodo': periodo,
                'sugerencias': sugerencias,
                'bono_actual': bono_actual,
                'bono_potencial': bono_potencial,
                'panel_url': f"{base_url}/mi-panel/",
            }
            asunto = f"Cómo mejorar su bono de {periodo}"
            if options['dry_run']:
                self.stdout.write(f"[DRY RUN] {empleado.name}: "
                                  f"{len(sugerencias)} sugerencias, "
                                  f"bono ${bono_actual} de ${bono_potencial}")
                continue
            if send_html_mail(asunto, 'coaching_semanal.html', contexto, [empleado.email]):
                enviados += 1

        self.stdout.write(self.style.SUCCESS(
            f"Coaching semanal {periodo}: {enviados} emails enviados."))
