# settings.py
import os
from pathlib import Path
import socket
import socks
import ssl  # <--- ¡AÑADE ESTA LÍNEA AQUÍ ARRIBA!
from decouple import config
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# CONFIGURACIÓN DE SEGURIDAD Y ENTORNO (¡ESTO VA PRIMERO!)
# ==============================================================================
# Lee la clave secreta y el modo DEBUG desde las variables de entorno o el archivo .env
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# ==============================================================================
# CONFIGURACIÓN DEL PROXY (SOLO SE ACTIVA EN LOCAL)
# ==============================================================================
if DEBUG:
    # El proxy SOCKS solo es necesario para 'runserver'
    PROXY_HOST = 'proxy.unicauca.edu.co'
    PROXY_PORT = 3128
    socks.set_default_proxy(socks.HTTP, PROXY_HOST, PROXY_PORT)
    socket.socket = socks.socksocket

# --- ¡SOLUCIÓN! ---
# Ponemos el parche SSL AFUERA del 'if DEBUG'.
# Esto fuerza a AMBAS terminales (runserver y process_tasks)
# a ignorar la verificación SSL del proxy.
ssl._create_default_https_context = ssl._create_unverified_context
# --- FIN DE LA SOLUCIÓN ---
# ==============================================================================
# CONFIGURACIÓN GENERAL DE DJANGO
# ==============================================================================
ALLOWED_HOSTS = ['*'] # Permite que Render acceda

INSTALLED_APPS = [
    'nucleo.apps.NucleoConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # Apps de terceros
    'crispy_forms',
    'crispy_bootstrap5',
    'background_task',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Posición correcta para servir estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gestion_pqrs.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gestion_pqrs.wsgi.application'

# ==============================================================================
# BASE DE DATOS (Configuración flexible para local y Render)
# ==============================================================================
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL')
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==============================================================================
# INTERNACIONALIZACIÓN
# ==============================================================================
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# ==============================================================================
# ARCHIVOS ESTÁTICOS Y MULTIMEDIA (Configuración para Whitenoise)
# ==============================================================================
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==============================================================================
# CONFIGURACIONES DE APPS Y OTRAS
# ==============================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
LOGIN_URL = 'admin:login'
LOGIN_REDIRECT_URL = '/'
SITE_ID = 1

# ==============================================================================
# CONFIGURACIÓN DE CORREO (SMTP y IMAP)
# ==============================================================================
# --- A. CONFIGURACIÓN DE ENVÍO (SMTP) USANDO BREVO ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST')                   # Lee 'smtp-relay.brevo.com' de .env
EMAIL_PORT = config('EMAIL_PORT', cast=int)         # Lee '587' de .env
EMAIL_HOST_USER = config('EMAIL_HOST_USER')         # Lee '99d9c...' de .env
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD') # Lee la API Key de .env
EMAIL_USE_TLS = True

# ¡IMPORTANTE! Esta es la dirección "De:" que verán los usuarios.
# Como ya verificaste 'notificacionesvra' en Brevo, esto SÍ funcionará.
DEFAULT_FROM_EMAIL = '"Notificaciones PQRS VRA" <notificaciones.vra.pqrs@gmail.com>'
# --- B. CONFIGURACIÓN DE LECTURA (IMAP) USANDO GOOGLE ---
# (Esta parte se queda igual que como la tenías)
EMAIL_IMAP_HOST = 'imap.gmail.com'
EMAIL_IMAP_USER = 'notificacionesvra@unicauca.edu.co'
EMAIL_IMAP_PASSWORD = config('EMAIL_IMAP_PASSWORD') # Lee la contraseña de Google de .env
# ==============================================================================
# CONFIGURACIÓN DE GOOGLE SHEETS (Flexible para local y Render)
# ==============================================================================
if config('GOOGLE_SHEETS_CREDENTIALS_FILE', default=None):
    # En Render, las credenciales están en una variable de entorno.
    # Las escribimos en un archivo temporal para que el resto del código funcione.
    creds_content = config('GOOGLE_SHEETS_CREDENTIALS_FILE')
    creds_path = os.path.join(BASE_DIR, 'render_gcreds.json')
    with open(creds_path, 'w') as f:
        f.write(creds_content)
    GOOGLE_SHEETS_CREDENTIALS_FILE = creds_path
else:
    # En local, simplemente apuntamos al archivo .json existente.
    GOOGLE_SHEETS_CREDENTIALS_FILE = os.path.join(BASE_DIR, 'pqrs-473715-b714e5cd838b.json')

GOOGLE_SHEETS_SPREADSHEET_ID = '1QadVa2F37vtd6YS5Jpd4iXDivJRSoC9MMQLJSU3tDow'