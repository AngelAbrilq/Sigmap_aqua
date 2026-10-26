"""
Oxigeno disuelto simulado en el tablero en vivo (solo pruebas).

Debe acompanar a los sensores reales sin contaminar la base de datos.
"""
from datetime import datetime, timezone as tz
from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from apps.monitoreo.models import Lectura, Sensor
from apps.monitoreo.simulacion import saturacion_oxigeno, valor_simulado

from .base import BaseSigmap


class CalculoTest(SimpleTestCase):
    """Valores fisicamente creibles y estables."""

    def test_saturacion_a_25_grados(self):
        self.assertAlmostEqual(saturacion_oxigeno(25), 8.2, delta=0.15)

    def test_agua_mas_caliente_tiene_menos_oxigeno(self):
        self.assertGreater(saturacion_oxigeno(20), saturacion_oxigeno(30))

    def test_mismo_instante_mismo_valor(self):
        momento = datetime(2026, 10, 21, 11, 0, tzinfo=tz.utc)
        self.assertEqual(valor_simulado(momento, 24), valor_simulado(momento, 24))

    def test_el_patron_se_repite_cada_10_minutos(self):
        inicio = datetime(2026, 10, 21, 11, 0, 7, tzinfo=tz.utc)
        despues = datetime(2026, 10, 21, 11, 10, 7, tzinfo=tz.utc)
        self.assertEqual(valor_simulado(inicio, 24), valor_simulado(despues, 24))


class TableroTest(BaseSigmap):
    """La tarjeta simulada aparece junto a las reales."""

    def setUp(self):
        # Sin sensor de oxigeno funcionando, como en la piscina real.
        Sensor.objects.filter(pk=self.sensor_ox.pk).update(estado='inactivo')
        for valor in (7.1, 7.2, 7.3):
            self.enviar_lectura('SEN-PH', valor)
        self.client.force_login(self.instructor)

    def _sensores(self):
        respuesta = self.client.get(f'/monitoreo/api/{self.piscina.pk}/estado/')
        return {s['codigo']: s for s in respuesta.json()['data']['sensores']}

    def test_aparece_el_oxigeno_marcado_como_simulado(self):
        oxigeno = self._sensores()['SEN-OX']
        self.assertTrue(oxigeno['simulado'])
        self.assertEqual(oxigeno['unidad'], 'mg/L')
        self.assertIn(oxigeno['estado'], ('normal', 'riesgo', 'critico'))

    def test_sigue_el_ritmo_del_sensor_real(self):
        sensores = self._sensores()
        self.assertEqual(len(sensores['SEN-OX']['serie']), len(sensores['SEN-PH']['serie']))
        self.assertEqual(sensores['SEN-OX']['momento'], sensores['SEN-PH']['momento'])

    def test_los_sensores_reales_no_se_marcan(self):
        self.assertFalse(self._sensores()['SEN-PH']['simulado'])

    def test_no_se_guarda_en_la_base_de_datos(self):
        self._sensores()
        self.assertFalse(Lectura.objects.filter(sensor=self.sensor_ox).exists())

    def test_la_pagina_muestra_la_etiqueta(self):
        respuesta = self.client.get(f'/monitoreo/?piscina={self.piscina.pk}')
        self.assertContains(respuesta, 'Simulado')

    @override_settings(MONITOREO_OXIGENO_SIMULADO=False)
    def test_se_puede_apagar(self):
        self.assertNotIn('SEN-OX', self._sensores())

    def test_sensor_activo_sin_lecturas_no_se_simula(self):
        """Un sensor instalado que no transmite se ve como falla, no se tapa."""
        Sensor.objects.filter(pk=self.sensor_ox.pk).update(estado='activo')
        oxigeno = self._sensores()['SEN-OX']
        self.assertFalse(oxigeno['simulado'])
        self.assertIsNone(oxigeno['valor'])

    def test_con_sensor_real_no_se_simula(self):
        Sensor.objects.filter(pk=self.sensor_ox.pk).update(estado='activo')
        self.enviar_lectura('SEN-OX', Decimal('6.4'))
        oxigeno = self._sensores()['SEN-OX']
        self.assertFalse(oxigeno['simulado'])
        self.assertEqual(oxigeno['valor'], 6.4)
