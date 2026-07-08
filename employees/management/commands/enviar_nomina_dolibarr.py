"""
Envía los recibos de nómina de un período a Dolibarr como salarios (paye=0).

Uso:
    python manage.py enviar_nomina_dolibarr                 # mes anterior (cierre)
    python manage.py enviar_nomina_dolibarr --year 2026 --month 6
"""
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from employees.nomina import enviar_recibos_dolibarr


class Command(BaseCommand):
    help = "Envía a Dolibarr los recibos de nómina de un período como salarios."

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Año del período (default: mes anterior)')
        parser.add_argument('--month', type=int, help='Mes del período (default: mes anterior)')

    def handle(self, *args, **options):
        if options['year'] and options['month']:
            year, month = options['year'], options['month']
        else:
            anterior = date.today().replace(day=1) - relativedelta(months=1)
            year, month = anterior.year, anterior.month

        resultado = enviar_recibos_dolibarr(year, month)

        self.stdout.write(self.style.SUCCESS(
            f"{len(resultado['enviados'])} recibos enviados a Dolibarr para {month:02d}/{year}."))
        if resultado['ya_sincronizados']:
            self.stdout.write(
                f"{len(resultado['ya_sincronizados'])} ya estaban sincronizados (omitidos).")
        for employee in resultado['sin_mapeo']:
            self.stdout.write(self.style.WARNING(
                f"Sin identidad Dolibarr (omitido): {employee.name}"))
        for recibo, mensaje in resultado['con_error']:
            self.stdout.write(self.style.ERROR(
                f"Error con {recibo.employee.name}: {mensaje}"))
