"""Pruebas de rangos efectivos por etapa de produccion (RF010 / RF012)."""
from decimal import Decimal as D

from django.test import SimpleTestCase

from apps.monitoreo.models import TipoParametro
from apps.monitoreo.rangos import clasificar_valor, rangos_efectivos
from apps.piscinas.models import EtapaProduccion


def tipo(nombre, n, r):
    """TipoParametro en memoria (no toca la BD)."""
    return TipoParametro(nombre_parametro=nombre, rango_normal_min=D(n[0]), rango_normal_max=D(n[1]),
                         rango_riesgo_min=D(r[0]), rango_riesgo_max=D(r[1]))


class RangosEfectivosTests(SimpleTestCase):
    def setUp(self):
        self.temperatura = tipo('Temperatura', ('24', '30'), ('20', '32'))
        self.oxigeno_legado = tipo('Oxigeno Disuelto', ('4', '8'), ('2.5', '4'))   # riesgo de un solo lado
        self.turbidez = tipo('Turbidez', ('0', '50'), ('0', '100'))
        self.alevin = EtapaProduccion(nombre_etapa='Alevin', rango_temperatura_min=D('25'),
                                      rango_temperatura_max=D('30'), rango_turbidez_min=D('0'),
                                      rango_turbidez_max=D('25'))

    def test_sin_etapa_usa_rango_general(self):
        # Arrange / Act
        rangos = rangos_efectivos(self.temperatura)
        # Assert
        self.assertEqual(rangos.fuente, 'general')
        self.assertEqual(clasificar_valor(D('27'), rangos), 'normal')
        self.assertEqual(clasificar_valor(D('31'), rangos), 'riesgo')
        self.assertEqual(clasificar_valor(D('33'), rangos), 'critico')

    def test_etapa_alevin_es_mas_estricta(self):
        rangos = rangos_efectivos(self.temperatura, self.alevin)
        self.assertEqual(rangos.fuente, 'Alevin')
        # 24.5 C es normal para engorde pero riesgo para alevinos
        self.assertEqual(self.temperatura.clasificar(D('24.5')), 'normal')
        self.assertEqual(clasificar_valor(D('24.5'), rangos), 'riesgo')
        # El margen de riesgo global (4 abajo, 2 arriba) se aplica alrededor del rango de la etapa
        self.assertEqual(rangos.riesgo_min, D('21'))
        self.assertEqual(rangos.riesgo_max, D('32'))

    def test_turbidez_alevin_agua_sucia(self):
        rangos = rangos_efectivos(self.turbidez, self.alevin)
        self.assertEqual(clasificar_valor(D('0'), rangos), 'normal')      # agua limpia no es critica
        self.assertEqual(clasificar_valor(D('40'), rangos), 'riesgo')
        self.assertEqual(clasificar_valor(D('200'), rangos), 'critico')

    def test_riesgo_legado_de_un_solo_lado_no_salta_a_critico(self):
        # Dato legado: riesgo cargado solo por debajo del normal (2.5-4.0)
        rangos = rangos_efectivos(self.oxigeno_legado)
        self.assertEqual(clasificar_valor(D('3'), rangos), 'riesgo')
        self.assertEqual(clasificar_valor(D('1'), rangos), 'critico')

    def test_etapa_sin_rango_del_parametro_cae_al_general(self):
        rangos = rangos_efectivos(self.oxigeno_legado, self.alevin)
        self.assertEqual(rangos.fuente, 'general')
