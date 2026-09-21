"""Management command to optimize CalDAV events in database:
1. Populate empty raw_ical fields so that serialize_event_to_ical doesn't need to rebuild them via vobject on each PROPFIND/REPORT request.
2. Strip any RFC 4791 non-compliant METHOD properties (like METHOD:PUBLISH) which cause Thunderbird dismiss issues.
"""
import re
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from caldav.models import CalendarEvent
from caldav.storage import serialize_event_to_ical


class Command(BaseCommand):
    help = "Optimiza eventos CalDAV poblando raw_ical y limpiando METHOD:PUBLISH para cumplir RFC 4791"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Filtrar por nombre de usuario (ej. licitaciones). Si no se especifica, procesa todos los usuarios.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula la optimización sin escribir en la base de datos.",
        )

    def handle(self, *args, **options):
        username = options.get("username")
        dry_run = options.get("dry_run", False)

        qs = CalendarEvent.objects.all().select_related("user")
        if username:
            try:
                user = User.objects.get(username=username)
                qs = qs.filter(user=user)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Usuario '{username}' no existe."))
                return

        total = qs.count()
        self.stdout.write(f"Iniciando optimización de {total} eventos CalDAV{' (DRY RUN)' if dry_run else ''}...")

        poblados = 0
        metodos_limpiados = 0
        sin_cambios = 0

        for event in qs.iterator():
            modificado = False
            raw = event.raw_ical or ""

            # 1. Si está vacío, generar raw_ical canónico
            if not raw.strip():
                raw = serialize_event_to_ical(event)
                poblados += 1
                modificado = True

            # 2. Si contiene METHOD:..., removerlo
            if "METHOD:" in raw:
                raw_limpio = re.sub(r"METHOD:[^\r\n]+\r?\n", "", raw, flags=re.IGNORECASE)
                if raw_limpio != raw:
                    raw = raw_limpio
                    metodos_limpiados += 1
                    modificado = True

            if modificado:
                if not dry_run:
                    event.raw_ical = raw
                    event.save(update_fields=["raw_ical"])
            else:
                sin_cambios += 1

        self.stdout.write(self.style.SUCCESS(
            f"Optimización completada:\n"
            f"  - Total procesados: {total}\n"
            f"  - raw_ical generados/poblados: {poblados}\n"
            f"  - METHOD:PUBLISH limpiados: {metodos_limpiados}\n"
            f"  - Sin cambios (ya óptimos): {sin_cambios}"
        ))
