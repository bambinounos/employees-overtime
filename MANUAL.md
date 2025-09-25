# Manual de Usuario y Configuración

Bienvenido al manual de usuario y configuración del sistema de gestión de empleados. Esta guía le proporcionará instrucciones detalladas sobre cómo configurar el entorno de la aplicación y cómo utilizar sus funcionalidades principales.

## 1. Configuración del Sistema

Esta sección describe los pasos para instalar y configurar la aplicación en un servidor Ubuntu 24.04.

### 1.1. Prerrequisitos

Asegúrese de tener acceso a un servidor con **Ubuntu 24.04** y privilegios de `sudo`.

### 1.2. Pasos de Instalación

Siga esta guía para poner en marcha la aplicación.

#### a. Actualizar el Sistema
Mantenga su sistema actualizado para asegurar la compatibilidad y seguridad.
```bash
sudo apt update && sudo apt upgrade -y
```

#### b. Instalar Dependencias del Sistema
Instale Python, las herramientas para entornos virtuales, PostgreSQL (la base de datos) y gettext (para la gestión de traducciones).
```bash
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib gettext -y
```

#### c. Configurar la Base de Datos PostgreSQL
Es necesario crear una base de datos y un usuario dedicado para la aplicación.

1.  **Acceda a la consola de PostgreSQL:**
    ```bash
    sudo -u postgres psql
    ```

2.  **Ejecute los siguientes comandos SQL.** Reemplace `'tu_contraseña'` con una contraseña segura de su elección.
    ```sql
    CREATE DATABASE salary_management;
    CREATE USER salary_manager WITH PASSWORD 'tu_contraseña';
    ALTER ROLE salary_manager SET client_encoding TO 'utf8';
    ALTER ROLE salary_manager SET default_transaction_isolation TO 'read committed';
    ALTER ROLE salary_manager SET timezone TO 'UTC';
    GRANT ALL PRIVILEGES ON DATABASE salary_management TO salary_manager;
    \q
    ```

#### d. Clonar el Repositorio
Descargue el código fuente de la aplicación.
```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_DIRECTORIO>
```
*Nota: Reemplace `<URL_DEL_REPOSITORIO>` y `<NOMBRE_DEL_DIRECTORIO>` con los valores correctos.*

#### e. Configurar el Entorno Virtual de Python
Cree un entorno virtual para aislar las dependencias de la aplicación.

1.  **Crear y activar el entorno virtual:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  **Instalar las librerías de Python:**
    ```bash
    pip install django django-year-calendar djangorestframework psycopg2-binary
    ```
    *`psycopg2-binary` es el conector que permite a Django comunicarse con PostgreSQL.*

#### f. Conectar Django a la Base de Datos
Edite el archivo de configuración de Django para que apunte a la base de datos que creó.

1.  **Abra el archivo `salary_management/settings.py`**.
2.  **Modifique la sección `DATABASES`** con los datos de su base de datos. Use la contraseña que definió en el paso `c`.
    ```python
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'salary_management',
            'USER': 'salary_manager',
            'PASSWORD': 'tu_contraseña', # ¡No olvide cambiar esto!
            'HOST': 'localhost',
            'PORT': '',
        }
    }
    ```

#### g. Aplicar Migraciones
Este comando crea las tablas necesarias en la base de datos según los modelos de la aplicación.
```bash
python3 manage.py migrate
```

#### h. Compilar Traducciones
Para que la interfaz de usuario se muestre en español, compile los archivos de idioma.
```bash
python3 manage.py compilemessages
```

#### i. Crear un Superusuario
Cree una cuenta de administrador para acceder al panel de administración de Django.
```bash
python3 manage.py createsuperuser
```
Siga las instrucciones en pantalla para definir el nombre de usuario, correo y contraseña.

#### j. Ejecutar el Servidor
Para pruebas, puede usar el servidor de desarrollo de Django.
```bash
python3 manage.py runserver 0.0.0.0:8000
```
Ahora puede acceder a la aplicación en su navegador visitando `http://<IP_DE_SU_SERVIDOR>:8000`.

**Nota sobre Producción:** Para un despliegue en producción, se recomienda utilizar un servidor de aplicaciones como Gunicorn junto con un proxy inverso como Nginx para mayor seguridad y rendimiento.

## 2. Uso de la Aplicación

Esta sección detalla las funcionalidades clave del sistema y cómo interactuar con ellas. La mayoría de las configuraciones iniciales (como la creación de KPIs) se realizan a través del **Panel de Administración de Django**.

### 2.1. Acceso al Panel de Administración

Para administrar los datos maestros del sistema, acceda al panel de administración en `http://<IP_DE_SU_SERVIDOR>:8000/admin` y utilice las credenciales del superusuario creado durante la instalación.

