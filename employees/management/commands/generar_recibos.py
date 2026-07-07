"""
Genera los recibos de nómina (snapshots) de un período.

Uso:
    python manage.py generar_recibos                 # mes anterior (cierre)
    python manage.py generar_recibos --year 2026 --month 6
"""
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from employees.nomina import generar_recibos_mes


class Command(BaseCommand):
    help = "Genera los recibos de nómina de todos los empleados activos para un período."

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Año del período (default: mes anterior)')
        parser.add_argument('--month', type=int, help='Mes del período (default: mes anterior)')

    def handle(self, *args, **options):
        if options['year'] and options['month']:
            year, month = options['year'], options['month']
        else:
            anterior = date.today().replace(day=1) - relativedelta(months=1)
            year, month = anterior.year, anterior.month

        generados, omitidos = generar_recibos_mes(year, month)

        self.stdout.write(self.style.SUCCESS(
            f"{len(generados)} recibos generados para {month:02d}/{year}."))
        for employee in omitidos:
            self.stdout.write(self.style.WARNING(
                f"Omitido (sin salario configurado): {employee.name}"))
