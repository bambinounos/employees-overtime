# PayrollConnect - Manual de Instalación y Configuración

Módulo Dolibarr que sincroniza Facturas, Presupuestos, Notas de Crédito y Productos con el servidor Django de nóminas mediante webhooks en tiempo real.

## Requisitos

- Dolibarr >= 16.0
- PHP >= 7.4 con extensión cURL habilitada
- Servidor Django (payroll) en funcionamiento

## 1. Instalación del módulo

1. Ir a **Inicio > Administración > Módulos/Aplicaciones**
2. Click en **Desplegar un módulo externo (paquete/archivo)**
3. Subir el archivo `module_payroll_connect-x.x.x.zip`
4. Buscar "Payroll Connect" en la lista de módulos (categoría **RR.HH.**)
5. Activar el módulo con el interruptor

## 2. Configuración

Tras activar el módulo, click en el icono de engranaje junto al nombre del módulo. Se abre la página con dos pestañas: **Settings** y **Retry Queue**.

### 2.1 Pestaña Settings

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| **Webhook URL** | Endpoint del servidor Django que recibe los webhooks | `https://salarios.ejemplo.com/api/webhook/dolibarr/` |
| **API Secret** | Clave compartida para firmar los webhooks con HMAC-SHA256 | (cadena hexadecimal de 64 caracteres) |

### 2.2 Generar el API Secret

Ejecutar en cualquier terminal:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Esto genera una clave segura como: `a3f8b2c1d4e5f6789...`

**IMPORTANTE:** La misma clave debe configurarse en dos lugares:

| Lugar | Dónde |
|-------|-------|
| **Dolibarr** | Módulo PayrollConnect > Settings > API Secret |
| **Django** | Admin > Dolibarr Instances > (tu instancia) > Api secret |

### 2.3 Configurar la instancia en Django

En el admin de Django (`/admin/`), ir a **Dolibarr Instances** y crear una entrada:

| Campo | Descripción |
|-------|-------------|
| **Name** | Nombre descriptivo (ej: "Empresa A") |
| **Professional ID** | El valor de **ID Profesional 1** del panel de administración de Dolibarr (Admin > Empresa/Organización) |
| **Api secret** | La misma clave generada en el paso 2.2 |

### 2.4 Pestaña Retry Queue

Muestra los webhooks que fallaron al enviarse. Desde aquí se puede:

- Ver el estado de eventos pendientes y fallidos
- Click **Process Retry Queue Now** para reintentar todos los pendientes
- Click **Retry Now** junto a un evento individual para reenviar uno específico

## 3. Eventos sincronizados

El módulo captura automáticamente estos eventos de Dolibarr:

| Evento | Trigger | Cuándo se dispara |
|--------|---------|-------------------|
| Factura validada | `BILL_VALIDATE` (type=0) | Al validar una factura estándar |
| Nota de crédito validada | `BILL_VALIDATE` (type=2) | Al validar una nota de crédito |
| Presupuesto validado | `PROPAL_VALIDATE` | Al validar un presupuesto/proforma |
| Producto creado | `PRODUCT_CREATE` | Al crear un nuevo producto |

## 4. Autenticación

Cada webhook enviado incluye dos cabeceras HTTP:

| Cabecera | Contenido |
|----------|-----------|
| `X-Dolibarr-Signature` | Firma HMAC-SHA256 del body JSON usando el API Secret |
| `X-Dolibarr-Professional-ID` | El ID Profesional 1 de la empresa en Dolibarr |

El servidor Django valida la firma recalculando el HMAC y comparándolo con la cabecera recibida.

## 5. Cola de reintentos

Si un webhook falla (servidor Django caído, timeout, etc.):

1. El evento se guarda automáticamente en la cola de reintentos
2. Un cron job lo reintenta cada 15 minutos con **backoff exponencial** (15min, 30min, 1h, 2h...)
3. Después de **10 intentos fallidos**, el evento se marca como `failed`
4. Los eventos fallidos pueden reintentarse manualmente desde la pestaña Retry Queue

## 6. Widget de Dashboard

El módulo incluye un widget para el dashboard de Dolibarr que muestra:

- Cantidad de webhooks pendientes de reenvío
- Cantidad de webhooks fallidos definitivamente
- Indicador verde si todo está sincronizado

Para habilitarlo: **Inicio > Configurar la página** > activar **Payroll Connect Status**.

## 7. Solución de problemas

| Problema | Causa probable | Solución |
|----------|---------------|----------|
| Error 500 al guardar configuración | Versión de Dolibarr incompatible | Actualizar el módulo a v1.1.4+ |
| No aparece icono de configuración | Módulo sin `config_page_url` | Actualizar el módulo a v1.1.3+ |
| Error al crear tabla en PostgreSQL | SQL con sintaxis MySQL | Actualizar el módulo a v1.1.2+ |
| Webhooks no llegan a Django | URL o Secret incorrectos | Verificar que ambos valores coincidan exactamente en Dolibarr y Django |
| "Unknown Dolibarr instance" en Django | Professional ID no coincide | Verificar que el ID Profesional 1 de Dolibarr coincida con el campo `professional_id` en Django |
