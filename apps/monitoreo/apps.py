from django.apps import AppConfig


class MonitoreoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoreo'

# apps/core/apps.py
class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'