### 2.2. Gestión de Empleados

Los empleados son el eje central del sistema.

*   **Crear un Empleado:**
    1.  En el panel de administración, vaya a la sección "Users" y cree un nuevo usuario para el empleado. Esto le da acceso al sistema.
    2.  Luego, vaya a la sección "Employees" y cree un nuevo empleado, asociándolo con el usuario recién creado.
    3.  Complete los datos como nombre, correo y fecha de contratación.
*   **Asignar Salario Base:**
    1.  Dentro del panel de administración, busque la sección "Salaries".
    2.  Cree un nuevo registro de salario, asigne el empleado y defina su `sueldo base mensual` y la `fecha de efectividad`.

### 2.3. Sistema de Tareas (Tablero Kanban)

El sistema incluye un tablero de tareas similar a Trello para organizar el trabajo.

*   **Acceso:** El tablero de tareas es accesible desde la interfaz principal de la aplicación para los usuarios que han iniciado sesión.
*   **Componentes:**
    *   **Tablero (Board):** Cada empleado tiene su propio tablero.
    *   **Listas (Lists):** Columnas que representan estados del flujo de trabajo (p. ej., "Pendiente", "En Progreso", "Hecho"). Se crean automáticamente para cada nuevo empleado.
    *   **Tareas (Tasks):** Tarjetas que representan unidades de trabajo. Se pueden arrastrar y soltar entre listas.
*   **Funcionalidades de una Tarea:**
    *   **Asignación:** Cada tarea está asignada a un empleado.
    *   **KPI Asociado:** Una tarea puede estar vinculada a un KPI para que su finalización contribuya al cálculo del desempeño.
    *   **Checklists:** Puede añadir listas de subtareas dentro de una tarea.
    *   **Comentarios:** Permite la comunicación entre el administrador y el empleado en el contexto de una tarea.

### 2.4. Indicadores de Desempeño (KPIs) y Bonificaciones

El sistema calcula bonificaciones basadas en el cumplimiento de KPIs.

*   **Configuración (vía Panel de Administración):**
    1.  **Crear KPIs:** Vaya a "KPIs" y defina los indicadores de desempeño.
        *   **Nombre:** "Productividad General", "Calidad Administrativa".
        *   **Tipo de Medición:**
            *   `Percentage`: Para métricas como "porcentaje de tareas completadas".
            *   `Count (Less Than)`: Para métricas donde un número menor es mejor (p. ej., "menos de 3 errores").
            *   `Count (Greater Than)`: Para métricas donde un número mayor es mejor (p. ej., "más de 10 ofertas enviadas").
        *   **Valor Objetivo:** El umbral que se debe alcanzar (p. ej., `95` para un 95%).
    2.  **Crear Reglas de Bonificación (Bonus Rules):** Vaya a "Bonus Rules" para vincular un KPI con un incentivo monetario.
        *   Asocie una regla a un KPI y defina el `monto del bono` que se otorga si se cumple el objetivo.

*   **Registro de Datos para KPIs:**
    *   **Automático:** Para KPIs basados en tareas (p. ej., "Productividad"), el sistema calcula el desempeño automáticamente al final del mes.
    *   **Manual:** Para KPIs como "Calidad" o "Gestión Comercial", un administrador puede registrar eventos a través de "Manual Kpi Entries" en el panel de administración. Por ejemplo, registrar un "error administrativo" en una fecha específica.

### 2.5. Cálculo de Salarios

El salario final de un empleado se calcula mensualmente y se compone de tres partes:

1.  **Salario Base Proporcional:** Calculado en función de las horas trabajadas registradas en el sistema (`Work Logs`).
2.  **Horas Extra:** Las horas extra se registran en los `Work Logs` y se pagan a una tasa de 1.5 veces la hora normal.
3.  **Bonificaciones por Desempeño:** La suma de todos los bonos ganados por cumplir los objetivos de los KPIs durante el mes.

El detalle del salario se puede consultar en la sección de informes de la aplicación.

#### 2.5.1. Configuración de Horas Base y Horas Extra
Para que el cálculo de las horas extra sea preciso, el sistema necesita saber cuál es la jornada laboral estándar. Esta configuración se gestiona desde la página de **Configuración de la Empresa**.

1.  **Acceda a la página:** Navegue a la sección de "Configuración de la Empresa" desde el menú principal.
2.  **Ajuste los parámetros:**
    *   **Frecuencia de Cálculo:** Defina si las horas base se contarán de forma `Mensual`, `Semanal` o `Diaria`.
    *   **Horas Base:** Ingrese el número total de horas que corresponden a la frecuencia seleccionada.
        *   **Ejemplo para base mensual:** Si la jornada es de 8 horas diarias de lunes a viernes, las horas base mensuales serían aproximadamente `160`.
        *   **Ejemplo para base semanal:** Si la jornada es de 40 horas semanales, elija `Semanal` e ingrese `40`.

