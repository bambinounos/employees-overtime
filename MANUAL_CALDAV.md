# Manual de Instalacion y Configuracion - Servidor CalDAV

## Indice

1. [Descripcion General](#1-descripcion-general)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Requisitos Previos](#3-requisitos-previos)
4. [Instalacion de Dependencias](#4-instalacion-de-dependencias)
5. [Configuracion del Servidor CalDAV](#5-configuracion-del-servidor-caldav)
6. [Inicio del Servidor](#6-inicio-del-servidor)
7. [Despliegue en Produccion](#7-despliegue-en-produccion)
8. [Configuracion de Clientes CalDAV](#8-configuracion-de-clientes-caldav)
9. [Sincronizacion Bidireccional con Tareas](#9-sincronizacion-bidireccional-con-tareas)
10. [Seguridad y Autenticacion](#10-seguridad-y-autenticacion)
11. [Verificacion y Diagnostico](#11-verificacion-y-diagnostico)
12. [Preguntas Frecuentes](#12-preguntas-frecuentes)

---

## 1. Descripcion General

El sistema incluye un servidor CalDAV integrado que expone los calendarios de los empleados mediante el protocolo WebDAV/CalDAV (RFC 4791). Esto permite:

- **Suscripcion a calendarios** desde clientes como Thunderbird, Outlook, Apple Calendar o calendarios moviles.
- **Alarmas automaticas** cuando se crean tareas con fecha de vencimiento en el panel de administracion.
- **Sincronizacion bidireccional**: si un empleado pospone o reprograma un evento desde Thunderbird, la fecha de la tarea en Django se actualiza automaticamente.
- **Vista web** del calendario en `/caldav/calendar/` usando FullCalendar.js.

### Componentes Principales

| Componente | Archivo | Funcion |
|---|---|---|
| Modelo de datos | `caldav/models.py` | `CalendarEvent` almacena eventos con alarmas |
| Servidor DAV | `caldav/resources.py` | Maneja GET/PUT de eventos iCalendar |
| Proveedor DAV | `caldav/dav_provider.py` | Conecta WsgiDAV con los recursos |
| Autenticacion | `caldav/auth.py` | Valida credenciales contra Django |
| Punto WSGI | `caldav/wsgi.py` | Entrada para Gunicorn en produccion |
| Script desarrollo | `run_wsgidav.py` | Servidor de pruebas local |
| Configuracion | `wsgidav.conf` | Parametros del servidor |
| Signals Django | `employees/signals.py` | Sincroniza Task <-> CalendarEvent |
| Vista web | `caldav/views.py` | Renderiza calendario FullCalendar |

---

## 2. Arquitectura del Sistema

El sistema opera con **dos procesos independientes**:

```
Puerto 8000 (Django)                     Puerto 8080 (CalDAV)
+---------------------------+            +---------------------------+
|  Aplicacion Principal     |            |  Servidor WsgiDAV         |
|                           |            |                           |
|  /admin/ (Panel Admin)    |            |  /{username}/             |
|  /api/   (REST API)       |            |  /{username}/{id}.ics     |
|  /caldav/calendar/ (Web)  |            |                           |
|                           |            |  Protocolo: CalDAV        |
|  Gunicorn / runserver     |            |  Auth: HTTP Basic         |
+---------------------------+            +---------------------------+
            |                                        |
            +------ Base de datos compartida --------+
            |       (CalendarEvent, Task, User)      |
            +----------------------------------------+
```

### Flujo de Datos

```
                    Admin Django
                         |
                    Crea/edita Task
                         |
                         v
               Signal: sync_task_to_calendar()
                         |
                    Crea CalendarEvent
                    (alarma 30 min)
                         |
                         v
               Thunderbird sincroniza
               via CalDAV (puerto 8080)
                         |
              Muestra evento con alarma
                         |
          (opcional) Usuario reprograma
                         |
                         v
               PUT /{username}/{id}.ics
                         |
                         v
              resources.py actualiza
              CalendarEvent + Task.due_date
```

---

## 3. Requisitos Previos

### 3.1. Software Base

Asegurese de tener instalada la aplicacion Django principal siguiendo los pasos del `MANUAL.md` (secciones 1.1 a 1.9).

### 3.2. Verificar Instalacion de Python

```bash
python3 --version   # Requiere Python 3.10+
```

### 3.3. Verificar que Django Funciona

```bash
source venv/bin/activate
python3 manage.py check
```

Debe mostrar `System check identified no issues`.

---

## 4. Instalacion de Dependencias

### 4.1. Desde requirements.txt (Recomendado)

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Esto instalara todas las dependencias, incluyendo las de CalDAV.

### 4.2. Instalacion Manual (Solo Dependencias CalDAV)

Si prefiere instalar solo los paquetes CalDAV:

```bash
source venv/bin/activate
pip install WsgiDAV==4.3.3 vobject==0.9.9 defusedxml==0.7.1 lxml
```

| Paquete | Version | Proposito |
|---|---|---|
| `WsgiDAV` | 4.3.3 | Framework del servidor WebDAV/CalDAV |
| `vobject` | 0.9.9 | Parseo y generacion de formato iCalendar (RFC 5545) |
| `defusedxml` | 0.7.1 | Proteccion contra ataques XXE en XML |
| `lxml` | (ultima) | Procesador XML requerido por WsgiDAV |

### 4.3. Verificar Instalacion

```bash
python3 -c "import wsgidav; print(wsgidav.__version__)"
python3 -c "import vobject; print('vobject OK')"
python3 -c "from lxml import etree; print('lxml OK')"
```

### 4.4. Aplicar Migraciones de Base de Datos

Las migraciones de CalDAV crean la tabla `CalendarEvent`:

```bash
python3 manage.py migrate caldav
```

Migraciones incluidas:

| Migracion | Descripcion |
|---|---|
| `0001_initial` | Crea tabla CalendarEvent (user, title, start_date, end_date, description, is_personal, task) |
| `0002_calendarevent_alarm_minutes` | Agrega campo `alarm_minutes` para alarmas VALARM |
| `0003_calendarevent_uid` | Agrega campo `uid` unico para compatibilidad CalDAV |

---

## 5. Configuracion del Servidor CalDAV

### 5.1. Archivo de Configuracion `wsgidav.conf`

El archivo `wsgidav.conf` en la raiz del proyecto controla el servidor CalDAV:

```ini
[wsgidav]
host = 0.0.0.0
port = 8080
provider_mapping = {
    "/": "caldav.dav_provider.CalDAVProvider",
}
verbose = 1
enable_loggers = []
props_manager = "wsgidav.props.memory_props_manager.MemoryPropsManager"
locks_manager = "wsgidav.locks.memory_locks_manager.MemoryLocksManager"
http_authenticator = {
    "domain_controller": "caldav.auth.DjangoDomainController",
    "accept_basic": True,
    "accept_digest": False,
    "default_to_digest": False,
}
```

### 5.2. Parametros Configurables

| Parametro | Valor por defecto | Descripcion |
|---|---|---|
| `host` | `0.0.0.0` | Direccion de escucha. `0.0.0.0` acepta conexiones de cualquier IP |
| `port` | `8080` | Puerto del servidor CalDAV |
| `verbose` | `1` | Nivel de log (0=silencioso, 5=maximo detalle) |
| `accept_basic` | `True` | Habilita autenticacion HTTP Basic |
| `accept_digest` | `False` | Deshabilita autenticacion Digest (no necesaria con HTTPS) |

### 5.3. Cambiar el Puerto

Si el puerto 8080 esta ocupado, edite `wsgidav.conf`:

```ini
port = 8443
```

Y si usa `run_wsgidav.py`, el puerto se lee automaticamente del archivo de configuracion.

### 5.4. Restringir Acceso por IP (Opcional)

Para limitar el acceso solo a la red local:

```ini
host = 192.168.1.100
```

---

## 6. Inicio del Servidor

### 6.1. Modo Desarrollo

```bash
source venv/bin/activate
python3 run_wsgidav.py
```

Salida esperada:

```
WsgiDAV server running on http://0.0.0.0:8080/
```

**Nota:** Este servidor usa `wsgiref.simple_server`, que es **solo para pruebas**. No lo use en produccion.

### 6.2. Verificar que el Servidor Responde

Desde otra terminal:

```bash
# Debe devolver 401 (requiere autenticacion)
curl -I http://localhost:8080/

# Con credenciales (reemplace usuario:clave)
curl -u admin:admin123 http://localhost:8080/admin/
```

### 6.3. Ejecucion Simultanea

El servidor CalDAV y la aplicacion Django deben ejecutarse al mismo tiempo:

**Terminal 1 - Django:**
```bash
source venv/bin/activate
python3 manage.py runserver 0.0.0.0:8000
```

**Terminal 2 - CalDAV:**
```bash
source venv/bin/activate
python3 run_wsgidav.py
```

---

## 7. Despliegue en Produccion

### 7.1. Servicio Systemd para CalDAV

Cree el archivo `/etc/systemd/system/caldav.service`:

```ini
[Unit]
Description=Servidor CalDAV (WsgiDAV)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/ruta/al/proyecto
Environment="DJANGO_SETTINGS_MODULE=salary_management.settings"
ExecStart=/ruta/al/proyecto/venv/bin/gunicorn \
    --workers 2 \
    --bind 0.0.0.0:8080 \
    --timeout 120 \
    caldav.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Reemplace** `/ruta/al/proyecto` con la ruta absoluta de su instalacion.

### 7.2. Habilitar e Iniciar el Servicio

```bash
sudo systemctl daemon-reload
sudo systemctl enable caldav
sudo systemctl start caldav
sudo systemctl status caldav
```

### 7.3. Configuracion Nginx (Proxy Inverso)

Agregar al bloque `server` de Nginx:

```nginx
# Proxy CalDAV - Puerto externo 8080 o subruta
location /caldav-server/ {
    proxy_pass http://127.0.0.1:8080/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Necesario para WebDAV
    proxy_set_header Depth $http_depth;
    proxy_set_header Destination $http_destination;

    # Permitir metodos WebDAV
    proxy_method $request_method;
    proxy_pass_request_headers on;

    # Tamanio maximo para eventos iCal
    client_max_body_size 1M;
}

# Descubrimiento automatico CalDAV (RFC 6764)
location /.well-known/caldav {
    return 301 $scheme://$host/caldav-server/;
}
```

### 7.4. HTTPS (Obligatorio en Produccion)

Dado que CalDAV usa autenticacion HTTP Basic, **es obligatorio** usar HTTPS en produccion para proteger las credenciales:

```bash
# Con Certbot (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d su-dominio.com
```

Una vez configurado HTTPS, la URL de CalDAV para los clientes sera:

```
https://su-dominio.com/caldav-server/{username}
```

---

## 8. Configuracion de Clientes CalDAV

### 8.1. Mozilla Thunderbird

1. Abra Thunderbird y vaya a la pestana de **Calendario**.
2. Clic derecho en el panel de calendarios izquierdo > **Nuevo calendario...**.
3. Seleccione **En la red**.
4. Configure:
   - **Formato:** CalDAV
   - **Ubicacion:** `http://<IP_SERVIDOR>:8080/<nombre_usuario>`
     - Ejemplo: `http://192.168.1.50:8080/jdoe`
     - Con HTTPS: `https://su-dominio.com/caldav-server/jdoe`
5. Ingrese las **credenciales Django** del empleado cuando se le solicite.
6. Asigne un nombre y color al calendario.
7. Clic en **Suscribirse**.

**Resultado esperado:** Los eventos aparecen en el calendario de Thunderbird con alarmas de 30 minutos antes de la hora de vencimiento de cada tarea.

### 8.2. Microsoft Outlook (CalDAV Synchronizer)

Outlook no soporta CalDAV nativamente. Se requiere un plugin:

1. Descargue e instale [CalDAV Synchronizer](https://caldavsynchronizer.org/) (gratuito).
2. En Outlook, vaya a **CalDAV Synchronizer** > **Synchronization Profiles**.
3. Cree un nuevo perfil con:
   - **DAV URL:** `http://<IP_SERVIDOR>:8080/<nombre_usuario>`
   - **Username:** Nombre de usuario Django
   - **Password:** Contrasena Django
   - **Sync Interval:** 15 minutos (recomendado)
4. Clic en **Test Connection** para verificar.
5. Guarde y sincronice.

### 8.3. Apple Calendar (macOS / iOS)

**macOS:**
1. Abra **Calendario** > **Preferencias** > **Cuentas**.
2. Clic en **+** > Seleccione **CalDAV**.
3. Tipo de cuenta: **Manual**.
4. Configure:
   - **Servidor:** `<IP_SERVIDOR>:8080`
   - **Nombre de usuario:** Usuario Django
   - **Contrasena:** Contrasena Django

**iOS (iPhone/iPad):**
1. Vaya a **Ajustes** > **Calendario** > **Cuentas** > **Anadir cuenta**.
2. Seleccione **Otra** > **Anadir cuenta CalDAV**.
3. Configure:
   - **Servidor:** `<IP_SERVIDOR>:8080`
   - **Nombre de usuario:** Usuario Django
   - **Contrasena:** Contrasena Django

### 8.4. Android (DAVx5)

1. Instale [DAVx5](https://www.davx5.com/) desde F-Droid o Google Play.
2. Cree una nueva cuenta:
   - **URL base:** `http://<IP_SERVIDOR>:8080/<nombre_usuario>`
   - Credenciales Django
3. Seleccione los calendarios a sincronizar.
4. DAVx5 sincronizara con la app de calendario nativa de Android.

---

## 9. Sincronizacion Bidireccional con Tareas

### 9.1. De Django a CalDAV (Automatica)

Cuando se crea o edita una tarea (`Task`) en el panel de administracion (`/admin/employees/task/add/`):

- Si la tarea tiene `due_date` (fecha de vencimiento), se crea automaticamente un `CalendarEvent` asociado.
- El evento dura **1 hora** a partir de la fecha de vencimiento.
- Se configura una **alarma de 30 minutos** antes del evento (VALARM).
- Si se elimina la `due_date`, el evento se borra.
- Si se elimina la tarea, el evento se borra.

**Ejemplo:** Si crea una tarea "Entregar informe" con vencimiento el 15/03/2025 a las 10:00:
- Se genera un evento CalDAV: 10:00 - 11:00
- Alarma a las 09:30
- Visible en Thunderbird tras la proxima sincronizacion

### 9.2. De CalDAV a Django (Bidireccional)

Cuando un usuario **reprograma un evento desde Thunderbird** u otro cliente CalDAV:

1. El cliente envia un `PUT` con el nuevo iCalendar al servidor.
2. El servidor actualiza el `CalendarEvent` en la base de datos.
3. Si el evento esta vinculado a una tarea (`task_id` no es nulo):
   - Se actualiza `Task.due_date` con la nueva fecha/hora.
   - Se usa una bandera `_skip_calendar_sync` para evitar que el signal de Django reescriba el evento innecesariamente.

**Ejemplo:** Si en Thunderbird mueve el evento "Entregar informe" del 15/03 al 20/03 a las 14:00:
- `CalendarEvent.start_date` se actualiza a 20/03 14:00
- `Task.due_date` se actualiza a 20/03 14:00
- Ambos registros quedan sincronizados

### 9.3. Limitaciones

- La sincronizacion funciona unicamente para **fecha/hora de inicio** (`start_date`/`due_date`). El titulo y descripcion del evento no se propagan de vuelta a la tarea.
- Los eventos creados directamente desde Thunderbird (sin tarea asociada) se almacenan como `CalendarEvent` sin vinculo a ninguna tarea.
- Los empleados deben tener un **usuario Django asignado** (`Employee.user`) para que la sincronizacion funcione.

---

## 10. Seguridad y Autenticacion

### 10.1. Mecanismo de Autenticacion

El servidor CalDAV usa **HTTP Basic Authentication** contra la base de datos de usuarios de Django:

- El archivo `caldav/auth.py` implementa `DjangoDomainController`.
- Solo usuarios con `is_active = True` pueden autenticarse.
- Cada usuario **solo ve su propio calendario** (aislamiento por usuario).

### 10.2. Aislamiento de Datos

```
GET /{username}/ --> Solo devuelve CalendarEvents donde user = usuario autenticado
```

Un usuario **no puede** ver ni modificar eventos de otro usuario, incluso conociendo su nombre.

### 10.3. Recomendaciones de Seguridad

| Recomendacion | Razon |
|---|---|
| Usar HTTPS en produccion | HTTP Basic envia credenciales en Base64 (legible sin cifrado) |
| Contrasenas fuertes | El servidor es accesible por red |
| Firewall en puerto 8080 | Limitar acceso a IPs de confianza si no se usa Nginx |
| Monitorear logs | `verbose = 2` en `wsgidav.conf` para auditar accesos |

### 10.4. Configurar Firewall (UFW)

```bash
# Permitir solo desde red local
sudo ufw allow from 192.168.1.0/24 to any port 8080

# O permitir desde cualquier IP (si usa HTTPS + Nginx)
sudo ufw allow 8080/tcp
```

---

## 11. Verificacion y Diagnostico

### 11.1. Verificar que las Migraciones Estan Aplicadas

```bash
python3 manage.py showmigrations caldav
```

Salida esperada (todas con `[X]`):

```
caldav
 [X] 0001_initial
 [X] 0002_calendarevent_alarm_minutes
 [X] 0003_calendarevent_uid
```

### 11.2. Verificar la Creacion Automatica de Eventos

```bash
python3 manage.py shell
```

```python
from employees.models import Task, Employee, TaskList
from caldav.models import CalendarEvent

# Ver tareas con eventos asociados
for t in Task.objects.filter(due_date__isnull=False):
    events = CalendarEvent.objects.filter(task=t)
    print(f"Tarea: {t.title} | due_date: {t.due_date} | Eventos CalDAV: {events.count()}")
```

### 11.3. Verificar Conectividad del Servidor

```bash
# Sin autenticacion (debe devolver 401)
curl -v http://localhost:8080/

# Con autenticacion (debe devolver 207 Multi-Status)
curl -u usuario:clave -X PROPFIND http://localhost:8080/usuario/
```

### 11.4. Probar Descarga de un Evento iCal

```bash
# Listar eventos (PROPFIND)
curl -u usuario:clave -X PROPFIND http://localhost:8080/usuario/

# Descargar un evento especifico
curl -u usuario:clave http://localhost:8080/usuario/1.ics
```

Salida esperada (formato iCalendar):

```
BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Entregar informe
DTSTART:20250315T100000
DTEND:20250315T110000
DESCRIPTION:Descripcion de la tarea
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Entregar informe
TRIGGER:-PT30M
END:VALARM
END:VEVENT
END:VCALENDAR
```

### 11.5. Ejecutar Tests Automatizados

```bash
python3 -m django test caldav --settings=salary_management.settings --verbosity=2
```

Tests incluidos:

| Test | Descripcion |
|---|---|
| `test_put_creates_event` | Crear un evento via PUT |
| `test_put_updates_event` | Actualizar un evento existente |
| `test_put_parses_alarm` | Parsear alarma VALARM |
| `test_thunderbird_reschedule_updates_task_due_date` | Reprogramar desde Thunderbird actualiza Task |
| `test_thunderbird_reschedule_no_loop` | No se crean duplicados por loop de signals |
| `test_unlinked_event_no_task_update` | Eventos sin tarea no causan errores |

### 11.6. Problemas Comunes

| Problema | Causa | Solucion |
|---|---|---|
| `LXML is not available` | Falta la libreria lxml | `pip install lxml` |
| `ModuleNotFoundError: 'wsgidav'` | Dependencias no instaladas | `pip install WsgiDAV vobject` |
| `401 Unauthorized` en cliente | Credenciales incorrectas | Verificar usuario/contrasena en Django admin |
| Eventos no aparecen en Thunderbird | URL incorrecta | Verificar formato: `http://ip:8080/username` |
| Evento se crea pero sin alarma | `alarm_minutes` es None | Verificar que la tarea tiene `due_date` asignada |
| Reprogramar en Thunderbird no actualiza tarea | Evento sin `task_id` | Solo eventos creados desde Django admin tienen vinculo |
| `Address already in use` al iniciar | Puerto 8080 ocupado | Cambiar puerto en `wsgidav.conf` o detener el proceso existente |
| `No module named 'caldav'` | Path de Python incorrecto | Verificar que ejecuta desde la raiz del proyecto |

---

## 12. Preguntas Frecuentes

**P: Se necesita ejecutar ambos servidores (Django y CalDAV)?**
R: Si. Django sirve la aplicacion web (puerto 8000) y WsgiDAV sirve el protocolo CalDAV (puerto 8080). Son procesos independientes que comparten la misma base de datos.

**P: Que pasa si el servidor CalDAV se detiene?**
R: Los eventos siguen almacenados en la base de datos. Los clientes CalDAV no podran sincronizar hasta que el servidor se reinicie, pero no se pierde informacion.

**P: Los empleados necesitan una cuenta especial para CalDAV?**
R: No. Usan sus mismas credenciales de Django (usuario y contrasena). El unico requisito es que el `Employee` tenga un `User` de Django asociado (`Employee.user`).

**P: Se puede usar CalDAV sin crear tareas?**
R: Si. Los clientes CalDAV pueden crear eventos directamente via PUT. Estos se almacenan como `CalendarEvent` sin tarea vinculada.

**P: Desde Thunderbird se puede posponer la fecha de una tarea?**
R: Si. Al mover o reprogramar un evento en Thunderbird, el servidor actualiza automaticamente la `due_date` de la tarea asociada en Django. La sincronizacion es bidireccional.

**P: Cuantos empleados puede manejar el servidor CalDAV?**
R: Con Gunicorn y 2 workers, el servidor puede manejar cientos de usuarios concurrentes sin problemas. Para mas de 500 usuarios simultaneos, considere aumentar los workers y usar un balanceador de carga.

**P: Se respalda la informacion de CalDAV con el script backup.sh?**
R: Si. Los eventos CalDAV se almacenan en la base de datos PostgreSQL, que se respalda completamente con `pg_dump`. El archivo `wsgidav.conf` tambien se incluye en el backup.

**P: Se puede cambiar el tiempo de alarma por defecto (30 minutos)?**
R: Si. Edite la constante `DEFAULT_ALARM_MINUTES` en `employees/signals.py`. El valor se aplica a los nuevos eventos creados a partir de tareas. Los eventos existentes no se modifican retroactivamente.
