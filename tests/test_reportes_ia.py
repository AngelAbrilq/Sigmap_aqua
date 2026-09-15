"""
Agregaciones, reportes, exportaciones y el modulo de IA.
"""
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from apps.ia.models import AnalisisIA
from apps.ia.services import ErrorIA, construir_contexto, generar_analisis
from apps.reportes.models import ComparacionDatos, Reporte
from apps.reportes.services import comparar_periodos, resumen_periodo

from .base import BaseSigmap


class AgregacionesTest(BaseSigmap):
    """El calculo ocurre en la base de datos, no en Python."""

    def setUp(self):
        # Arrange: cinco lecturas normales y dos fuera de rango.
        for valor in (7.0, 7.1, 7.2, 6.9, 7.3):
            self.enviar_lectura('SEN-PH', valor)
        self.enviar_lectura('SEN-PH', 9.5)
        self.enviar_lectura('SEN-OX', 2.0)
        self.hoy = timezone.localdate()

    def test_el_resumen_cuenta_todas_las_lecturas(self):
        datos = resumen_periodo(self.piscina, self.hoy - timedelta(days=1), self.hoy)
        self.assertEqual(datos['lecturas'], 7)

    def test_el_resumen_separa_las_lecturas_fuera_de_rango(self):
        datos = resumen_periodo(self.piscina, self.hoy - timedelta(days=1), self.hoy)
        self.assertEqual(datos['fuera_rango'], 2)

    def test_calcula_el_porcentaje_de_cumplimiento(self):
        """5 de 7 dentro de rango = 71.4 %."""
        datos = resumen_periodo(self.piscina, self.hoy - timedelta(days=1), self.hoy)
        self.assertAlmostEqual(datos['cumplimiento'], 71.4, places=1)

    def test_un_periodo_sin_lecturas_no_divide_por_cero(self):
        """Caso limite: cumplimiento es None, no una excepcion."""
        lejano = self.hoy - timedelta(days=365)
        datos = resumen_periodo(self.piscina, lejano, lejano)
        self.assertEqual(datos['lecturas'], 0)
        self.assertIsNone(datos['cumplimiento'])

    def test_compara_dos_periodos_y_calcula_la_variacion(self):
        """Camino feliz de la comparacion."""
        resultado = comparar_periodos(
            self.piscina, self.hoy - timedelta(days=14), self.hoy - timedelta(days=8),
            self.hoy - timedelta(days=1), self.hoy)
        self.assertIn('variaciones', resultado)
        self.assertIn('por_parametro', resultado)