El sistema utilizará estos valores para calcular la tarifa por hora de cada empleado y, a partir de ahí, determinar el valor de las horas extra.

### 2.6. Informes

La aplicación ofrece vistas para consultar información clave:

*   **Lista de Empleados:** Un resumen de todos los empleados.
*   **Informe de Desempeño:** Muestra el rendimiento de un empleado frente a sus KPIs para un mes y año seleccionados.
*   **Cálculo de Salario:** Proporciona un desglose detallado del salario de un empleado para un mes y año.

### 2.7. Servidor de Calendarios (CalDAV)

El sistema incluye un servidor WebDAV/CalDAV para exponer los calendarios de los empleados. Esto permite a los usuarios suscribirse a sus calendarios de trabajo utilizando clientes de calendario compatibles (como Thunderbird, Outlook o calendarios de móviles).

*   **Cómo Iniciar el Servidor:**
    1.  Asegúrese de tener el entorno virtual activado (`source venv/bin/activate`).
    2.  Ejecute el siguiente script desde el directorio raíz del proyecto:
        ```bash
        python3 run_wsgidav.py
        ```
    3.  El servidor se iniciará en el puerto `8080`. Verá un mensaje como: `WsgiDAV server running on http://0.0.0.0:8080/`.

*   **Cómo Usarlo:**
    1.  Abra su cliente de calendario preferido.
    2.  Busque la opción para añadir un "Calendario en red" o "Calendario CalDAV".
    3.  Cuando se le solicite la URL, introduzca la dirección del servidor seguida de su nombre de usuario. Por ejemplo, si su nombre de usuario es `jdoe` y está accediendo desde el mismo servidor, la URL sería:
        ```
        http://localhost:8080/jdoe
        ```
    4.  El servidor está configurado para **acceso anónimo**, por lo que no necesitará introducir un nombre de usuario o contraseña en su cliente de calendario. Su cliente podrá ver y suscribirse a los eventos del calendario del empleado especificado en la URL.

## 3. Actualización de la Aplicación

Para actualizar una instalación existente a la última versión, siga estos pasos.

### 3.1. Prerrequisitos

*   Asegúrese de tener acceso al servidor donde está instalada la aplicación.
*   Confirme que tiene permisos para ejecutar comandos como `git` y `python3`.

### 3.2. Pasos para Actualizar

1.  **Navegue al Directorio del Proyecto:**
    Abra una terminal y vaya al directorio donde clonó el repositorio.
    ```bash
    cd <NOMBRE_DEL_DIRECTORIO>
    ```

2.  **Active el Entorno Virtual:**
    Es crucial activar el entorno virtual para usar las dependencias correctas.
    ```bash
    source venv/bin/activate
    ```

3.  **Descargue los Últimos Cambios:**
    Obtenga la versión más reciente del código desde el repositorio de `git`.
    ```bash
    git pull origin main  # O la rama que corresponda (ej. master)
    ```

4.  **Instale o Actualice las Dependencias:**
    Si se han añadido nuevas librerías, instálelas. Es una buena práctica ejecutar siempre este comando.
    ```bash
    pip install -r requirements.txt
    ```
    *Nota: Si el proyecto no cuenta con un archivo `requirements.txt`, deberá instalar manualmente cualquier nueva dependencia que se haya añadido.*

5.  **Aplique las Migraciones de la Base de Datos:**
    Este es un paso crítico para actualizar el esquema de la base de datos con los últimos cambios.
    ```bash
    python3 manage.py migrate
    ```

6.  **Recopile los Archivos Estáticos (si aplica):**
    Si se han realizado cambios en los archivos CSS, JavaScript o imágenes, es importante recopilarlos.
    ```bash
    python3 manage.py collectstatic
    ```

7.  **Reinicie el Servidor de Aplicaciones:**
    Si está usando un servidor como Gunicorn o Apache, reinícielo para que los cambios surtan efecto.
    ```bash
    # Ejemplo para Gunicorn con systemd
    sudo systemctl restart gunicorn
    ```
    Si está usando el servidor de desarrollo de Django, simplemente deténgalo (`Ctrl+C`) y vuelva a iniciarlo.

## 4. Política de Copias de Seguridad

Mantener copias de seguridad regulares es fundamental para proteger los datos de la aplicación contra fallos de hardware, corrupción de datos o errores humanos. Esta sección describe cómo utilizar el script de backup proporcionado.

