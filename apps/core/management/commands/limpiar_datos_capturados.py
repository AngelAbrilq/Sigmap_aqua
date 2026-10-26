"""
Deja la base de datos "en limpio" para volver a capturar desde el ESP32.

Borra SOLO los datos capturados o derivados de las lecturas:
    lecturas de sensores, alertas y sus notificaciones, historial del estado
    del agua, análisis de IA y sus predicciones, reportes y comparaciones de
    periodos.

NO toca la configuración del sistema:
    piscinas (geomembranas), etapas de producción, sensores, dispositivos
    ESP32 (ni su token), tipos de parámetro con sus rangos, usuarios y roles.

Uso:
    python manage.py limpiar_datos_capturados              # solo muestra qué borraría
    python manage.py limpiar_datos_capturados --confirmar  # borra de verdad
    python manage.py limpiar_datos_capturados --confirmar --incluir-eventos

Todo se hace en una transacción: si algo falla, no se borra nada.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.alertas.models import Alerta, HistorialEstadoAgua, Notificacion
from apps.auditoria.models import EventoSistema
from apps.ia.models import AnalisisIA, Prediccion
from apps.monitoreo.models import Dispositivo, Lectura, Sensor
from apps.piscinas.models import Geomembrana
from apps.reportes.models import ComparacionDatos, Reporte

# Orden de borrado: primero lo que referencia, después lo referenciado
# (Alerta -> Lectura y Prediccion -> AnalisisIA usan on_delete=PROTECT).
TABLAS_A_LIMPIAR = (
    ('Notificaciones de alertas', Notificacion),
    ('Alertas', Alerta),
    ('Historial del estado del agua', HistorialEstadoAgua),
    ('Predicciones de IA', Prediccion),
    ('Análisis de IA', AnalisisIA),
    ('Reportes', Reporte),
    ('Comparaciones de periodos', ComparacionDatos),
    ('Lecturas de sensores', Lectura),
)

TABLAS_PROTEGIDAS = (
    ('Piscinas (geomembranas)', Geomembrana),
    ('Sensores', Sensor),
    ('Dispositivos ESP32', Dispositivo),
)


class Command(BaseCommand):
    help = ('Borra lecturas, alertas, análisis de IA, reportes y comparaciones '
            'para volver a capturar en limpio. Conserva piscinas, sensores, '
            'dispositivos, parámetros y usuarios.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar', action='store_true',
            help='Ejecuta el borrado. Sin esta opción solo se muestra el conteo.')
        parser.add_argument(
            '--incluir-eventos', action='store_true',
            help='También borra el registro de eventos del sistema (auditoría).')

    def handle(self, *args, **opciones):
        confirmar = opciones['confirmar']
        incluir_eventos = opciones['incluir_eventos']

        tablas = list(TABLAS_A_LIMPIAR)
        if incluir_eventos:
            tablas.append(('Eventos del sistema (auditoría)', EventoSistema))

        self._mostrar_plan(tablas)

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\nModo simulación: no se borró nada.\n'
                'Para borrar de verdad ejecuta:\n'
                '  python manage.py limpiar_datos_capturados --confirmar\n'))
            return

        borrados = self._borrar(tablas)
        self._registrar_evento(borrados, incluir_eventos)

        total = sum(borrados.values())
        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {total} registro(s) borrados. '
            'Prende el ESP32 y los datos se capturarán desde cero.\n'))

    def _mostrar_plan(self, tablas):
        """Imprime qué se borra y qué se conserva."""
        self.stdout.write(self.style.MIGRATE_HEADING('\nSe BORRARÁN:'))
        for nombre, modelo in tablas:
            self.stdout.write(f'  - {nombre}: {modelo.objects.count()}')

        self.stdout.write(self.style.MIGRATE_HEADING('\nSe CONSERVAN:'))
        for nombre, modelo in TABLAS_PROTEGIDAS:
            self.stdout.write(f'  + {nombre}: {modelo.objects.count()}')
        self.stdout.write('  + Etapas, tipos de parámetro y sus rangos, usuarios y roles')

    @transaction.atomic
    def _borrar(self, tablas):
        """
        Borra las tablas en orden y reinicia la última conexión de los ESP32.

        :param tablas: lista de (nombre, modelo)
        :return: dict nombre -> registros borrados
        """
        borrados = {}
        for nombre, modelo in tablas:
            cantidad, _ = modelo.objects.all().delete()
            borrados[nombre] = cantidad
            self.stdout.write(f'  Borrado {nombre}: {cantidad}')

        # La última conexión se deriva de las lecturas: sin lecturas, queda vacía
        # hasta que el ESP32 vuelva a transmitir.
        Dispositivo.objects.update(ultima_conexion=None)
        return borrados

    def _registrar_evento(self, borrados, incluir_eventos):
        """Deja constancia en auditoría de que se limpió la base."""
        from apps.auditoria.services import registrar_evento

        registrar_evento(
            EventoSistema.Tipo.SISTEMA,
            'Limpieza de datos capturados para reiniciar la captura desde el ESP32',
            nivel='advertencia',
            datos={'borrados': borrados, 'incluyo_eventos': incluir_eventos},
        )
