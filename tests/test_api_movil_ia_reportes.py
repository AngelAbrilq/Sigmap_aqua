"""
API móvil: módulos de IA y reportes PDF/Excel.

Los servicios de IA se simulan (mock): las pruebas no deben gastar cuota de
la API de DeepSeek/Gemini ni depender de internet.
"""
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from apps.ia.models import AnalisisIA, ConsultaIA
from apps.ia.services import ErrorIA

from .test_api_movil import BASE, BaseAPI

SALIDA_IA = {
    'diagnostico': 'pH elevado en la tarde.',
    'anomalias': [{'parametro': 'pH', 'descripcion': 'Sube a 9.5', 'gravedad': 'alta'},
                  'texto suelto del modelo'],
    'recomendaciones': ['Hacer recambio parcial', 'Medir alcalinidad'],
    'riesgo_proyectado': 'alto',
    'confianza': 82,
}
RESPUESTA_ASISTENTE = {
    'respuesta': 'La piscina **GEO-TEST** tiene pH alto.',
    'hallazgos': [{'piscina': 'Estanque de Prueba', 'parametro': 'pH',
                   'descripcion': 'pH 9.5', 'gravedad': 'alta'}],
    'tablas': [{'titulo': 'Lecturas', 'columnas': ['Parámetro', 'Valor'],
                'filas': [['pH', '9.5']]}],
    'recomendaciones': ['Recambio de agua'],
    'sugerencias': ['¿Cómo está el oxígeno?'],
    'enlaces': [],
}


def _crear_analisis(piscina, **extra):
    return AnalisisIA.objects.create(
        geomembrana=piscina, tipo_analisis='diagnostico',
        datos_entrada={'total_lecturas': 40, 'ventana_dias': 7},
        resultados_salida=SALIDA_IA,
        descripcion_analisis=SALIDA_IA['diagnostico'],
        recomendaciones='\n'.join(SALIDA_IA['recomendaciones']),
        anomalias_detectadas=SALIDA_IA['anomalias'],
        confianza=82, modelo_usado='deepseek-test', **extra)


class AnalisisIAAPITest(BaseAPI):
    """Historial y generación de análisis."""

    def test_lista_el_analisis_con_la_forma_del_panel_web(self):
        # Arrange
        _crear_analisis(self.piscina)
        self.autenticar(self.aprendiz)

        # Act
        cuerpo = self.api.get(f'{BASE}/ia/analisis/?geomembrana={self.piscina.pk}').json()

        # Assert
        analisis = cuerpo['data']['resultados'][0]
        self.assertEqual(analisis['descripcion_analisis'], 'pH elevado en la tarde.')
        self.assertEqual(analisis['recomendaciones'],
                         ['Hacer recambio parcial', 'Medir alcalinidad'])
        self.assertEqual(analisis['riesgo_proyectado'], 'alto')
        self.assertEqual(analisis['nivel_confianza'], 'alta')
        self.assertEqual(analisis['total_lecturas'], 40)
        # El texto suelto del modelo se normaliza, no rompe la app.
        self.assertEqual(len(analisis['anomalias']), 2)
        self.assertEqual(analisis['anomalias'][1]['gravedad'], 'media')

    @patch('apps.api_movil.views.ia.generar_analisis')
    def test_el_operario_genera_un_analisis(self, generar):
        # Arrange
        generar.return_value = _crear_analisis(self.piscina)
        self.autenticar(self.operario)

        # Act
        respuesta = self.api.post(f'{BASE}/ia/analisis/', {
            'geomembrana': self.piscina.pk, 'tipo': 'prediccion',
            'dias': 15, 'horizonte': 5}, format='json')

        # Assert
        self.assertEqual(respuesta.status_code, 201)
        generar.assert_called_once_with(self.piscina, tipo='prediccion', dias=15, horizonte=5)
        self.assertTrue(respuesta.json()['success'])

    @patch('apps.api_movil.views.ia.generar_analisis')
    def test_el_aprendiz_no_puede_gastar_cuota_de_ia(self, generar):
        """Seguridad: el aprendiz solo ve el módulo de IA, no genera."""
        self.autenticar(self.aprendiz)

        respuesta = self.api.post(f'{BASE}/ia/analisis/',
                                  {'geomembrana': self.piscina.pk}, format='json')

        self.assertEqual(respuesta.status_code, 403)
        generar.assert_not_called()

    def test_una_ventana_no_permitida_se_rechaza_con_el_campo(self):
        """Caso límite: mismas ventanas que la web (3, 7, 15, 30)."""
        self.autenticar(self.operario)

        cuerpo = self.api.post(f'{BASE}/ia/analisis/', {
            'geomembrana': self.piscina.pk, 'dias': 9}, format='json').json()

        self.assertFalse(cuerpo['success'])
        self.assertIn('dias', cuerpo['data'])

    @patch('apps.api_movil.views.ia.generar_analisis',
           side_effect=ErrorIA('No hay lecturas en los últimos 7 días.'))
    def test_sin_datos_la_ia_responde_503_con_mensaje(self, _generar):
        self.autenticar(self.operario)

        respuesta = self.api.post(f'{BASE}/ia/analisis/',
                                  {'geomembrana': self.piscina.pk}, format='json')

        self.assertEqual(respuesta.status_code, 503)
        self.assertIn('No hay lecturas', respuesta.json()['message'])


