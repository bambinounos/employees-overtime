# Guia de Configuracion Post-Actualizacion v1.1 — Modulo de Ventas y Comisiones

Esta guia describe los pasos necesarios para configurar el sistema despues de actualizar a la version 1.1, que incluye la integracion con Dolibarr para ventas, comisiones y KPIs automatizados.

> **Importante:** Los datos existentes (empleados, salarios, horas trabajadas, bonos, KPIs y registros de rendimiento de meses anteriores) se conservan intactos. Esta actualizacion **no modifica ni borra** ningun dato previo.

---

## Indice

1. [Aplicar la actualizacion](#1-aplicar-la-actualizacion)
2. [Configuracion obligatoria: Perfiles de Trabajo](#2-configuracion-obligatoria-perfiles-de-trabajo-jobprofile)
3. [Configuracion de Dolibarr (solo si aplica)](#3-configuracion-de-dolibarr-solo-si-aplica)
4. [Configuracion de Bonos Escalonados (opcional)](#4-configuracion-de-bonos-escalonados-opcional)
5. [Verificacion post-configuracion](#5-verificacion-post-configuracion)
6. [Referencia de nuevos modelos](#6-referencia-de-nuevos-modelos)
7. [Preguntas frecuentes](#7-preguntas-frecuentes)

---

## 1. Aplicar la actualizacion

### 1.1. Actualizar el codigo

```bash
cd /ruta/del/proyecto
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
```

### 1.2. Aplicar migraciones de base de datos

```bash
python3 manage.py migrate
```

Esto ejecutara dos migraciones:
- `0016`: Crea los nuevos modelos (`JobProfile`, `DolibarrInstance`, `DolibarrUserIdentity`, `SalesRecord`, `ProductCreationLog`, `WebhookLog`, `KPIBonusTier`) y agrega campos `internal_code` y `min_volume_threshold` a KPI, y `profile` a Employee.
- `0017`: Agrega el campo `is_suspect_duplicate` a `ProductCreationLog`.

> Ninguna de estas migraciones modifica datos existentes. Solo agregan tablas y columnas nuevas con valores por defecto seguros.

### 1.3. Recopilar archivos estaticos y reiniciar

```bash
python3 manage.py collectstatic --noinput
sudo systemctl restart gunicorn   # o el servidor que utilice
```

---

## 2. Configuracion obligatoria: Perfiles de Trabajo (JobProfile)

### Por que es necesario

El campo `profile` en Employee es **nullable** (`null=True`). Esto significa que el sistema sigue funcionando sin configurar nada: si un empleado no tiene perfil asignado, se evaluan **todos** los KPIs existentes (comportamiento identico al anterior).

Sin embargo, cuando se cree el KPI de `SALES_EFFECTIVENESS` para vendedores, este se evaluara tambien para empleados administrativos (resultando en 0% efectividad). Para evitar esto, se recomienda configurar perfiles.

### Opcion A: Script automatico (recomendado para la primera vez)

Este script crea un perfil "Standard" con todos los KPIs existentes y lo asigna a todos los empleados que no tienen perfil:

```bash
python3 manage.py shell -c "exec(open('scripts/setup_profiles.py').read()); run()"
```

Despues, se pueden crear perfiles adicionales manualmente desde el admin.

### Opcion B: Configuracion manual desde el Panel de Administracion

1. Acceda a `http://<servidor>/admin/`
2. Vaya a **"Job profiles"** en la seccion Employees

#### Paso 2.1: Crear perfiles

Cree los perfiles que necesite segun los roles de su empresa. Ejemplo:

| Perfil | KPIs asociados | Gana comisiones? |
|---|---|---|
| **Administrativo** | Productividad General, Calidad Administrativa | No |
| **Vendedor** | Productividad General, Efectividad de Ventas, Creacion de Productos | Si |
| **Digitalizador** | Productividad General, Creacion de Productos | No |
| **Gerente** | Productividad General, Calidad Administrativa | No |

Para cada perfil:
1. Click en **"Add Job profile"**
2. Escriba el nombre (ej: "Vendedor")
3. Seleccione los KPIs aplicables en el selector horizontal
4. Marque **"Earns commissions"** si este perfil cobra comisiones de ventas
5. Guarde

#### Paso 2.2: Asignar perfil a cada empleado

1. Vaya a **"Employees"**
2. Abra cada empleado
3. Seleccione su **"Profile"** en el dropdown (aparecera al final del formulario)
4. Guarde

> **Nota:** Si un empleado ya tiene perfil asignado (por ejemplo, via el script), no es necesario volver a configurarlo.

#### Paso 2.3: Configurar KPIs de ventas (solo si aplica)

Si su empresa usa Dolibarr y quiere medir efectividad de ventas:

1. Vaya a **"KPIs"**
2. Cree un nuevo KPI:
   - **Name:** Efectividad de Ventas
   - **Measurement type:** Percentage
   - **Target value:** 35 (o el porcentaje minimo deseado)
   - **Internal code:** `SALES_EFFECTIVENESS`
   - **Min volume threshold:** 10 (minimo de proformas para ser elegible al bono)
3. Guarde
4. Asegurese de que este KPI este asociado al perfil "Vendedor"

---

## 3. Configuracion de Dolibarr (solo si aplica)

Si su empresa utiliza Dolibarr como ERP y desea sincronizar las ventas automaticamente, siga estos pasos. **Si no usa Dolibarr, puede omitir toda esta seccion.**

### 3.1. Configurar el lado Django

#### Paso 3.1.1: Crear la instancia de Dolibarr

1. En el admin, vaya a **"Dolibarr instances"**
2. Click en **"Add Dolibarr instance"**
3. Complete:
   - **Name:** Nombre descriptivo (ej: "Empresa Principal")
   - **Professional ID:** El valor del campo "ID Profesional 1" configurado en Dolibarr (Admin > Empresa > ID Profesional 1). Este valor debe coincidir exactamente.
   - **API Secret:** Una clave secreta compartida entre Django y Dolibarr. Genere una clave segura, por ejemplo:
     ```bash
     python3 -c "import secrets; print(secrets.token_hex(32))"
     ```
4. Guarde. **Copie el API Secret** ya que lo necesitara para configurar Dolibarr.

#### Paso 3.1.2: Mapear usuarios de Dolibarr a empleados

Para cada vendedor/empleado que use Dolibarr:

1. Vaya a **"Dolibarr user identities"**
2. Click en **"Add Dolibarr user identity"**
3. Complete:
   - **Employee:** Seleccione el empleado local
   - **Dolibarr instance:** Seleccione la instancia creada en el paso anterior
   - **Dolibarr user id:** El ID numerico (rowid) del usuario en Dolibarr. Puede encontrarlo en Dolibarr yendo a Usuarios > seleccionar usuario > el numero en la URL
   - **Dolibarr login:** (Opcional) El nombre de usuario en Dolibarr, solo para referencia visual
4. Guarde

> **Alternativa:** Tambien puede crear mapeos desde la pagina de edicion de la instancia de Dolibarr (en la seccion inline "Dolibarr User Identities").

> **Nota:** Si un webhook llega con un usuario no mapeado, el sistema lo registra en el `WebhookLog` con un mensaje de advertencia pero no falla. No se pierde el evento.

### 3.2. Instalar el modulo en Dolibarr

#### Paso 3.2.1: Copiar los archivos del modulo

Copie el directorio `dolibarr_module/payroll_connect/` al directorio de modulos personalizados de su instalacion de Dolibarr:

```bash
cp -r dolibarr_module/payroll_connect/ /var/www/dolibarr/htdocs/custom/payroll_connect/
```

> La ruta puede variar segun su instalacion. Lo importante es que quede dentro de `htdocs/custom/`.

#### Paso 3.2.2: Activar el modulo

1. En Dolibarr, vaya a **Inicio > Configuracion > Modulos/Aplicaciones**
2. Busque **"Payroll Connect"** en la lista
3. Active el modulo haciendo click en el interruptor

Al activar el modulo se crea automaticamente la tabla de cola de reintentos.

#### Paso 3.2.3: Configurar el modulo

1. Una vez activado, vaya a **Configuracion > Modulos > Payroll Connect** (o haga click en el icono de engranaje junto al modulo)
2. En la pestana **"Settings"**:
   - **Webhook URL:** La URL del endpoint de su instalacion Django. Ejemplo:
     ```
     https://nomina.suempresa.com/api/webhook/dolibarr/
     ```
   - **API Secret:** La misma clave secreta que configuro en Django (paso 3.1.1)
3. Guarde la configuracion

#### Paso 3.2.4: Verificar el ID Profesional

1. En Dolibarr, vaya a **Configuracion > Empresa/Organizacion**
2. Verifique que el campo **"ID Profesional 1"** (CIF/RUC/NIT) tenga un valor
3. Este valor **debe coincidir exactamente** con el campo "Professional ID" de la instancia Django

#### Paso 3.2.5: Configurar el Cron Job de reintentos (recomendado)

El modulo incluye un cron job para reintentar webhooks fallidos automaticamente. Para activarlo:

1. En Dolibarr, vaya a **Inicio > Configuracion > Tareas Programadas (Cron)**
2. Debe ver una tarea llamada **"PayrollConnect - Process Retry Queue"**
3. Verifique que este activa

Si no aparece, desactive y vuelva a activar el modulo para regenerar la tarea.

### 3.3. Verificar la conexion

1. En Dolibarr, cree una proforma de prueba y validela
2. En Django, verifique en **"Webhook logs"** (admin) que llego un registro con `status = processed`
3. Verifique en **"Sales records"** que se creo un registro con status `proforma`

Si el webhook falla:
- Revise **"Webhook logs"** en Django para ver el error
- En Dolibarr, vaya a la pestana **"Retry Queue"** del modulo para ver eventos pendientes y reintentar manualmente

---

## 4. Configuracion de Bonos Escalonados (opcional)

La version 1.1 permite definir multiples niveles de bonificacion para un mismo KPI (en lugar de solo un monto fijo).

### Ejemplo: Bonos escalonados para Efectividad de Ventas

1. En el admin, vaya a **"KPIs"** y abra el KPI "Efectividad de Ventas"
2. En la seccion inferior **"KPI Bonus Tiers"**, agregue niveles:

| Umbral (%) | Monto del Bono | Descripcion |
|---|---|---|
| 35 | $100.00 | Nivel basico |
| 50 | $200.00 | Nivel intermedio |
| 75 | $400.00 | Nivel avanzado |
| 90 | $700.00 | Nivel excelencia |

3. Guarde

> **Nota sobre compatibilidad:** Si un KPI ya tiene un `BonusRule` (regla legacy), el sistema evalua ambos (la regla legacy y los niveles escalonados) y aplica el mayor. No es necesario eliminar reglas existentes.

---

## 5. Verificacion post-configuracion

Ejecute estas verificaciones para asegurarse de que todo esta funcionando:

### 5.1. Verificar que los calculos anteriores no cambiaron

1. En el sistema, vaya al calculo de salario de cualquier empleado para un mes anterior (ej: Enero 2026)
2. Compare los valores con los que tenia antes de la actualizacion
3. Los numeros deben ser **identicos** (base salary, work pay, overtime pay, performance bonus)

### 5.2. Verificar los perfiles

1. En el admin, vaya a **"Employees"**
2. Verifique que la columna **"Profile"** muestra el perfil asignado
3. Si hay empleados sin perfil, aparecera `-` (vacio) — esto es valido pero se recomienda asignar uno

### 5.3. Verificar la integracion Dolibarr (si aplica)

1. Revise **"Webhook logs"** — no debe haber registros con `status = error` recientes
2. Revise **"Sales records"** — las ventas deben aparecer con la fecha correcta del evento (no la fecha de recepcion del webhook)

---

## 6. Referencia de nuevos modelos

### Modelos en el Panel de Administracion

| Modelo | Seccion Admin | Descripcion |
|---|---|---|
| **Job profile** | Employees > Job profiles | Define roles y los KPIs que aplican a cada uno |
| **KPI Bonus Tier** | (inline en KPI) | Niveles escalonados de bonificacion |
| **Dolibarr instance** | Employees > Dolibarr instances | Instancias de Dolibarr conectadas |
| **Dolibarr user identity** | Employees > Dolibarr user identities | Mapeo usuario Dolibarr → empleado local |
| **Sales record** | Employees > Sales records | Registro de ventas sincronizadas (facturas, proformas, notas de credito) |
| **Product creation log** | Employees > Product creation logs | Registro de productos creados (para KPI de creacion) |
| **Webhook log** | Employees > Webhook logs | Auditoria de webhooks recibidos |

### Campos nuevos en modelos existentes

| Modelo | Campo | Tipo | Default | Descripcion |
|---|---|---|---|---|
| Employee | `profile` | FK (nullable) | `None` | Perfil de trabajo asignado |
| KPI | `internal_code` | SlugField (nullable) | `None` | Codigo interno para logica automatizada (ej: `SALES_EFFECTIVENESS`) |
| KPI | `min_volume_threshold` | Integer | `0` | Volumen minimo para activar el KPI (anti-fraude) |

### API Endpoints nuevos

| Endpoint | Metodo | Descripcion |
|---|---|---|
| `/api/webhook/dolibarr/` | POST | Recibe webhooks de Dolibarr (autenticacion HMAC) |

---

## 7. Preguntas frecuentes

### Si no configuro perfiles, se pierden datos?

**No.** Sin perfiles, el sistema evalua todos los KPIs para todos los empleados (comportamiento identico a antes de la actualizacion). Los datos historicos no se modifican.

### Puedo configurar perfiles gradualmente?

**Si.** Puede crear perfiles y asignarlos uno por uno. Los empleados sin perfil seguiran evaluandose contra todos los KPIs.

### Que pasa si un webhook de Dolibarr llega y el empleado no esta mapeado?

El evento se guarda en el `WebhookLog` con status `processed` y se registra una advertencia en los logs. No se crea un `SalesRecord` pero el evento no se pierde — puede mapear el empleado despues y reprocesar si es necesario.

### Que pasa con las Notas de Credito?

Las notas de credito (type=2 en Dolibarr) se registran como `SalesRecord` con status `credit_note` y **monto negativo**. Se descuentan automaticamente de las comisiones del mes.

### Puedo deshacer esta actualizacion?

Si, ejecutando `python3 manage.py migrate employees 0015` se revierte a la version anterior. Sin embargo, esto eliminara los datos nuevos (SalesRecords, WebhookLogs, etc.). Los datos originales (Employee, Salary, WorkLog, KPI, BonusRule, PerformanceRecord) no se afectan.

### Como se detecta el fraude por SKU duplicado?

Cuando se recibe un webhook de `PRODUCT_CREATE`, el sistema verifica si ya existe un producto con el mismo SKU (referencia) creado en el mismo mes y la misma instancia de Dolibarr. Si existe, el nuevo registro se marca como `is_suspect_duplicate = True` y no es elegible para el bono de creacion de productos.
