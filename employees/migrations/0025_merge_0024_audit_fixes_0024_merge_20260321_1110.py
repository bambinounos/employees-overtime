# Recuperada del servidor de producción (2026-07-07). Merge vacío que une
# 0024_audit_fixes con 0024_merge_20260321_1110. Ya está aplicada en
# producción; el contenido de un merge es determinístico (sin operaciones).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0024_audit_fixes'),
        ('employees', '0024_merge_20260321_1110'),
    ]

    operations = [
    ]
