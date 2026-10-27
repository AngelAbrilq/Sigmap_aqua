from django.apps import AppConfig


class DemoConfig(AppConfig):
    """Acceso de demostración por QR para la sustentación del proyecto."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.demo'
    verbose_name = 'Demostración por QR'
