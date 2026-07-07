# Checklist de despliegue a producción

Servidor de referencia: Ubuntu 22.04, Python 3.10, gunicorn + nginx, PostgreSQL.

## Cada deploy (rutina)

```bash
cd /home/ubuntu/employees_overtime
git pull
venv/bin/pip install -r requirements.txt   # solo si cambió requirements.txt
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
kill -HUP $(pgrep -f 'gunicorn.*employees_overtime' | head -1)
```

Verificar tras el deploy:

- [ ] La home carga y el footer muestra la versión nueva (archivo `VERSION`).
- [ ] `python manage.py showmigrations | grep '\[ \]'` no muestra migraciones pendientes.
- [ ] Login como empleado normal: tablero de tareas funciona (drag & drop).

## Una sola vez (configuración del servidor)

- [ ] `salary_management/local_settings.py` creado a partir de
      `salary_management/local_settings.example.py` con:
  - [ ] `DEBUG = False`
  - [ ] `SECRET_KEY` propia (no la del repo)
  - [ ] `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` con el dominio real
  - [ ] `DATABASES` PostgreSQL
  - [ ] SMTP real (`EMAIL_*`, `DEFAULT_FROM_EMAIL`)
- [ ] Directorio `logs/` creado junto a `manage.py` (activa el log rotativo
      `logs/app.log` definido en settings): `mkdir -p logs`
- [ ] Crontab instalado según `scripts/crontab.example`.
- [ ] `~/.pgpass` configurado para `backup.sh` y backup probado a mano.
- [ ] Rotar credenciales si alguna vez se compartieron por chat/email
      (contraseña de PostgreSQL, SECRET_KEY).

## Seguridad de la API (desde v1.5.0)

- La API DRF exige sesión autenticada (`IsAuthenticated` global).
  El webhook de Dolibarr NO se ve afectado (usa HMAC con `AllowAny` explícito).
- `/api/worklogs/` filtra por empleado dueño; `employee_salary`,
  `kpi-history` y `performance_report` solo muestran datos propios salvo
  superuser.
- Si algún integrador externo consumía `/api/worklogs/` sin sesión, ahora
  recibirá 403: revisar `access.log` de nginx antes de actualizar.
