"""
Plantilla de local_settings.py para producción.

Copiar como salary_management/local_settings.py en el servidor (está
gitignored) y completar los valores. Todo lo definido aquí sobreescribe
settings.py.

    cp salary_management/local_settings.example.py salary_management/local_settings.py
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Seguridad ---------------------------------------------------------------
DEBUG = False

# Generar una nueva:  python3 -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY = "CAMBIAR-POR-UNA-CLAVE-SECRETA-REAL"

ALLOWED_HOSTS = ["salarios.example.com"]
CSRF_TRUSTED_ORIGINS = ["https://salarios.example.com"]

# Detrás de nginx con TLS:
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# --- Base de datos -----------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "salary_management",
        "USER": "salary_manager",
        "PASSWORD": "CAMBIAR",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# --- Email (SMTP real; el default del repo imprime a consola) ----------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.example.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "notificaciones@example.com"
EMAIL_HOST_PASSWORD = "CAMBIAR"
DEFAULT_FROM_EMAIL = "Salarios <notificaciones@example.com>"

# URL pública del sistema (para links en emails enviados desde cron)
SITE_BASE_URL = "https://salarios.example.com"
