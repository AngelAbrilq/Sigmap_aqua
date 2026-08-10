from django.apps import AppConfig


class PiscinasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'piscinas'

# apps/core/apps.py
class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