class AsistenteIAAPITest(BaseAPI):
    """Chat del asistente y su Excel."""

    def _consulta(self, usuario):
        return ConsultaIA.objects.create(
            usuario=usuario, pregunta='¿Cómo está el pH?',
            respuesta=RESPUESTA_ASISTENTE, contexto={}, modelo_usado='deepseek-test')

    @patch('apps.api_movil.views.ia.preguntar')
    def test_el_aprendiz_puede_preguntar_como_en_la_web(self, preguntar):
        # Arrange
        preguntar.return_value = self._consulta(self.aprendiz)
        self.autenticar(self.aprendiz)

        # Act
        respuesta = self.api.post(f'{BASE}/ia/asistente/',
                                  {'pregunta': '¿Cómo está el pH?'}, format='json')

        # Assert
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()['data']
        self.assertEqual(datos['hallazgos'][0]['gravedad'], 'alta')
        self.assertTrue(datos['tiene_excel'])

    def test_una_pregunta_vacia_se_rechaza(self):
        self.autenticar(self.operario)

        cuerpo = self.api.post(f'{BASE}/ia/asistente/', {'pregunta': '  '},
                               format='json').json()

        self.assertFalse(cuerpo['success'])
        self.assertIn('pregunta', cuerpo['data'])

    def test_el_excel_de_otro_usuario_no_existe(self):
        """Seguridad: la consulta de otro operario no se puede descargar."""
        ajena = self._consulta(self.instructor)
        self.autenticar(self.operario)

        respuesta = self.api.get(f'{BASE}/ia/asistente/{ajena.pk}/excel/')

        self.assertEqual(respuesta.status_code, 404)

    def test_el_autor_descarga_su_excel(self):
        propia = self._consulta(self.operario)
        self.autenticar(self.operario)

        respuesta = self.api.get(f'{BASE}/ia/asistente/{propia.pk}/excel/',
                                 HTTP_ACCEPT='*/*')

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('spreadsheetml', respuesta['Content-Type'])
        self.assertTrue(respuesta.content.startswith(b'PK'))  # xlsx = zip


class ReportesAPITest(BaseAPI):
    """Vista previa y descarga de reportes del historial."""

    def setUp(self):
        super().setUp()
        self.enviar_lectura('SEN-PH', 7.2)
        self.enviar_lectura('SEN-PH', 9.5)
        self.hoy = timezone.localdate().isoformat()

    def test_los_parametros_activos_alimentan_los_filtros(self):
        self.autenticar(self.aprendiz)

        datos = self.api.get(f'{BASE}/parametros/').json()['data']

        self.assertIn('pH', [p['nombre_parametro'] for p in datos])

    def test_la_vista_previa_resume_las_lecturas_filtradas(self):
        # Arrange
        self.autenticar(self.operario)

        # Act
        datos = self.api.get(
            f'{BASE}/reportes/historial/resumen/',
            {'geomembrana': self.piscina.pk, 'parametro': self.ph.pk,
             'desde': self.hoy, 'hasta': self.hoy}).json()['data']

        # Assert
        self.assertEqual(datos['total'], 2)
        self.assertEqual(datos['criticas'], 1)
        self.assertEqual(datos['parametros'][0]['parametro'], 'pH')
        self.assertEqual(datos['parametros'][0]['maximo'], 9.5)

    def test_descarga_el_pdf_identico_al_de_la_web(self):
        self.autenticar(self.operario)

        respuesta = self.api.get(f'{BASE}/reportes/historial/',
                                 {'formato': 'pdf', 'desde': self.hoy, 'hasta': self.hoy},
                                 HTTP_ACCEPT='*/*')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertTrue(respuesta.content.startswith(b'%PDF'))
        self.assertIn('.pdf', respuesta['Content-Disposition'])

    def test_descarga_el_excel(self):
        self.autenticar(self.aprendiz)

        respuesta = self.api.get(f'{BASE}/reportes/historial/',
                                 {'formato': 'xlsx', 'geomembrana': self.piscina.pk},
                                 HTTP_ACCEPT='*/*')

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.content.startswith(b'PK'))

    def test_un_rango_invertido_responde_400_en_json(self):
        """Caso límite: el error de filtros llega como JSON aunque se pida un archivo."""
        self.autenticar(self.operario)
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()

        respuesta = self.api.get(f'{BASE}/reportes/historial/',
                                 {'desde': self.hoy, 'hasta': ayer}, HTTP_ACCEPT='*/*')

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('desde', respuesta.json()['data'])

    def test_un_formato_desconocido_se_rechaza(self):
        self.autenticar(self.operario)

        respuesta = self.api.get(f'{BASE}/reportes/historial/', {'formato': 'docx'})

        self.assertEqual(respuesta.status_code, 400)

    def test_sin_token_no_hay_reporte(self):
        respuesta = self.api.get(f'{BASE}/reportes/historial/')

        self.assertEqual(respuesta.status_code, 401)
