"""
SmartStock Django Settings
==========================
AI-Powered Inventory Management System
"""

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from decouple import config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ──────────────────────────────────────────────
IS_VERCEL = bool(os.environ.get('VERCEL'))
DEBUG = config('DEBUG', default=not IS_VERCEL, cast=bool)
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-change-this-in-production-xyz123' if DEBUG else '',
)
if not DEBUG and (
    not SECRET_KEY
    or SECRET_KEY.startswith('django-insecure-')
    or SECRET_KEY.startswith('replace-with-')
):
    raise ImproperlyConfigured('Set a unique production SECRET_KEY.')

ALLOWED_HOSTS = [
    host.strip()
    for host in config('ALLOWED_HOSTS', default='127.0.0.1,localhost').split(',')
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip().rstrip('/')
    for origin in config('CSRF_TRUSTED_ORIGINS', default='').split(',')
    if origin.strip()
]
for vercel_host_variable in ('VERCEL_URL', 'VERCEL_PROJECT_PRODUCTION_URL'):
    vercel_host = os.environ.get(vercel_host_variable, '').strip()
    if vercel_host:
        parsed_host = urlparse(
            vercel_host if '://' in vercel_host else f'https://{vercel_host}'
        ).hostname
        if parsed_host:
            ALLOWED_HOSTS.append(parsed_host)
            CSRF_TRUSTED_ORIGINS.append(f'https://{parsed_host}')
ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))
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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
if not DEBUG:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

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
# Use SQLite by default so the project runs locally without extra DB setup.
# Use DATABASE_URL for hosted PostgreSQL deployments.
USE_SQLITE = config('USE_SQLITE', default=True, cast=bool)
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    database_url = urlparse(DATABASE_URL)
    if database_url.scheme not in ('postgres', 'postgresql') or not database_url.hostname:
        raise ImproperlyConfigured('DATABASE_URL must be a PostgreSQL connection URL.')
    database_name = unquote(database_url.path.lstrip('/'))
    if not database_name:
        raise ImproperlyConfigured('DATABASE_URL must include a database name.')
    database_options = {}
    sslmode = parse_qs(database_url.query).get('sslmode', [])
    if sslmode:
        database_options['sslmode'] = sslmode[-1]
    elif IS_VERCEL:
        database_options['sslmode'] = 'require'
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': database_name,
            'USER': unquote(database_url.username or ''),
            'PASSWORD': unquote(database_url.password or ''),
            'HOST': database_url.hostname,
            'PORT': database_url.port or '',
            'OPTIONS': database_options,
            'CONN_MAX_AGE': 0,
        }
    }
elif IS_VERCEL:
    raise ImproperlyConfigured(
        'Configure a persistent PostgreSQL DATABASE_URL in the Vercel project settings.'
    )
elif USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Option A: PostgreSQL (Recommended)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='smartstock'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='password'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

# Option B: MySQL (Uncomment to use)
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': config('DB_NAME', default='smartstock'),
#         'USER': config('DB_USER', default='root'),
#         'PASSWORD': config('DB_PASSWORD', default=''),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='3306'),
#     }
# }

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
if DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Crispy Forms ────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ── Service Configuration ─────────────────────────────────────
AI_SERVICE_URL = config('AI_SERVICE_URL', default='http://127.0.0.1:8001').rstrip('/')
AI_SERVICE_TOKEN = config('AI_SERVICE_TOKEN', default='')
INVENTORY_SERVICE_TOKEN = config('INVENTORY_SERVICE_TOKEN', default='')

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
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'smartstock.log',
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
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
if DEBUG:
    logs_dir = BASE_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)
    LOGGING['handlers']['file'] = {
        'class': 'logging.FileHandler',
        'filename': logs_dir / 'smartstock.log',
        'formatter': 'verbose',
    }
    LOGGING['loggers']['ai_assistant']['handlers'].append('file')
