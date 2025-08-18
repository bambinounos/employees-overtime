# employees-overtime
It calculates employees salary and overtime, it based on calendar selecction

Solución para el error de traducción (gettext)
El error que encontré al intentar compilar las traducciones (CommandError: Can't find msgfmt...) se debe a que la herramienta gettext, que es necesaria para manejar los archivos de traducción, no está instalada en el entorno de desarrollo.
La solución es instalar gettext en tu servidor Ubuntu. Puedes hacerlo con el siguiente comando:
sudo apt install gettext -y

Una vez instalado, el comando python3 manage.py compilemessages debería funcionar correctamente y las traducciones al español se mostrarán en la aplicación.
Pasos de instalación en Ubuntu 24.04 Server
Aquí tienes una guía paso a paso para instalar y configurar la aplicación en tu servidor:
Actualizar el sistema:
sudo apt update && sudo apt upgrade -y


Instalar dependencias del sistema (Python, pip, venv, PostgreSQL y gettext):
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib gettext -y


Configurar la base de datos PostgreSQL: Inicia sesión en PostgreSQL y crea la base de datos y el usuario para la aplicación.
sudo -u postgres psql


Dentro de la consola de psql, ejecuta los siguientes comandos. Reemplaza 'tu_contraseña' con una contraseña segura.
CREATE DATABASE salary_management;
CREATE USER salary_manager WITH PASSWORD 'tu_contraseña';
ALTER ROLE salary_manager SET client_encoding TO 'utf8';
ALTER ROLE salary_manager SET default_transaction_isolation TO 'read committed';
ALTER ROLE salary_manager SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE salary_management TO salary_manager;
\q


Clonar el repositorio: Descarga el código de la aplicación desde el repositorio.
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_DIRECTORIO>


Configurar el entorno de Python: Crea un entorno virtual e instala las dependencias de Python.
python3 -m venv venv
source venv/bin/activate
pip install django django-year-calendar djangorestframework psycopg2-binary


(Nota: psycopg2-binary es necesario para que Django se conecte con PostgreSQL).
Configurar la conexión a la base de datos en Django: Edita el archivo salary_management/settings.py y modifica la sección DATABASES para que se vea así. No olvides usar la contraseña que creaste en el paso 3.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'salary_management',
        'USER': 'salary_manager',
        'PASSWORD': 'tu_contraseña',
        'HOST': 'localhost',
        'PORT': '',
    }
}


Aplicar las migraciones de la base de datos:
python3 manage.py migrate


Compilar las traducciones: Ahora que gettext está instalado, puedes compilar los archivos de traducción.
python3 manage.py compilemessages


Crear un superusuario para el panel de administración:
python3 manage.py createsuperuser


Sigue las instrucciones para crear tu cuenta de administrador.
Ejecutar el servidor de desarrollo: Para probar la aplicación, puedes usar el servidor de desarrollo de Django.
python3 manage.py runserver 0.0.0.0:8000


Ahora deberías poder acceder a la aplicación desde tu navegador en http://<IP_DE_TU_SERVIDOR>:8000.
Para un entorno de producción, te recomiendo usar un servidor de aplicaciones como Gunicorn y un proxy inverso como Nginx, pero estos pasos te darán una instalación funcional para empezar.
