"""
Deja la base de datos lista para una demostracion de SIGMAP-AQUA.

Crea roles, grupos espejo, usuarios de prueba, dos geomembranas, sus
sensores, 24 horas de lecturas y un par de alertas activas.

Uso:  python manage.py preparar_demo
      python manage.py preparar_demo --limpiar
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.alertas.models import Alerta, HistorialEstadoAgua
from apps.monitoreo.models import Dispositivo, Lectura, Sensor, TipoParametro
from apps.piscinas.models import EtapaProduccion, Geomembrana
from apps.usuarios.models import Rol, Usuario
from apps.usuarios.permissions import ROL_APRENDIZ, ROL_INSTRUCTOR, ROL_OPERARIO

# (rol, email, nombre_completo, password)
USUARIOS_DEMO = [
    (ROL_INSTRUCTOR, 'instructor@sigmap.com', 'Ana Instructora', 'Instructor2026*'),
    (ROL_APRENDIZ,   'aprendiz@sigmap.com',   'Luis Aprendiz',   'Aprendiz2026*'),
    (ROL_OPERARIO,   'operario@sigmap.com',   'Carlos Operario', 'Operario2026*'),
]

# nombre, unidad, (normal_min, normal_max), (critico_min, critico_max)
PARAMETROS_DEMO = [
    ('Temperatura',       'C',    (24, 30),    (20, 34)),
    ('pH',                'pH',   (6.5, 8.5),  (5.5, 9.5)),
    ('Oxigeno disuelto',  'mg/L', (5.0, 9.0),  (3.0, 12.0)),
    ('Turbidez',          'NTU',  (0, 25),     (0, 45)),
]

LECTURAS_POR_SENSOR = 24   # una por hora en las ultimas 24 h


class Command(BaseCommand):
    help = 'Prepara usuarios, geomembranas, sensores, lecturas y alertas de demostracion.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Borra lecturas, alertas, sensores y geomembranas de demo antes de cargar.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['limpiar']:
            self._limpiar()

        usuarios = self._crear_usuarios()
        etapa = self._crear_etapa()
        parametros = self._crear_parametros()
        geomembranas = self._crear_geomembranas(etapa)
        sensores = self._crear_sensores(geomembranas, parametros)
        self._crear_lecturas(sensores)
        self._crear_alertas(sensores, usuarios[ROL_OPERARIO])
        self._crear_historial(geomembranas)

        self._resumen()

    # ------------------------------------------------------------------ #
    # Pasos
    # ------------------------------------------------------------------ #
    def _limpiar(self):
        self.stdout.write('Limpiando datos de demostracion...')
        Alerta.objects.all().delete()
        HistorialEstadoAgua.objects.all().delete()
        Lectura.objects.all().delete()
        Sensor.objects.all().delete()
        Dispositivo.objects.all().delete()
        Geomembrana.objects.all().delete()

    def _crear_usuarios(self):
        """Crea o actualiza los tres usuarios de prueba. :return: dict rol -> Usuario"""
        creados = {}
        for nombre_rol, email, nombre, password in USUARIOS_DEMO:
            rol, _ = Rol.objects.get_or_create(
                nombre_rol=nombre_rol,
                defaults={'descripcion': nombre_rol, 'permisos': {}, 'estado': 'activo'},
            )
            grupo, _ = Group.objects.get_or_create(name=nombre_rol)

            usuario, _ = Usuario.objects.get_or_create(
                email=email,
                defaults={'nombre_completo': nombre, 'rol': rol, 'estado': 'activo'},
            )
            usuario.nombre_completo = nombre
            usuario.rol = rol
            usuario.estado = 'activo'
            usuario.is_staff = False
            usuario.is_superuser = False
            usuario.set_password(password)
            usuario.save()
            usuario.groups.set([grupo])
            creados[nombre_rol] = usuario

        self.stdout.write(self.style.SUCCESS('  Usuarios: %d' % len(creados)))
        return creados

    def _crear_etapa(self):
        etapa, _ = EtapaProduccion.objects.get_or_create(
            nombre_etapa='Engorde',
            defaults={
                'descripcion': 'Etapa de engorde de tilapia roja.',
                'dias_duracion': 120,
                'rango_temperatura_min': Decimal('24.00'),
                'rango_temperatura_max': Decimal('30.00'),
                'rango_ph_min': Decimal('6.50'),
                'rango_ph_max': Decimal('8.50'),
                'rango_oxigeno_min': Decimal('5.00'),
                'rango_oxigeno_max': Decimal('9.00'),
            },
        )
        return etapa

    def _crear_parametros(self):
        """:return: dict nombre -> TipoParametro"""
        parametros = {}
        for nombre, unidad, (n_min, n_max), (c_min, c_max) in PARAMETROS_DEMO:
            tipo, _ = TipoParametro.objects.get_or_create(
                nombre_parametro=nombre,
                defaults={
                    'unidad_medida': unidad,
                    'rango_normal_min': Decimal(str(n_min)),
                    'rango_normal_max': Decimal(str(n_max)),
                    'rango_critico_min': Decimal(str(c_min)),
                    'rango_critico_max': Decimal(str(c_max)),
                    'importancia': 'alta',
                },
            )
            parametros[nombre] = tipo
        self.stdout.write(self.style.SUCCESS('  Parametros: %d' % len(parametros)))
        return parametros

    def _crear_geomembranas(self, etapa):
        """:return: lista de Geomembrana"""
        definicion = [
            ('Piscina Norte', 'GEO-001', 'Sector norte de la granja', 1500),
            ('Piscina Sur',   'GEO-002', 'Sector sur de la granja',   1200),
        ]
        geomembranas = []
        for nombre, codigo, ubicacion, capacidad in definicion:
            geo, _ = Geomembrana.objects.get_or_create(
                codigo_identificacion=codigo,
                defaults={
                    'nombre_piscina': nombre,
                    'descripcion': 'Geomembrana de demostracion.',
                    'ubicacion': ubicacion,
                    'profundidad_promedio': Decimal('1.80'),
                    'capacidad_maxima_peces': capacidad,
                    'etapa_actual': etapa,
                    'material': 'HDPE',
                    'espesor_mm': Decimal('1.00'),
                    'proveedor': 'Geosistemas del Huila',
                    'garantia_anios': 5,
                    'vida_util_anios': 12,
                    'fecha_instalacion': timezone.localdate() - timedelta(days=400),
                    'fecha_ultimo_mantenimiento': timezone.localdate() - timedelta(days=25),
                    'apta_para_produccion': True,
                    'estado': 'activo',
                },
            )
            geomembranas.append(geo)

            Dispositivo.objects.get_or_create(
                codigo='ESP32-%s' % codigo,
                defaults={
                    'descripcion': 'Nodo ESP32 de %s' % nombre,
                    'geomembrana': geo,
                    'token': 'demo-token-%s' % codigo.lower(),
                    'firmware_version': '1.0.0',
                    'ultima_conexion': timezone.now(),
                    'estado': 'activo',
                },
            )

        self.stdout.write(self.style.SUCCESS('  Geomembranas: %d' % len(geomembranas)))
        return geomembranas

    def _crear_sensores(self, geomembranas, parametros):
        """:return: lista de Sensor"""
        sensores = []
        for geo in geomembranas:
            for nombre_param, tipo in parametros.items():
                codigo = 'SEN-%s-%s' % (geo.codigo_identificacion.split('-')[1],
                                        nombre_param[:3].upper())
                sensor, _ = Sensor.objects.get_or_create(
                    codigo_hardware=codigo,
                    defaults={
                        'nombre_sensor': '%s - %s' % (nombre_param, geo.nombre_piscina),
                        'geomembrana': geo,
                        'tipo_parametro': tipo,
                        'ubicacion_exacta': 'Centro de la piscina, 50 cm de profundidad',
                        'modelo_sensor': 'DS18B20' if nombre_param == 'Temperatura' else 'Generico',
                        'marca_sensor': 'Atlas Scientific',
                        'rango_medicion_min': tipo.rango_critico_min,
                        'rango_medicion_max': tipo.rango_critico_max,
                        'intervalo_lectura_segundos': 300,
                        'firmware_version': '1.0.0',
                        'estado': 'activo',
                    },
                )
                sensores.append(sensor)
        self.stdout.write(self.style.SUCCESS('  Sensores: %d' % len(sensores)))
        return sensores

    def _crear_lecturas(self, sensores):
        """Genera 24 lecturas por sensor (una por hora) dentro de rango."""
        if Lectura.objects.exists():
            self.stdout.write('  Lecturas: ya existian, no se regeneraron')
            return

        ahora = timezone.now()
        nuevas = []
        for sensor in sensores:
            tipo = sensor.tipo_parametro
            minimo = float(tipo.rango_normal_min or 0)
            maximo = float(tipo.rango_normal_max or 10)
            for i in range(LECTURAS_POR_SENSOR):
                valor = round(random.uniform(minimo * 1.02, maximo * 0.98), 4)
                nuevas.append(Lectura(
                    sensor=sensor,
                    geomembrana=sensor.geomembrana,
                    tipo_parametro=tipo,
                    valor_medida=Decimal(str(valor)),
                    estado_lectura='normal',
                    dentro_rango=True,
                    timestamp_lectura=ahora - timedelta(hours=LECTURAS_POR_SENSOR - i),
                    secuencia=i + 1,
                    validada=True,
                ))
        Lectura.objects.bulk_create(nuevas)
        self.stdout.write(self.style.SUCCESS('  Lecturas: %d' % len(nuevas)))

    def _crear_alertas(self, sensores, usuario_operario):
        """Crea dos alertas activas visibles en el dashboard."""
        if Alerta.objects.exists():
            self.stdout.write('  Alertas: ya existian, no se regeneraron')
            return

        sensor_oxigeno = next(
            (s for s in sensores if s.tipo_parametro.nombre_parametro == 'Oxigeno disuelto'), None)
        sensor_ph = next(
            (s for s in sensores if s.tipo_parametro.nombre_parametro == 'pH'), None)

        plantillas = [
            (sensor_oxigeno, 'critico', 'critica', Decimal('3.8000'),
             'Oxigeno disuelto por debajo del rango seguro. Revisar aireacion de inmediato.'),
            (sensor_ph, 'riesgo', 'media', Decimal('8.9000'),
             'pH por encima del rango normal. Verificar encalado y recambio de agua.'),
        ]

        creadas = 0
        for sensor, tipo_alerta, severidad, valor, mensaje in plantillas:
            if sensor is None:
                continue
            lectura = Lectura.objects.create(
                sensor=sensor,
                geomembrana=sensor.geomembrana,
                tipo_parametro=sensor.tipo_parametro,
                valor_medida=valor,
                estado_lectura=tipo_alerta,
                dentro_rango=False,
                timestamp_lectura=timezone.now() - timedelta(minutes=15),
                validada=True,
            )
            Alerta.objects.create(
                geomembrana=sensor.geomembrana,
                sensor=sensor,
                tipo_parametro=sensor.tipo_parametro,
                lectura=lectura,
                tipo_alerta=tipo_alerta,
                severidad=severidad,
                valor_que_disparo=valor,
                mensaje_alerta=mensaje,
                estado='activa',
            )
            creadas += 1

        self.stdout.write(self.style.SUCCESS('  Alertas: %d' % creadas))

    def _crear_historial(self, geomembranas):
        if HistorialEstadoAgua.objects.exists():
            return
        for geo in geomembranas:
            HistorialEstadoAgua.objects.create(
                geomembrana=geo,
                estado_general='optimo',
                apta_produccion=True,
                observaciones='Evaluacion automatica de demostracion.',
            )

    def _resumen(self):
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Credenciales de demostracion'))
        self.stdout.write('-' * 62)
        for nombre_rol, email, nombre, password in USUARIOS_DEMO:
            self.stdout.write('  %-16s %-26s %s' % (nombre_rol, email, password))
        self.stdout.write('-' * 62)
        self.stdout.write(self.style.SUCCESS('Base de datos lista. Entra por /auth/login/'))
