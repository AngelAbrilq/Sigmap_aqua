"""
Asistente IA flotante global (apps.ia.context_processors.agente_ia).

El asistente debe aparecer en todas las páginas para quien tiene acceso al
módulo de IA, con un resumen del último análisis, y nunca debe tumbar una
página si algo falla al armar ese resumen.
"""

import json
from unittest import mock

from django.test import RequestFactory

from apps.ia.context_processors import agente_ia
from apps.ia.models import AnalisisIA
from apps.usuarios.models import Rol, Usuario

from .base import CLAVE_VALIDA, BaseSigmap


def _datos_agente(respuesta):
    """Extrae el JSON #iaAgenteDatos que base.html entrega al agente."""
    html = respuesta.content.decode()
    marca = 'id="iaAgenteDatos" type="application/json">'
    inicio = html.index(marca) + len(marca)
    fin = html.index('</script>', inicio)
    return json.loads(html[inicio:fin])


class AgenteGlobalTest(BaseSigmap):
    """El asistente acompaña al usuario en todo el sistema."""

    def setUp(self):
        self.client.force_login(self.instructor)

    def test_aparece_fuera_del_modulo_de_ia(self):
        """Camino feliz: en otra pantalla también está el robot."""
        respuesta = self.client.get('/geomembranas/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'data-agent')
        self.assertContains(respuesta, 'css/ia_agente.css')
        self.assertContains(respuesta, 'js/ia_agente.js')
        self.assertFalse(_datos_agente(respuesta)['en_modulo_ia'])

    def test_se_incluye_una_sola_vez_en_el_modulo_de_ia(self):
        """Caso límite: /ai/ no debe duplicar el widget."""
        respuesta = self.client.get('/ai/')

        self.assertEqual(respuesta.content.decode().count('id="iaAgent"'), 1)
        self.assertTrue(_datos_agente(respuesta)['en_modulo_ia'])

    def test_resume_el_ultimo_analisis(self):
        """El JSON lleva riesgo, anomalías y recomendaciones del análisis más reciente."""
        AnalisisIA.objects.create(
            geomembrana=self.piscina, tipo_analisis='diagnostico',
            descripcion_analisis='Turbidez elevada.', confianza=88,
            anomalias_detectadas=[{'parametro': 'Turbidez', 'descripcion': 'Alta', 'gravedad': 'alta'}],
            datos_entrada={},
            resultados_salida={'riesgo_proyectado': 'alto', 'recomendaciones': ['Recambio de agua']},
        )

        datos = _datos_agente(self.client.get('/geomembranas/'))

        self.assertEqual(datos['analisis']['piscina'], 'Estanque de Prueba')
        self.assertEqual(datos['analisis']['riesgo'], 'alto')
        self.assertEqual(datos['analisis']['confianza'], 88)
        self.assertEqual(datos['analisis']['anomalias'][0]['gravedad'], 'alta')
        self.assertEqual(datos['analisis']['recomendaciones'], ['Recambio de agua'])
        self.assertIn('?seleccion=', datos['url_analisis'])

    def test_sin_analisis_entrega_contexto_vacio_valido(self):
        """Sistema recién instalado: el agente igual carga, sin análisis."""
        datos = _datos_agente(self.client.get('/geomembranas/'))

        self.assertIsNone(datos['analisis'])
        self.assertEqual(datos['pendientes'], [])
        self.assertEqual(datos['alertas'], {'activas': 0, 'graves': 0})


class AgentePermisosTest(BaseSigmap):
    """Solo quien puede ver el módulo de IA ve al asistente."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_anonimo_no_recibe_agente(self):
        """La pantalla de login no expone datos del cultivo."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get('/')
        request.user = AnonymousUser()

        self.assertIsNone(agente_ia(request)['agente_ia'])

    def test_rol_sin_permiso_no_recibe_agente(self):
        """Error de permisos: un rol fuera de MODULOS_POR_ROL no ve al asistente."""
        visitante = Usuario.objects.create_user(
            'visitante@sena.edu.co', 'Visitante', CLAVE_VALIDA,
            rol=Rol.objects.create(nombre_rol='Visitante'))
        request = self.factory.get('/')
        request.user = visitante

        self.assertIsNone(agente_ia(request)['agente_ia'])

    def test_un_fallo_de_datos_no_tumba_la_pagina(self):
        """Si la consulta falla, la página carga y el agente queda sin análisis."""
        self.client.force_login(self.operario)
        with mock.patch('apps.ia.context_processors._resumen_analisis', side_effect=RuntimeError('BD caída')):
            respuesta = self.client.get('/geomembranas/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(_datos_agente(respuesta)['analisis'])
