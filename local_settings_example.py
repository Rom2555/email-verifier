"""
Локальные настройки для разработки.
Скопируйте этот файл в local_settings.py и заполните свои значения.
"""

from .settings import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'your-secret-key-here'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Настройки Redis (опционально для разработки)
# REDIS_URL = 'redis://127.0.0.1:6379/1'
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': REDIS_URL,
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#         }
#     }
# }

# YooKassa (опционально для тестирования)
# YOOKASSA_SHOP_ID = 'your_shop_id'
# YOOKASSA_SECRET_KEY = 'your_secret_key'
