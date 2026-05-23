from django.db import migrations

from psicoevaluacion.memoria_pool import sync_memoria_pool


def forwards(apps, schema_editor):
    sync_memoria_pool(
        apps.get_model('psicoevaluacion', 'Prueba'),
        apps.get_model('psicoevaluacion', 'Pregunta'),
    )


def backwards(apps, schema_editor):
    # Data de seed: no se revierte.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('psicoevaluacion', '0007_resultadofinal_detalle_arbol_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
