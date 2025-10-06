from decouple import config
import dj_database_url
# settings.py
import os # Asegúrate que esta línea esté al principio del archivo

from pathlib import Path
import socket
import socks

# --- CONFIGURACIÓN DEL PROXY DE UNICAUCA ---
if DEBUG:
    PROXY_HOST = 'proxy.unicauca.edu.co'
    PROXY_PORT = 3128
    socks.set_default_proxy(socks.HTTP, PROXY_HOST, PROXY_PORT)
    socket.socket = socks.socksocket
# --- FIN DE LA CONFIGURACIÓN DEL PROXY ---

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = ['*'] # Permitimos que Render acceda

#ALLOWED_HOSTS = ['192.168.42.175']

# Application definition
INSTALLED_APPS = [
    'nucleo.apps.NucleoConfig',  # <-- ¡ESTE ES EL CAMBIO!
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # <-- ¡AÑADE ESTA LÍNEA!
    # Apps de terceros
    'crispy_forms',
    'crispy_bootstrap5',
    'background_task', # <-- Añade esta línea
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # <-- MUEVE ESTA LÍNEA AQUÍ
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

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL')
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- ¡AQUÍ ESTÁ EL BLOQUE DE CORREO QUE FALTABA! ---
# Usando las credenciales que ya sabes que funcionan.
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'notificacionesvra@unicauca.edu.co'
EMAIL_HOST_PASSWORD = 'jjnj yapg qgnl uybc'
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
LOGIN_URL = 'admin:login'
LOGIN_REDIRECT_URL = '/'
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
SITE_ID = 1

# --- ¡AÑADE ESTE NUEVO BLOQUE! ---
# --- CONFIGURACIÓN PARA LEER EL BUZÓN DE CORREO (IMAP) ---
EMAIL_IMAP_HOST = 'imap.gmail.com'  # Servidor para leer correos de Gmail
EMAIL_IMAP_USER = 'notificacionesvra@unicauca.edu.co'
EMAIL_IMAP_PASSWORD = 'jjnj yapg qgnl uybc' # La misma contraseña de aplicación

# Configuración para la integración con Google Sheets
GOOGLE_SHEETS_CREDENTIALS_FILE = os.path.join(BASE_DIR, 'pqrs-473715-b714e5cd838b.json')
# Ve a la URL de tu hoja de cálculo y copia el ID largo que está en el medio
GOOGLE_SHEETS_SPREADSHEET_ID = '1QadVa2F37vtd6YS5Jpd4iXDivJRSoC9MMQLJSU3tDow'