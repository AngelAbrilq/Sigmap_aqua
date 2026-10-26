"""
Comando limpiar_datos_capturados.

Debe dejar la base lista para capturar de nuevo desde el ESP32 sin perder la
configuración: piscinas, sensores, dispositivos, parámetros y usuarios.
"""

from io import StringIO

from django.core.management import call_command

from apps.alertas.models import Alerta
from apps.auditoria.models import EventoSistema
from apps.ia.models import AnalisisIA
from apps.monitoreo.models import Dispositivo, Lectura, Sensor, TipoParametro
from apps.piscinas.models import Geomembrana
from apps.usuarios.models import Usuario

from .base import BaseSigmap


class LimpiarDatosCapturadosTest(BaseSigmap):

    def setUp(self):
        # Una lectura fuera de rango genera lectura + alerta + notificaciones.
        self.enviar_lectura('SEN-PH', '9.6')
        AnalisisIA.objects.create(
            geomembrana=self.piscina, tipo_analisis='diagnostico',
            datos_entrada={}, resultados_salida={'riesgo_proyectado': 'alto'})

    def _ejecutar(self, *args):
        salida = StringIO()
        call_command('limpiar_datos_capturados', *args, stdout=salida)
        return salida.getvalue()

    def test_sin_confirmar_no_borra_nada(self):
        """Caso límite: el modo por defecto es solo simulación."""
        lecturas_antes = Lectura.objects.count()

        salida = self._ejecutar()

        self.assertIn('Modo simulación', salida)
        self.assertEqual(Lectura.objects.count(), lecturas_antes)
        self.assertTrue(AnalisisIA.objects.exists())

    def test_confirmar_borra_lo_capturado(self):
        """Camino feliz: lecturas, alertas y análisis quedan en cero."""
        self.assertTrue(Lectura.objects.exists())
        self.assertTrue(Alerta.objects.exists())

        self._ejecutar('--confirmar')

        self.assertFalse(Lectura.objects.exists())
        self.assertFalse(Alerta.objects.exists())
        self.assertFalse(AnalisisIA.objects.exists())
        self.assertIsNone(Dispositivo.objects.get().ultima_conexion)

    def test_conserva_la_configuracion(self):
        """Piscinas, sensores, dispositivo, parámetros y usuarios no se tocan."""
        token = self.dispositivo.token

        self._ejecutar('--confirmar')

        self.assertEqual(Geomembrana.objects.count(), 1)
        self.assertEqual(Sensor.objects.count(), 2)
        self.assertEqual(Dispositivo.objects.get().token, token)
        self.assertEqual(TipoParametro.objects.count(), 2)
        self.assertEqual(Usuario.objects.count(), 3)

    def test_el_esp32_puede_volver_a_enviar(self):
        """Tras limpiar, la ingesta funciona y la piscina arranca sin alertas."""
        self._ejecutar('--confirmar')

        respuesta = self.enviar_lectura('SEN-PH', '7.2')

        self.assertIn(respuesta.status_code, (200, 201))
        self.assertEqual(Lectura.objects.count(), 1)
        self.assertEqual(self.piscina.alertas_activas.count(), 0)

    def test_eventos_se_conservan_salvo_que_se_pida(self):
        """La auditoría se mantiene por defecto y registra la limpieza."""
        self._ejecutar('--confirmar')
        self.assertTrue(EventoSistema.objects.filter(tipo_evento='sistema').exists())

        self._ejecutar('--confirmar', '--incluir-eventos')
        # Solo queda el evento de la última limpieza.
        self.assertEqual(EventoSistema.objects.count(), 1)
