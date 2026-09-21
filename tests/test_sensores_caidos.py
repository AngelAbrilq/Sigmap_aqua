"""
Deteccion de sensores caidos (RF001).

Cubre: apertura por silencio/sin lecturas, no duplicacion (idempotente),
que un sensor con lectura reciente no dispare alerta, el auto-cierre cuando el
sensor vuelve a transmitir, y el rastro en auditoria.
"""
from decimal import Decimal

from django.utils import timezone

from apps.alertas.models import Alerta
from apps.alertas.services import evaluar_sensores_caidos
from apps.auditoria.models import EventoSistema
from apps.monitoreo.models import Lectura

from .base import BaseSigmap


class SensoresCaidosTest(BaseSigmap):
    """La base crea 2 sensores activos (pH y O2) sin lecturas."""

    def _lectura(self, sensor, tipo, valor, cuando=None):
        return Lectura.objects.create(
            sensor=sensor, geomembrana=self.piscina, tipo_parametro=tipo,
            valor_medida=Decimal(str(valor)), dispositivo=self.dispositivo,
            timestamp_lectura=cuando or timezone.now(),
        )

    def test_sensor_sin_lecturas_abre_alerta(self):
        resultado = evaluar_sensores_caidos()
        self.assertEqual(resultado['abiertas'], 2)
        self.assertEqual(
            Alerta.objects.filter(tipo_alerta='sensor', estado='activa').count(), 2)

    def test_es_idempotente(self):
        evaluar_sensores_caidos()
        segunda = evaluar_sensores_caidos()
        self.assertEqual(segunda['abiertas'], 0)
        self.assertEqual(
            Alerta.objects.filter(tipo_alerta='sensor', estado='activa').count(), 2)

    def test_lectura_reciente_no_dispara_alerta(self):
        self._lectura(self.sensor_ph, self.ph, 7.0)
        resultado = evaluar_sensores_caidos()
        # Solo el de oxigeno (sin lecturas) queda caido.
        self.assertEqual(resultado['abiertas'], 1)
        self.assertFalse(
            Alerta.objects.filter(tipo_alerta='sensor', sensor=self.sensor_ph,
                                  estado='activa').exists())
        self.assertTrue(
            Alerta.objects.filter(tipo_alerta='sensor', sensor=self.sensor_ox,
                                  estado='activa').exists())

    def test_autocierre_cuando_vuelve_a_transmitir(self):
        # 1) pH cae y se abre su alerta.
        evaluar_sensores_caidos()
        self.assertTrue(
            Alerta.objects.filter(tipo_alerta='sensor', sensor=self.sensor_ph,
                                  estado='activa').exists())
        # 2) llega una lectura reciente de pH -> su alerta se cierra sola.
        self._lectura(self.sensor_ph, self.ph, 7.2)
        resultado = evaluar_sensores_caidos()
        self.assertGreaterEqual(resultado['cerradas'], 1)
        self.assertFalse(
            Alerta.objects.filter(tipo_alerta='sensor', sensor=self.sensor_ph,
                                  estado='activa').exists())
        self.assertTrue(
            Alerta.objects.filter(tipo_alerta='sensor', sensor=self.sensor_ph,
                                  estado='resuelta').exists())

    def test_registra_evento_de_auditoria(self):
        evaluar_sensores_caidos()
        self.assertTrue(
            EventoSistema.objects.filter(
                tipo_evento='sistema', nivel='critico',
                descripcion__startswith='Sensor caido',
            ).exists())
