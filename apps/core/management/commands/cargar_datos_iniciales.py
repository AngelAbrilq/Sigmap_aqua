import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.usuarios.models import Rol, Usuario
from apps.piscinas.models import EtapaProduccion, Geomembrana
from apps.monitoreo.models import TipoParametro, Sensor, Dispositivo

PASSWORD_DESARROLLO = 'sigmap2026'


class Command(BaseCommand):
    help = 'Carga los datos iniciales de SIGMAP-AQUA desde el fixture JSON.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Elimina los registros existentes antes de cargar.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        ruta = Path(__file__).resolve().parents[2] / 'fixtures' / 'datos_iniciales.json'

        if not ruta.exists():
            self.stderr.write(self.style.ERROR(f'No se encontró el fixture: {ruta}'))
            return

        with open(ruta, encoding='utf-8') as f:
            datos = json.load(f)

        if options['limpiar']:
            self._limpiar()

        self._cargar_roles(datos['roles'])
        self._cargar_tipos_parametros(datos['tipos_parametros'])
        self._cargar_etapas(datos['etapas_produccion'])
        self._cargar_geomembranas(datos['geomembranas'])
        self._cargar_dispositivos(datos['sensores'])
        self._cargar_sensores(datos['sensores'])
        self._cargar_usuarios(datos['usuarios'])

        self.stdout.write(self.style.SUCCESS('\nDatos iniciales cargados correctamente.'))
        self.stdout.write(
            self.style.WARNING(
                f'Contraseña de desarrollo para todos los usuarios: {PASSWORD_DESARROLLO}'
            )
        )

    def _limpiar(self):
        self.stdout.write('Eliminando registros existentes...')
        Sensor.objects.all().delete()
        Dispositivo.objects.all().delete()
        Usuario.objects.filter(is_superuser=False).delete()
        Geomembrana.objects.all().delete()
        EtapaProduccion.objects.all().delete()
        TipoParametro.objects.all().delete()
        Rol.objects.all().delete()

    def _cargar_roles(self, registros):
        for r in registros:
            Rol.objects.update_or_create(
                id=r['id'],
                defaults={
                    'nombre_rol': r['nombre_rol'],
                    'descripcion': r['descripcion'],
                    'permisos': r['permisos'],
                },
            )
        self.stdout.write(f'  Roles: {len(registros)}')

    def _cargar_tipos_parametros(self, registros):
        for r in registros:
            TipoParametro.objects.update_or_create(
                id=r['id'],
                defaults={k: v for k, v in r.items() if k != 'id'},
            )
        self.stdout.write(f'  Tipos de parámetro: {len(registros)}')

    def _cargar_etapas(self, registros):
        for r in registros:
            EtapaProduccion.objects.update_or_create(
                id=r['id'],
                defaults={k: v for k, v in r.items() if k != 'id'},
            )
        self.stdout.write(f'  Etapas de producción: {len(registros)}')

    def _cargar_geomembranas(self, registros):
        for r in registros:
            datos = {k: v for k, v in r.items() if k not in ('id', 'id_etapa_actual')}
            datos['etapa_actual_id'] = r['id_etapa_actual']
            Geomembrana.objects.update_or_create(id=r['id'], defaults=datos)
        self.stdout.write(f'  Geomembranas: {len(registros)}')

    def _cargar_dispositivos(self, sensores):
        """Crea un nodo ESP32 por cada piscina que tenga sensores."""
        piscinas_con_sensores = sorted({s['id_geomembrana'] for s in sensores})

        for indice, id_piscina in enumerate(piscinas_con_sensores, start=1):
            geomembrana = Geomembrana.objects.get(id=id_piscina)
            Dispositivo.objects.update_or_create(
                codigo=f'NODO-{indice:03d}',
                defaults={
                    'descripcion': f'Nodo de monitoreo - {geomembrana.nombre_piscina}',
                    'geomembrana': geomembrana,
                    'token': Dispositivo.generar_token(),
                    'firmware_version': '1.0',
                },
            )
        self.stdout.write(f'  Dispositivos: {len(piscinas_con_sensores)}')

    def _cargar_sensores(self, registros):
        for r in registros:
            datos = {
                k: v for k, v in r.items()
                if k not in ('id', 'id_geomembrana', 'id_tipo_parametro')
            }
            datos['geomembrana_id'] = r['id_geomembrana']
            datos['tipo_parametro_id'] = r['id_tipo_parametro']
            Sensor.objects.update_or_create(id=r['id'], defaults=datos)
        self.stdout.write(f'  Sensores: {len(registros)}')

    def _cargar_usuarios(self, registros):
        for r in registros:
            usuario, creado = Usuario.objects.update_or_create(
                email=r['email'],
                defaults={
                    'nombre_completo': r['nombre_completo'],
                    'rol_id': r['id_rol'],
                    'documento_identidad': r['documento_identidad'],
                    'numero_celular': r['numero_celular'],
                    'numero_whatsapp': r['numero_whatsapp'],
                    'estado': r['estado'],
                },
            )
            if creado:
                usuario.set_password(PASSWORD_DESARROLLO)
                usuario.save(update_fields=['password'])
        self.stdout.write(f'  Usuarios: {len(registros)}')