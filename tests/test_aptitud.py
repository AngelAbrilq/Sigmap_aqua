"""
RF013: aptitud de la piscina para produccion + recomendaciones.
"""
from decimal import Decimal

from django.utils import timezone

from apps.monitoreo.aptitud import evaluar_aptitud
from apps.monitoreo.models import Lectura

from .base import BaseSigmap


class AptitudTest(BaseSigmap):
    """La base crea una piscina con sensores de pH (6.5-8.5) y O2 (5-9)."""

    def _lectura(self, sensor, tipo, valor):
        return Lectura.objects.create(
            sensor=sensor, geomembrana=self.piscina, tipo_parametro=tipo,
            valor_medida=Decimal(str(valor)), dispositivo=self.dispositivo,
            timestamp_lectura=timezone.now(),
        )

    def test_sin_lecturas_apta_pero_sin_datos(self):
        r = evaluar_aptitud(self.piscina)
        self.assertTrue(r['apta'])
        self.assertEqual(r['estado_general'], 'optimo')
        self.assertEqual(len(r['sin_datos']), 2)   # pH y Oxigeno sin reportar

    def test_todo_normal_es_apta(self):
        self._lectura(self.sensor_ph, self.ph, 7.2)
        self._lectura(self.sensor_ox, self.oxigeno, 6.5)
        r = evaluar_aptitud(self.piscina)
        self.assertTrue(r['apta'])
        self.assertEqual(r['motivos'], [])

    def test_critico_la_vuelve_no_apta_con_recomendacion(self):
        self._lectura(self.sensor_ph, self.ph, 9.6)     # > riesgo_max(9.0) -> critico
        self._lectura(self.sensor_ox, self.oxigeno, 6.5)
        r = evaluar_aptitud(self.piscina)
        self.assertFalse(r['apta'])
        self.assertEqual(r['estado_general'], 'critico')
        motivo_ph = next(m for m in r['motivos'] if m['parametro'] == 'pH')
        self.assertEqual(motivo_ph['estado'], 'critico')
        self.assertEqual(motivo_ph['direccion'], 'alto')
        self.assertIn('pH', motivo_ph['recomendacion'])

    def test_riesgo_sigue_apta_pero_lo_reporta(self):
        self._lectura(self.sensor_ph, self.ph, 8.8)     # entre 8.5 y 9.0 -> riesgo
        r = evaluar_aptitud(self.piscina)
        self.assertTrue(r['apta'])
        self.assertEqual(r['estado_general'], 'riesgo')
        self.assertEqual(len(r['motivos']), 1)
