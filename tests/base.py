"""
Cimientos compartidos por la suite.

Crear roles, usuarios, parametros y piscinas en cada prueba seria lento y
repetitivo. `setUpTestData` los crea UNA vez por clase dentro de una
transaccion que se revierte al terminar.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.monitoreo.models import Dispositivo, Sensor, TipoParametro
from apps.piscinas.models import EtapaProduccion, Geomembrana
from apps.usuarios.models import Rol, Usuario

CLAVE_VALIDA = 'Piscicultura.2026'


class BaseSigmap(TestCase):
    """Datos minimos para que el sistema tenga sentido en una prueba."""

    @classmethod
    def setUpTestData(cls):
        # --- Roles. Los nombres deben coincidir EXACTAMENTE con permissions.py ---
        cls.rol_instructor = Rol.objects.create(nombre_rol='Instructor Lider')
        cls.rol_operario = Rol.objects.create(nombre_rol='Operario')
        cls.rol_aprendiz = Rol.objects.create(nombre_rol='Aprendiz')

        cls.instructor = Usuario.objects.create_user(
            'instructor@sena.edu.co', 'Instructor de Prueba',
            CLAVE_VALIDA, rol=cls.rol_instructor)
        cls.operario = Usuario.objects.create_user(
            'operario@sena.edu.co', 'Operario de Prueba',
            CLAVE_VALIDA, rol=cls.rol_operario)
        cls.aprendiz = Usuario.objects.create_user(
            'aprendiz@sena.edu.co', 'Aprendiz de Prueba',
            CLAVE_VALIDA, rol=cls.rol_aprendiz)

        # --- Etapa de produccion ---
        cls.etapa = EtapaProduccion.objects.create(
            nombre_etapa='Engorde', dias_duracion=90,
            densidad_peces_por_m2=Decimal('8.00'))

        # --- Parametros con sus tres rangos anidados ---
        cls.ph = TipoParametro.objects.create(
            nombre_parametro='pH', unidad_medida='pH',
            rango_normal_min=Decimal('6.5'), rango_normal_max=Decimal('8.5'),
            rango_riesgo_min=Decimal('6.0'), rango_riesgo_max=Decimal('9.0'),
            rango_critico_min=Decimal('0'), rango_critico_max=Decimal('14'))
        cls.oxigeno = TipoParametro.objects.create(
            nombre_parametro='Oxígeno disuelto', unidad_medida='mg/L',
            rango_normal_min=Decimal('5.0'), rango_normal_max=Decimal('9.0'),
            rango_riesgo_min=Decimal('4.0'), rango_riesgo_max=Decimal('11.0'),
            rango_critico_min=Decimal('0'), rango_critico_max=Decimal('20'))

        # --- Piscina operativa ---
        cls.piscina = Geomembrana.objects.create(
            nombre_piscina='Estanque de Prueba', codigo_identificacion='GEO-TEST',
            area_m2=Decimal('2500.00'), profundidad_promedio=Decimal('1.80'),
            capacidad_maxima_peces=12000, etapa_actual=cls.etapa,
            material='HDPE', espesor_mm=Decimal('1.50'),
            garantia_anios=8, vida_util_anios=10,
            fecha_instalacion=date(2024, 3, 15), estado='activo')

        # --- Sensores y nodo ESP32 ---
        cls.sensor_ph = Sensor.objects.create(
            nombre_sensor='Sonda pH', codigo_hardware='SEN-PH',
            geomembrana=cls.piscina, tipo_parametro=cls.ph,
            rango_medicion_min=Decimal('0'), rango_medicion_max=Decimal('14'),
            intervalo_lectura_segundos=300, estado='activo')
        cls.sensor_ox = Sensor.objects.create(
            nombre_sensor='Sonda O2', codigo_hardware='SEN-OX',
            geomembrana=cls.piscina, tipo_parametro=cls.oxigeno,
            rango_medicion_min=Decimal('0'), rango_medicion_max=Decimal('20'),
            intervalo_lectura_segundos=300, estado='activo')

        cls.dispositivo = Dispositivo.objects.create(
            codigo='ESP32-TEST', geomembrana=cls.piscina,
            token=Dispositivo.generar_token(), estado='activo')

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def cabecera_dispositivo(self, token=None):
        """
        Cabecera de autenticacion que envia el nodo ESP32.

        :param token: token alternativo para probar rechazos
        :return: dict con la cabecera HTTP
        """
        return {'HTTP_AUTHORIZATION': f'Device {token or self.dispositivo.token}'}

    def enviar_lectura(self, codigo_hardware, valor, token=None):
        """
        Simula el POST de un nodo ESP32 a la API de ingesta.

        :param codigo_hardware: codigo del sensor que reporta
        :param valor: medicion
        :param token: token alternativo para probar rechazos
        :return: HttpResponse
        """
        return self.client.post(
            '/api/v1/lecturas/',
            {'lecturas': [{'codigo_hardware': codigo_hardware, 'valor': valor}]},
            content_type='application/json',
            **self.cabecera_dispositivo(token),
        )
