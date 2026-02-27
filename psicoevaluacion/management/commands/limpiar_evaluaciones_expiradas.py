from django.core.management.base import BaseCommand
from django.utils import timezone

from psicoevaluacion.models import Evaluacion


class Command(BaseCommand):
    help = 'Marca como EXPIRADA las evaluaciones pendientes cuyo token ha expirado'

    def handle(self, *args, **options):
        expiradas = Evaluacion.objects.filter(
            estado='PENDIENTE',
            fecha_expiracion__lt=timezone.now(),
        )
        count = expiradas.update(estado='EXPIRADA')
        self.stdout.write(self.style.SUCCESS(
            f'{count} evaluaciones marcadas como EXPIRADA'
        ))