class ReportesTest(BaseSigmap):
    """Un reporte congela sus datos: es evidencia, no una consulta viva."""

    def setUp(self):
        self.enviar_lectura('SEN-PH', 7.2)
        self.client.force_login(self.instructor)
        self.hoy = timezone.localdate()

    def test_genera_un_reporte_con_datos_agregados(self):
        self.client.post('/graficas-reportes/crear/', {
            'piscina': self.piscina.pk,
            'desde': (self.hoy - timedelta(days=1)).isoformat(),
            'hasta': self.hoy.isoformat(), 'tipo': 'semanal', 'titulo': 'Prueba',
        }, follow=True)
        self.assertTrue(Reporte.objects.exists())

    def test_el_reporte_guarda_el_resumen_por_parametro(self):
        self.client.post('/graficas-reportes/crear/', {
            'piscina': self.piscina.pk,
            'desde': (self.hoy - timedelta(days=1)).isoformat(),
            'hasta': self.hoy.isoformat(), 'tipo': 'semanal', 'titulo': 'Prueba',
        }, follow=True)
        reporte = Reporte.objects.get()
        self.assertGreaterEqual(len(reporte.datos_reporte['parametros']), 1)

    def test_no_genera_reporte_de_un_periodo_sin_lecturas(self):
        """Caso de error: un reporte vacio no es evidencia de nada."""
        lejano = (self.hoy - timedelta(days=365)).isoformat()
        self.client.post('/graficas-reportes/crear/', {
            'piscina': self.piscina.pk, 'desde': lejano, 'hasta': lejano,
            'tipo': 'diario', 'titulo': 'Vacío',
        }, follow=True)
        self.assertFalse(Reporte.objects.exists())

    def test_exporta_el_reporte_a_csv(self):
        self.client.post('/graficas-reportes/crear/', {
            'piscina': self.piscina.pk,
            'desde': (self.hoy - timedelta(days=1)).isoformat(),
            'hasta': self.hoy.isoformat(), 'tipo': 'semanal', 'titulo': 'Prueba',
        }, follow=True)
        reporte = Reporte.objects.get()
        respuesta = self.client.get(f'/graficas-reportes/{reporte.pk}/csv/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('text/csv', respuesta['Content-Type'])

    def test_exporta_el_historial_a_csv(self):
        respuesta = self.client.get('/historial/csv/', {
            'desde': (self.hoy - timedelta(days=1)).isoformat(),
            'hasta': self.hoy.isoformat(),
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('attachment', respuesta['Content-Disposition'])

    def test_guarda_una_comparacion_de_periodos(self):
        self.client.post('/comparacion-periodos/guardar/', {
            'piscina': self.piscina.pk,
            'p1_inicio': (self.hoy - timedelta(days=14)).isoformat(),
            'p1_fin': (self.hoy - timedelta(days=8)).isoformat(),
            'p2_inicio': (self.hoy - timedelta(days=7)).isoformat(),
            'p2_fin': self.hoy.isoformat(),
        }, follow=True)
        self.assertTrue(ComparacionDatos.objects.exists())


class MonitoreoTiempoRealTest(BaseSigmap):
    """Endpoint JSON que alimenta el refresco del tablero."""

    def setUp(self):
        self.enviar_lectura('SEN-PH', 7.2)
        self.client.force_login(self.operario)

    def test_responde_con_el_formato_estandar(self):
        """{success, data, message}, igual que la API de hardware."""
        respuesta = self.client.get(f'/monitoreo/api/{self.piscina.pk}/estado/')
        cuerpo = respuesta.json()
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(cuerpo['success'])
        self.assertIn('sensores', cuerpo['data'])

    def test_devuelve_la_ultima_lectura_de_cada_sensor(self):
        respuesta = self.client.get(f'/monitoreo/api/{self.piscina.pk}/estado/')
        sensores = {s['codigo']: s for s in respuesta.json()['data']['sensores']}
        self.assertEqual(sensores['SEN-PH']['valor'], 7.2)

    def test_un_sensor_sin_lecturas_devuelve_valor_nulo(self):
        """Caso limite: no se inventa un cero que parezca una medicion real."""
        respuesta = self.client.get(f'/monitoreo/api/{self.piscina.pk}/estado/')
        sensores = {s['codigo']: s for s in respuesta.json()['data']['sensores']}
        self.assertIsNone(sensores['SEN-OX']['valor'])
        self.assertEqual(sensores['SEN-OX']['estado'], 'sin_datos')


class AnalisisIATest(BaseSigmap):
    """
    Modulo de IA. Las llamadas a Gemini se simulan: una prueba no debe
    depender de la red ni gastar cuota de la API.
    """

    def setUp(self):
        for valor in (7.0, 7.2, 8.9):
            self.enviar_lectura('SEN-PH', valor)
        self.client.force_login(self.instructor)

    def test_el_contexto_envia_agregados_y_no_lecturas_crudas(self):
        """
        Siete dias con cuatro sensores a cinco minutos son ~8000 filas: no
        caben en el prompt y no aportan mas que su estadistica.
        """
        contexto = construir_contexto(self.piscina, dias=7)
        self.assertEqual(contexto['total_lecturas'], 3)
        self.assertIn('parametros', contexto)
        self.assertNotIn('lecturas_crudas', contexto)

    def test_el_contexto_es_serializable_a_json(self):
        """Caso limite: los Decimal de la BD romperian json.dumps()."""
        import json
        contexto = construir_contexto(self.piscina, dias=7)
        self.assertIsInstance(json.dumps(contexto), str)

    def test_sin_lecturas_no_llama_a_la_api(self):
        """
        Caso de error: pedir un analisis de una piscina sin datos gastaria
        cuota para recibir una respuesta inventada.
        """
        from apps.piscinas.models import Geomembrana
        vacia = Geomembrana.objects.create(
            nombre_piscina='Sin datos', codigo_identificacion='GEO-SIN')
        with self.assertRaises(ErrorIA):
            generar_analisis(vacia, tipo='diagnostico', dias=7)

    @patch('apps.ia.services._llamar_gemini')
    def test_persiste_el_analisis_con_su_evidencia(self, llamada_simulada):
        """Camino feliz: la recomendacion queda auditable."""
        llamada_simulada.return_value = {
            'diagnostico': 'El pH muestra una tendencia al alza.',
            'anomalias': [{'parametro': 'pH', 'descripcion': 'Pico de 8.9',
                           'gravedad': 'media'}],
            'recomendaciones': ['Verificar la fuente de agua de recambio.'],
            'riesgo_proyectado': 'medio',
            'confianza': 78,
        }
        analisis = generar_analisis(self.piscina, tipo='diagnostico', dias=7)
        self.assertEqual(analisis.confianza, 78)
        self.assertEqual(analisis.estado, 'generado')
        self.assertEqual(analisis.datos_entrada['total_lecturas'], 3)
        self.assertEqual(len(analisis.anomalias_detectadas), 1)

    @patch('apps.ia.services._llamar_gemini')
    def test_acota_una_confianza_fuera_de_rango(self, llamada_simulada):
        """
        Caso limite: el modelo puede devolver 150. Se recorta a 100 en vez de
        guardar un valor imposible.
        """
        llamada_simulada.return_value = {
            'diagnostico': 'x', 'anomalias': [], 'recomendaciones': [],
            'riesgo_proyectado': 'bajo', 'confianza': 150,
        }
        analisis = generar_analisis(self.piscina, dias=7)
        self.assertEqual(analisis.confianza, 100)

    @patch('apps.ia.services._llamar_gemini')
    def test_una_confianza_no_numerica_no_rompe_el_guardado(self, llamada_simulada):
        """Caso limite: el modelo devuelve texto donde se esperaba un numero."""
        llamada_simulada.return_value = {
            'diagnostico': 'x', 'anomalias': [], 'recomendaciones': [],
            'riesgo_proyectado': 'bajo', 'confianza': 'alta',
        }
        analisis = generar_analisis(self.piscina, dias=7)
        self.assertIsNone(analisis.confianza)

    def test_un_fallo_de_la_ia_no_rompe_el_sistema(self):
        """
        Caso de error: sin API key la vista informa y vuelve al panel, sin
        excepcion sin capturar.
        """
        with self.settings(GEMINI_API_KEY=''):
            respuesta = self.client.post('/ai/generar/', {
                'piscina': self.piscina.pk, 'tipo': 'diagnostico', 'dias': '7',
            }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(AnalisisIA.objects.exists())

    @patch('apps.ia.services._llamar_gemini')
    def test_solo_el_instructor_valida_un_analisis(self, llamada_simulada):
        """
        Una recomendacion de IA solo se vuelve instruccion operativa cuando
        una persona con criterio tecnico la avala.
        """
        llamada_simulada.return_value = {
            'diagnostico': 'x', 'anomalias': [], 'recomendaciones': [],
            'riesgo_proyectado': 'bajo', 'confianza': 80,
        }
        analisis = generar_analisis(self.piscina, dias=7)

        self.client.force_login(self.operario)
        self.client.post(f'/ai/{analisis.pk}/estado/', {'estado': 'validado'}, follow=True)
        analisis.refresh_from_db()
        self.assertEqual(analisis.estado, 'generado')

        self.client.force_login(self.instructor)
        self.client.post(f'/ai/{analisis.pk}/estado/', {'estado': 'validado'}, follow=True)
        analisis.refresh_from_db()
        self.assertEqual(analisis.estado, 'validado')
        self.assertEqual(analisis.validado_por, self.instructor)
