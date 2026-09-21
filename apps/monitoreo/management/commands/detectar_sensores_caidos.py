"""
Detecta sensores activos que dejaron de transmitir y gestiona su alerta (RF001).

Uso:
    python manage.py detectar_sensores_caidos
    python manage.py detectar_sensores_caidos --margen 3 --gracia 120

Pensado para el Programador de tareas de Windows, cada 5-10 minutos.
Es idempotente: no duplica ni cierra dos veces.
"""
from django.core.management.base import BaseCommand

from apps.alertas.services import evaluar_sensores_caidos


class Command(BaseCommand):
    help = ('Abre alertas de los sensores que dejaron de transmitir y cierra '
            'las de los que volvieron a reportar.')

    def add_arguments(self, parser):
        parser.add_argument('--margen', type=int, default=3,
                            help='Intervalos de silencio tolerados antes de marcar caido (def. 3).')
        parser.add_argument('--gracia', type=int, default=120,
                            help='Colchon fijo en segundos (def. 120).')

    def handle(self, *args, **opciones):
        resultado = evaluar_sensores_caidos(
            margen_multiplos=opciones['margen'],
            gracia_segundos=opciones['gracia'],
        )
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nSensores activos revisados: {resultado["activos"]}\n'))
        self.stdout.write(self.style.ERROR(
            f'  Alertas abiertas: {resultado["abiertas"]}'))
        self.stdout.write(self.style.SUCCESS(
            f'  Alertas cerradas: {resultado["cerradas"]}'))
        if not resultado['abiertas'] and not resultado['cerradas']:
            self.stdout.write('  Sin cambios.')
