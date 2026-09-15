"""
Registra un nodo fisico (ESP32) y genera su token de autenticacion.

Uso:
    python manage.py crear_dispositivo ESP32-P1 --piscina GEO-01
    python manage.py crear_dispositivo ESP32-P1 --piscina GEO-01 --rotar-token

El token se imprime una sola vez. Copialo al secrets.h del firmware.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.monitoreo.models import Dispositivo
from apps.piscinas.models import Geomembrana


class Command(BaseCommand):
    help = 'Crea un dispositivo ESP32 y muestra su token de autenticacion.'

    def add_arguments(self, parser):
        parser.add_argument('codigo', type=str, help='Codigo unico del nodo, ej. ESP32-P1')
        parser.add_argument(
            '--piscina', required=True, type=str,
            help='codigo_identificacion de la Geomembrana asociada',
        )
        parser.add_argument('--descripcion', type=str, default='')
        parser.add_argument(
            '--rotar-token', action='store_true',
            help='Si el dispositivo ya existe, genera un token nuevo y revoca el anterior.',
        )

    def handle(self, *args, **opciones):
        codigo = opciones['codigo']
        codigo_piscina = opciones['piscina']

        try:
            geomembrana = Geomembrana.objects.get(codigo_identificacion=codigo_piscina)
        except Geomembrana.DoesNotExist:
            disponibles = ', '.join(
                Geomembrana.objects.values_list('codigo_identificacion', flat=True)
            ) or '(ninguna registrada)'
            raise CommandError(
                f'No existe la piscina "{codigo_piscina}". Disponibles: {disponibles}'
            )

        dispositivo = Dispositivo.objects.filter(codigo=codigo).first()

        if dispositivo and not opciones['rotar_token']:
            raise CommandError(
                f'El dispositivo "{codigo}" ya existe. Usa --rotar-token para '
                f'generar credenciales nuevas (el token anterior deja de servir).'
            )

        token = Dispositivo.generar_token()

        if dispositivo:
            dispositivo.token = token
            dispositivo.geomembrana = geomembrana
            dispositivo.estado = 'activo'
            dispositivo.save(update_fields=['token', 'geomembrana', 'estado'])
            accion = 'Token rotado'
        else:
            dispositivo = Dispositivo.objects.create(
                codigo=codigo,
                descripcion=opciones['descripcion'],
                geomembrana=geomembrana,
                token=token,
                estado='activo',
            )
            accion = 'Dispositivo creado'

        self.stdout.write(self.style.SUCCESS(f'\n{accion}: {dispositivo.codigo}'))
        self.stdout.write(f'Piscina : {geomembrana}')
        self.stdout.write(self.style.WARNING(f'TOKEN   : {token}'))
        self.stdout.write(
            '\nPega este token en firmware/bioaqua_handshake/secrets.h '
            'como DEVICE_TOKEN.\nNo se vuelve a mostrar.\n'
        )
