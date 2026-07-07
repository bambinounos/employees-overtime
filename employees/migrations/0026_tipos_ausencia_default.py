"""Data migration: tipos de ausencia por defecto."""
from django.db import migrations

TIPOS = [
    # (nombre, descuenta_saldo, es_remunerada)
    ("Vacaciones", True, True),
    ("Permiso médico", False, True),
    ("Permiso sin sueldo", False, False),
]


def crear_tipos(apps, schema_editor):
    TipoAusencia = apps.get_model('employees', 'TipoAusencia')
    for nombre, descuenta, remunerada in TIPOS:
        TipoAusencia.objects.get_or_create(
            nombre=nombre,
            defaults={'descuenta_saldo': descuenta, 'es_remunerada': remunerada, 'activo': True},
        )


def eliminar_tipos(apps, schema_editor):
    TipoAusencia = apps.get_model('employees', 'TipoAusencia')
    TipoAusencia.objects.filter(
        nombre__in=[t[0] for t in TIPOS], solicitudausencia__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0025_tipoausencia_employee_dias_vacaciones_anuales_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_tipos, eliminar_tipos),
    ]
