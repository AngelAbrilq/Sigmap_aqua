"""
Proveedores de IA: DeepSeek como principal y Gemini como respaldo.

No hay llamadas reales: se simula urlopen para revisar qué se envía y cómo
se interpreta lo que vuelve.
"""
import io
import json
import urllib.error
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.ia.services import (
    ErrorIA, _llamar_deepseek, _llamar_ia, ia_configurada, proveedores_configurados,
)

SALIDA = {
    'diagnostico': 'Agua estable.', 'anomalias': [], 'recomendaciones': [],
    'riesgo_proyectado': 'bajo', 'confianza': 90,
}


class _RespuestaFalsa(io.BytesIO):
    """Imita el objeto que devuelve urlopen dentro de un with."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _respuesta_deepseek(contenido, finish_reason='stop'):
    cuerpo = {'choices': [{'message': {'role': 'assistant', 'content': contenido},
                           'finish_reason': finish_reason}]}
    return _RespuestaFalsa(json.dumps(cuerpo).encode('utf-8'))


def _error_http(codigo):
    return urllib.error.HTTPError(
        'https://api.deepseek.com/chat/completions', codigo, 'error', {},
        io.BytesIO(b'{"error": "x"}'))


@override_settings(DEEPSEEK_API_KEY='sk-prueba', DEEPSEEK_MODEL='deepseek-flash',
                   DEEPSEEK_BASE_URL='https://api.deepseek.com')
class LlamarDeepSeekTest(SimpleTestCase):
    """Petición y lectura de la respuesta de DeepSeek."""

    @patch('apps.ia.services.urllib.request.urlopen')
    def test_camino_feliz_devuelve_el_json(self, urlopen):
        urlopen.return_value = _respuesta_deepseek(json.dumps(SALIDA))
        self.assertEqual(_llamar_deepseek('Analiza'), SALIDA)

    @patch('apps.ia.services.urllib.request.urlopen')
    def test_envia_modo_json_modelo_y_clave(self, urlopen):
        urlopen.return_value = _respuesta_deepseek(json.dumps(SALIDA))
        _llamar_deepseek('Analiza')

        peticion = urlopen.call_args.args[0]
        cuerpo = json.loads(peticion.data)
        self.assertEqual(peticion.full_url, 'https://api.deepseek.com/chat/completions')
        self.assertEqual(peticion.get_header('Authorization'), 'Bearer sk-prueba')
        self.assertEqual(cuerpo['model'], 'deepseek-flash')
        self.assertEqual(cuerpo['response_format'], {'type': 'json_object'})
        # El modo JSON de DeepSeek exige que el prompt mencione "JSON".
        self.assertIn('JSON', cuerpo['messages'][0]['content'])
        self.assertIn('riesgo_proyectado', cuerpo['messages'][0]['content'])

    @patch('apps.ia.services.urllib.request.urlopen')
    def test_contenido_vacio_es_error_controlado(self, urlopen):
        """DeepSeek documenta que en modo JSON puede devolver contenido vacío."""
        urlopen.return_value = _respuesta_deepseek('')
        with self.assertRaises(ErrorIA):
            _llamar_deepseek('Analiza')

    @patch('apps.ia.services.urllib.request.urlopen')
    def test_respuesta_cortada_es_error_controlado(self, urlopen):
        urlopen.return_value = _respuesta_deepseek('{"diagnostico": "a', finish_reason='length')
        with self.assertRaisesMessage(ErrorIA, 'se cortó'):
            _llamar_deepseek('Analiza')

    @patch('apps.ia.services.urllib.request.urlopen')
    def test_clave_rechazada(self, urlopen):
        urlopen.side_effect = _error_http(401)
        with self.assertRaisesMessage(ErrorIA, 'DEEPSEEK_API_KEY'):
            _llamar_deepseek('Analiza')

    @patch('apps.ia.services.urllib.request.urlopen')
    def test_sin_saldo(self, urlopen):
        urlopen.side_effect = _error_http(402)
        with self.assertRaisesMessage(ErrorIA, 'saldo'):
            _llamar_deepseek('Analiza')

    @patch('apps.ia.services.urllib.request.urlopen')
    def test_sin_red(self, urlopen):
        urlopen.side_effect = urllib.error.URLError('sin red')
        with self.assertRaisesMessage(ErrorIA, 'conexión'):
            _llamar_deepseek('Analiza')

    @override_settings(DEEPSEEK_API_KEY='')
    def test_sin_clave(self):
        with self.assertRaises(ErrorIA):
            _llamar_deepseek('Analiza')


class OrdenProveedoresTest(SimpleTestCase):
    """DeepSeek primero; Gemini solo como respaldo."""

    @override_settings(IA_PROVEEDOR='deepseek', DEEPSEEK_API_KEY='a', GEMINI_API_KEY='b')
    def test_deepseek_es_el_principal(self):
        self.assertEqual(proveedores_configurados(), ['deepseek', 'gemini'])

    @override_settings(IA_PROVEEDOR='gemini', DEEPSEEK_API_KEY='a', GEMINI_API_KEY='b')
    def test_se_puede_cambiar_el_principal(self):
        self.assertEqual(proveedores_configurados(), ['gemini', 'deepseek'])

    @override_settings(IA_PROVEEDOR='deepseek', DEEPSEEK_API_KEY='', GEMINI_API_KEY='b')
    def test_sin_clave_de_deepseek_usa_gemini(self):
        self.assertEqual(proveedores_configurados(), ['gemini'])

    @override_settings(DEEPSEEK_API_KEY='', GEMINI_API_KEY='')
    def test_sin_claves_no_esta_configurada(self):
        self.assertFalse(ia_configurada())
        with self.assertRaisesMessage(ErrorIA, 'DEEPSEEK_API_KEY'):
            _llamar_ia('Analiza')

    @override_settings(IA_PROVEEDOR='deepseek', DEEPSEEK_API_KEY='a', GEMINI_API_KEY='b',
                       DEEPSEEK_MODEL='deepseek-flash')
    @patch('apps.ia.services._llamar_gemini')
    @patch('apps.ia.services._llamar_deepseek')
    def test_responde_deepseek_y_no_se_llama_a_gemini(self, deepseek, gemini):
        deepseek.return_value = SALIDA
        salida, modelo = _llamar_ia('Analiza')
        self.assertEqual((salida, modelo), (SALIDA, 'deepseek-flash'))
        gemini.assert_not_called()

    @override_settings(IA_PROVEEDOR='deepseek', DEEPSEEK_API_KEY='a', GEMINI_API_KEY='b',
                       GEMINI_MODEL='gemini-3.5-flash-lite')
    @patch('apps.ia.services._llamar_gemini')
    @patch('apps.ia.services._llamar_deepseek')
    def test_si_deepseek_falla_responde_gemini(self, deepseek, gemini):
        deepseek.side_effect = ErrorIA('caído')
        gemini.return_value = SALIDA
        salida, modelo = _llamar_ia('Analiza')
        self.assertEqual(modelo, 'gemini-3.5-flash-lite')

    @override_settings(IA_PROVEEDOR='deepseek', DEEPSEEK_API_KEY='a', GEMINI_API_KEY='b')
    @patch('apps.ia.services._llamar_gemini')
    @patch('apps.ia.services._llamar_deepseek')
    def test_si_ambos_fallan_se_informa_el_error(self, deepseek, gemini):
        deepseek.side_effect = ErrorIA('caído')
        gemini.side_effect = ErrorIA('cuota agotada')
        with self.assertRaisesMessage(ErrorIA, 'cuota agotada'):
            _llamar_ia('Analiza')
