# Configuracion de Calendario CalDAV - Guia para Clientes

## Datos de conexion

| Campo | Valor |
|-------|-------|
| **URL** | `https://[tu-dominio]/caldav-server/[tu_usuario]/` |
| **Usuario** | Tu usuario del sistema (el mismo que usas para iniciar sesion) |
| **Password** | Tu contrasena del sistema |
| **Tipo** | CalDAV |

Cada usuario tiene su **calendario individual** — solo veras tus propias tareas.

---

## Thunderbird

1. Abre Thunderbird y click en el icono de **Calendario** (barra lateral izquierda)
2. En el panel de calendarios, click derecho → **"Nuevo calendario..."**
3. Selecciona **"En la red"** → Siguiente
4. Formato: **CalDAV**
5. URL: `https://[tu-dominio]/caldav-server/[tu_usuario]/`
6. Nombre: "Tareas Trabajo" (o el que prefieras)
7. Click **Siguiente** → ingresa tu usuario y contrasena
8. Marca **"Recordar contrasena"** si deseas
9. Listo — tus tareas apareceran como eventos en el calendario

---

## Android (Google Calendar + DAVx5)

Google Calendar no soporta CalDAV directamente. Se usa la app **DAVx5**:

1. Instala **DAVx5** desde Play Store o F-Droid
2. Abre DAVx5 → **"+"** → **"Iniciar sesion con URL y nombre de usuario"**
3. URL base: `https://[tu-dominio]/caldav-server/`
4. Ingresa tu usuario y contrasena
5. DAVx5 detectara tu calendario automaticamente
6. Marca la casilla del calendario para sincronizar
7. Abre Google Calendar — tus eventos apareceran

---

## iPhone / Mac (Apple Calendar)

### iPhone / iPad

1. Ve a **Ajustes → Calendario → Cuentas → Anadir cuenta**
2. Selecciona **"Otra"** → **"Anadir cuenta CalDAV"**
3. Servidor: `[tu-dominio]`
4. Nombre de usuario: tu usuario del sistema
5. Contrasena: tu contrasena
6. Descripcion: "Tareas Trabajo"
7. En **Ajustes avanzados**:
   - Ruta: `/caldav-server/[tu_usuario]/`
   - Puerto: `443`
   - SSL: **Activado**

### Mac

1. Abre **Calendario** → Menu **Calendario** → **Cuentas...**
2. Click **"+"** → selecciona **"Otra cuenta CalDAV..."**
3. Tipo: **CalDAV**
4. Usuario: tu usuario del sistema
5. Contrasena: tu contrasena
6. Direccion del servidor: `https://[tu-dominio]/caldav-server/[tu_usuario]/`

---

## Outlook (con plugin CalDav Synchronizer)

Outlook no soporta CalDAV de forma nativa. Se necesita un plugin:

1. Descarga e instala **CalDav Synchronizer** desde caldavsynchronizer.org
2. En Outlook: **Herramientas → CalDav Synchronizer → Perfiles de sincronizacion**
3. Click **Anadir** → selecciona **CalDAV generico**
4. Configura:
   - URL: `https://[tu-dominio]/caldav-server/[tu_usuario]/`
   - Usuario y contrasena
   - Intervalo de sincronizacion: 15 minutos (recomendado)
5. Click **Probar configuracion** para verificar
6. Guardar

---

## Que se sincroniza

### Desde el sistema al calendario

| Accion en el sistema | Resultado en tu calendario |
|---------------------|---------------------------|
| Se crea una tarea con fecha limite | Aparece un evento de 1 hora con alarma 30 min antes |
| Se cambia la fecha de una tarea | El evento se mueve automaticamente |
| Se elimina una tarea | El evento desaparece |
| Se completa una tarea recurrente | Se crea la siguiente tarea con nuevo evento |

### Desde el calendario al sistema

| Accion en tu calendario | Resultado en el sistema |
|------------------------|------------------------|
| Mover un evento a otra fecha | La fecha limite de la tarea se actualiza |

---

## Solucion de problemas

| Problema | Solucion |
|----------|----------|
| "No se puede conectar" | Verifica que la URL termine con `/` y que tu usuario sea exacto (las mayusculas importan) |
| "Error de autenticacion" | Verifica que puedes iniciar sesion en el sistema web con el mismo usuario y contrasena |
| "Calendario vacio" | Solo aparecen tareas que tienen fecha limite asignada |
| "Eventos duplicados" | Evita editar el mismo evento en el calendario y en el sistema al mismo tiempo |
| "Los cambios no se reflejan" | Espera al intervalo de sincronizacion o fuerza una sincronizacion manual en tu cliente |

---

## Notas importantes

- El calendario es **personal**: cada usuario solo ve sus propias tareas
- La alarma por defecto es **30 minutos antes** de la fecha limite
- Los eventos se crean como bloques de **1 hora** a partir de la fecha limite
- Si mueves un evento en tu calendario, la fecha limite de la tarea se actualizara automaticamente en el sistema
