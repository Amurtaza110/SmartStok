"""
SmartStock Django Settings
==========================
AI-Powered Inventory Management System
Single-service, self-contained architecture compatible with local development and Vercel.
"""

import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Environment & Deployment Detection ────────────────────
IS_VERCEL = bool(os.environ.get('VERCEL'))
DEBUG = config('DEBUG', default=not IS_VERCEL, cast=bool)

# ── Security ──────────────────────────────────────────────
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-smartstock-ai-inventory-system-2026',
)
if not SECRET_KEY:
    SECRET_KEY = 'django-insecure-smartstock-ai-inventory-system-2026'

ALLOWED_HOSTS = [
    host.strip()
    for host in config('ALLOWED_HOSTS', default='127.0.0.1,localhost').split(',')
    if host.strip()
]
for default_host in ('127.0.0.1', 'localhost', '.vercel.app'):
    if default_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(default_host)

# Dynamic Vercel Host Detection
for vercel_var in ('VERCEL_URL', 'VERCEL_PROJECT_PRODUCTION_URL'):
    v_host = os.environ.get(vercel_var, '').strip()
    if v_host:
        parsed_h = urlparse(v_host if '://' in v_host else f'https://{v_host}').hostname or v_host
        if parsed_h and parsed_h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(parsed_h)

ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = [
    origin.strip().rstrip('/')
    for origin in config('CSRF_TRUSTED_ORIGINS', default='').split(',')
    if origin.strip()
]
for vercel_origin in ('https://*.vercel.app', 'http://127.0.0.1:8000', 'http://localhost:8000'):
    if vercel_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(vercel_origin)

for vercel_var in ('VERCEL_URL', 'VERCEL_PROJECT_PRODUCTION_URL'):
    v_host = os.environ.get(vercel_var, '').strip()
    if v_host:
        origin_url = v_host if v_host.startswith('http') else f'https://{v_host}'
        if origin_url not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin_url)

CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ── Installed Apps ─────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Third-party
    'crispy_forms',
    'crispy_bootstrap5',

    # Project Apps
    'inventory',
    'ai_assistant',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'smartstock.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'smartstock.wsgi.application'

# ── Database ───────────────────────────────────────────────
# Fully self-contained SQLite configuration.
# On Vercel serverless functions, the root filesystem is read-only.
# We copy bundled db.sqlite3 to /tmp/db.sqlite3 so it is writable.
if IS_VERCEL:
    tmp_db = Path('/tmp/db.sqlite3')
    bundled_db = BASE_DIR / 'db.sqlite3'
    if not tmp_db.exists() and bundled_db.exists():
        try:
            shutil.copyfile(bundled_db, tmp_db)
        except Exception:
            pass
    active_db = str(tmp_db) if tmp_db.exists() else str(bundled_db)
    SQLITE_PATH = config('SQLITE_PATH', default=active_db)
else:
    SQLITE_PATH = config('SQLITE_PATH', default=str(BASE_DIR / 'db.sqlite3'))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': SQLITE_PATH,
    }
}

# ── Authentication ─────────────────────────────────────────
AUTH_USER_MODEL = 'inventory.CustomUser'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalization ────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

# ── Static & Media Files ────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = Path('/tmp/media') if IS_VERCEL else (BASE_DIR / 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Crispy Forms ────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ── AI & Service Configuration ──────────────────────────────
OLLAMA_BASE_URL = config('OLLAMA_BASE_URL', default='http://localhost:11434').rstrip('/')
OLLAMA_MODEL = config('OLLAMA_MODEL', default='llama3.2')
OLLAMA_TIMEOUT = config('OLLAMA_TIMEOUT', default=60, cast=int)
INVENTORY_SERVICE_TOKEN = config('INVENTORY_SERVICE_TOKEN', default='smartstock-service-token')

# ── Logging ──────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'ai_assistant': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

if not IS_VERCEL and DEBUG:
    try:
        logs_dir = BASE_DIR / 'logs'
        logs_dir.mkdir(exist_ok=True)
        LOGGING['handlers']['file'] = {
            'class': 'logging.FileHandler',
            'filename': logs_dir / 'smartstock.log',
            'formatter': 'verbose',
        }
        LOGGING['loggers']['ai_assistant']['handlers'].append('file')
    except Exception:
        pass