### 4.1. ¿Qué se Incluye en la Copia de Seguridad?

El proceso de backup está diseñado para salvaguardar los datos más críticos de la aplicación:

1.  **Base de Datos Completa:** Un volcado completo de la base de datos `salary_management` de PostgreSQL.
2.  **Archivos de Configuración:**
    *   `salary_management/settings.py`: Contiene la configuración de Django, incluida la conexión a la base de datos.
    *   `wsgidav.conf`: Contiene la configuración del servidor de calendarios CalDAV.

### 4.2. El Script `backup.sh`

En la raíz del proyecto se encuentra el script `backup.sh`, que automatiza todo el proceso.

*   **Ubicación de las Copias:** Los backups se guardan en el directorio `backups/` en la raíz del proyecto.
*   **Formato del Archivo:** Cada copia es un archivo `.tar.gz` con un nombre que incluye la fecha y hora, por ejemplo: `backup_2024-09-25_10-30-00.tar.gz`.
*   **Retención:** El script elimina automáticamente las copias de seguridad con más de 7 días de antigüedad para evitar el consumo excesivo de espacio en disco.

### 4.3. Ejecutar una Copia de Seguridad Manualmente

Para crear una copia de seguridad en cualquier momento, siga estos pasos:

1.  **Navegue al Directorio del Proyecto:**
    ```bash
    cd <NOMBRE_DEL_DIRECTORIO>
    ```

2.  **Asegúrese de que el Script sea Ejecutable:**
    La primera vez, debe darle permisos de ejecución.
    ```bash
    chmod +x backup.sh
    ```

3.  **Ejecute el Script:**
    ```bash
    ./backup.sh
    ```

    El script mostrará el progreso en la terminal y le notificará cuando el proceso haya finalizado.

    *Nota sobre la contraseña:* El comando `pg_dump` dentro del script puede solicitarle la contraseña del usuario `salary_manager` de la base de datos. Para automatizar esto, se recomienda configurar un archivo `~/.pgpass`.

### 4.4. Restaurar desde una Copia de Seguridad

Restaurar una copia de seguridad implica dos pasos: restaurar la base de datos y restaurar los archivos de configuración.

#### a. Extraer la Copia de Seguridad

Primero, descomprima el archivo de backup que desea restaurar.

```bash
# Navegue al directorio de backups
cd backups/

# Extraiga el contenido (reemplace con el nombre de su archivo)
tar -xzf backup_2024-09-25_10-30-00.tar.gz
```
Esto creará una carpeta `backups/` dentro del directorio actual, que contiene el archivo `db_dump.sql` y los archivos de configuración.

#### b. Restaurar la Base de Datos

Utilice el comando `pg_restore` para cargar el volcado en su base de datos.

```bash
# El -c (o --clean) elimina los objetos de la base de datos antes de recrearlos
pg_restore -U salary_manager -d salary_management -c -v backups/db_dump.sql
```
*Le pedirá la contraseña del usuario `salary_manager`.*

#### c. Restaurar los Archivos de Configuración

Copie los archivos de configuración extraídos a sus ubicaciones originales.

```bash
# Desde el directorio raíz del proyecto
cp backups/salary_management/settings.py salary_management/settings.py
cp backups/wsgidav.conf wsgidav.conf
```

### 4.5. Automatizar las Copias de Seguridad con Cron

Para garantizar que las copias de seguridad se realicen de forma regular y desatendida, puede usar `cron`, el programador de tareas de Linux.

1.  **Abra el Editor de Cron:**
    ```bash
    crontab -e
    ```
    Si es la primera vez, es posible que le pida que elija un editor de texto. Seleccione el que prefiera (por ejemplo, `nano`).

2.  **Añada una Nueva Tarea Programada:**
    Añada la siguiente línea al final del archivo. Este ejemplo ejecuta el script de backup todos los días a las 2:30 AM.

    ```crontab
    # m h  dom mon dow   command
    30 2 * * * /ruta/completa/a/su/proyecto/backup.sh >> /ruta/completa/a/su/proyecto/backups/cron.log 2>&1
    ```

    **Importante:**
    *   Reemplace `/ruta/completa/a/su/proyecto/` con la ruta absoluta al directorio raíz de su aplicación (ej: `/home/ubuntu/employees_overtime`).
    *   `>> backups/cron.log 2>&1` redirige la salida del script (tanto la estándar como los errores) a un archivo de registro, lo cual es útil para la depuración.

3.  **Guarde y Cierre el Archivo:**
    *   En `nano`, presione `Ctrl+X`, luego `Y` para confirmar, y `Enter`.

Con esto, el sistema creará automáticamente una copia de seguridad cada día a la hora especificada.
