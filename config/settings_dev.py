# settings_dev.py — Solo para desarrollo visual sin BD
# No modifica settings.py del proyecto real

from .settings import *

# Reemplaza MySQL por SQLite para no necesitar BD
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_dev.sqlite3',
    }
}

# Auth
LOGIN_URL           = '/auth/login/'
LOGIN_REDIRECT_URL  = '/admin/'
LOGOUT_REDIRECT_URL = '/auth/login/'
