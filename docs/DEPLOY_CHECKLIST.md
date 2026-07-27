# Checklist de despliegue a producción

Servidor de referencia: Ubuntu 22.04, Python 3.10, gunicorn + Apache
(proxy inverso, `mpm_prefork` + mod_php porque Dolibarr vive en el mismo
servidor), PostgreSQL. El dominio pasa por Cloudflare.

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
  recibirá 403: revisar `access.log` de Apache antes de actualizar.

## Apache detrás de Cloudflare

- **Keepalive** (aplicado 2026-07-27 en `/etc/apache2/apache2.conf`):

  ```
  KeepAlive On
  KeepAliveTimeout 15
  MaxKeepAliveRequests 500
  ```

  Con el default de Ubuntu (`KeepAliveTimeout 5`), Cloudflare reutiliza
  conexiones que Apache ya está cerrando y aparecen errores **525 (SSL
  handshake failed)** intermitentes — se reproducía con "Save and add
  another" del admin (patrón POST + GET inmediato de la redirección).
  Tras editar: `sudo apachectl configtest && sudo systemctl reload apache2`.

- **Diagnóstico rápido de un 525**: es un fallo entre Cloudflare y el origen
  (la petición no llegó a Django). Verificar el origen con
  `openssl s_client -connect <IP>:443 -servername salarios.hellbam.com`
  (certificado y handshake), `sudo systemctl status apache2` (¿reinicio
  reciente?) y `sudo tail -50 /var/log/apache2/error.log`. La línea
  "resuming normal operations" de las 00:00 es la rotación diaria de logs,
  no un fallo.

- **Pendiente**: restringir los puertos 80/443 en la security list de Oracle
  Cloud a los [rangos de IP de Cloudflare](https://www.cloudflare.com/ips/)
  (dejando SSH abierto). Hoy los bots escanean el origen directo por IP
  buscando `.env`, `.git`, `phpinfo.php`, etc. — Apache los rechaza, pero
  mejor que ni lleguen.
