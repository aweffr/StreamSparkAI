from pathlib import Path
from environ import Env
import os

BASE_DIR = Path(__file__).resolve().parent.parent

env = Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, 'secret'),
    AWS_S3_ENDPOINT_URL=(str, 'endpoint_url'),
    AWS_STORAGE_BUCKET_NAME=(str, 'bucket_name'),
    AWS_ACCESS_KEY_ID=(str, 'access_key'),
    AWS_SECRET_ACCESS_KEY=(str, 'secret_key'),
    ALIBABA_DASHSCOPE_API_KEY=(str, 'api_key'),
    OPENAI_API_KEY=(str, ''),
    OPENAI_API_BASE=(str, 'https://api.openai.com/v1'),
    DEFAULT_OPENAI_MODEL=(str, 'gemini-2.5-flash-preview-04-17'),
    ALIBABA_LLM_MODEL=(str, 'qwen-max'),
    DEFAULT_LLM_PROVIDER=(str, 'openai'),
    DATABASE_URL=(str, 'sqlite:////' + str(BASE_DIR / 'db.sqlite3')),
    SERVER_ORIGIN=(str, 'http://localhost:8000'),
)

env.read_env()

SECRET_KEY = env('SECRET_KEY')

SERVER_ORIGIN = env('SERVER_ORIGIN')

DEBUG = env('DEBUG')

ALLOWED_HOSTS = [
    '*'
]

# CSRF Trusted Origins Configuration
if DEBUG:
    # Generate localhost and 127.0.0.1 URLs with various ports using a loop
    CSRF_TRUSTED_ORIGINS = []
    hosts = ['localhost', '127.0.0.1']
    protocols = ['http', 'https']
    ports = [None, '3000', '5000', '8000', '8080', '8888', '9000']
    
    for host in hosts:
        for protocol in protocols:
            for port in ports:
                if port:
                    CSRF_TRUSTED_ORIGINS.append(f"{protocol}://{host}:{port}")
                else:
                    CSRF_TRUSTED_ORIGINS.append(f"{protocol}://{host}")
else:
    # In production mode, add the server origin and its subdomains
    from urllib.parse import urlparse
    parsed_url = urlparse(SERVER_ORIGIN)
    scheme = parsed_url.scheme
    netloc = parsed_url.netloc
    
    # Handle domain with or without port
    if ':' in netloc:
        domain = netloc.split(':')[0]
        port = netloc.split(':')[1]
        CSRF_TRUSTED_ORIGINS = [
            SERVER_ORIGIN,  # The exact server origin
            f"{scheme}://*.{domain}:{port}",  # All subdomains with specific port
            f"{scheme}://*.{domain}"  # All subdomains without port
        ]
    else:
        domain = netloc
        CSRF_TRUSTED_ORIGINS = [
            SERVER_ORIGIN,  # The exact server origin
            f"{scheme}://*.{domain}"  # All subdomains
        ]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # Add this line
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'conf.urls'

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

WSGI_APPLICATION = 'conf.wsgi.application'

DATABASES = {
    'default': env.db('DATABASE_URL'),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# Add Locale paths for translation files
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

LANGUAGES = [
    ('en', 'English'),
    ('zh-hans', '简体中文'),
]

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# config django storages
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": env('AWS_S3_ENDPOINT_URL'),
            "access_key": env('AWS_ACCESS_KEY_ID'),
            "secret_key": env('AWS_SECRET_ACCESS_KEY'),
            "bucket_name": env('AWS_STORAGE_BUCKET_NAME'),
            "default_acl": "private",
            "addressing_style": "virtual",
            "querystring_expire": 7200,
            "file_overwrite": False,
            "signature_version": "s3",
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

ALIBABA_DASHSCOPE_API_KEY = env('ALIBABA_DASHSCOPE_API_KEY')

# LLM settings
OPENAI_API_KEY = env('OPENAI_API_KEY')
OPENAI_API_BASE = env('OPENAI_API_BASE')
DEFAULT_OPENAI_MODEL = env('DEFAULT_OPENAI_MODEL')

ALIBABA_LLM_MODEL = env('ALIBABA_LLM_MODEL')

DEFAULT_LLM_PROVIDER = env('DEFAULT_LLM_PROVIDER')

# Logging Configuration

# Directory for log files in production
LOG_DIR = BASE_DIR / 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)
    
TMP_DIR = BASE_DIR / 'tmp'
if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR, exist_ok=True)

# Determine log level based on DEBUG setting
CORE_LOG_LEVEL = 'DEBUG' if DEBUG else 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} [{levelname}] {name}:{lineno} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'core.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'core': {
            'handlers': ['console', 'file'] if not DEBUG else ['console'],
            'level': CORE_LOG_LEVEL,
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

