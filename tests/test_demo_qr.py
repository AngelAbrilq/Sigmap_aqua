"""
Acceso de demostración por QR (apps.demo).

Cubre: firma y vencimiento del token, revocación por versión, que el GET no
inicie sesión, que el POST sí lo haga con el rol correcto, la auditoría, la
pantalla de presentación, el feed en vivo y el comando generar_qrs_demo.
"""

import tempfile
from pathlib import Path
from unittest import mock

from django.core import signing
from django.core.management import call_command
from django.test import override_settings

from apps.auditoria.models import EventoSistema
from apps.demo.qr import qr_svg
from apps.demo.tokens import TokenDemoInvalido, crear_token, leer_token

from .base import BaseSigmap

DEMO = dict(DEMO_QR_ACTIVO=True, DEMO_QR_HORAS=24, DEMO_QR_VERSION=1,
            DEMO_QR_SESION_MINUTOS=120, DEMO_QR_URL_BASE='https://demo.devtunnels.ms')


@override_settings(**DEMO)
class TokenDemoTest(BaseSigmap):

    def test_token_valido_devuelve_el_usuario(self):
        """Camino feliz: el token firmado identifica al usuario."""
        self.assertEqual(leer_token(crear_token(self.operario)), self.operario)

    def test_token_no_contiene_la_contrasena_ni_el_correo(self):
        """El QR solo lleva id + versión firmados."""
        token = crear_token(self.instructor)
        self.assertNotIn(self.instructor.email, token)
        self.assertTrue(token.startswith(f'{self.instructor.pk}.1:'))

    def test_token_alterado_es_invalido(self):
        """Error: cambiar el id para hacerse pasar por otro usuario."""
        token = crear_token(self.aprendiz)
        falso = token.replace(f'{self.aprendiz.pk}.', f'{self.instructor.pk}.', 1)
        with self.assertRaises(TokenDemoInvalido) as ctx:
            leer_token(falso)
        self.assertEqual(ctx.exception.motivo, 'invalido')

    def test_token_vencido(self):
        """Caso límite: pasada la vigencia el QR deja de servir."""
        token = crear_token(self.operario)
        with mock.patch.object(signing.TimestampSigner, 'unsign',
                               side_effect=signing.SignatureExpired('vencido')):
            with self.assertRaises(TokenDemoInvalido) as ctx:
                leer_token(token)
        self.assertEqual(ctx.exception.motivo, 'expirado')

    def test_subir_la_version_revoca_los_qr(self):
        """Revocación inmediata de todos los QR impresos."""
        token = crear_token(self.operario)
        with override_settings(DEMO_QR_VERSION=2):
            with self.assertRaises(TokenDemoInvalido) as ctx:
                leer_token(token)
        self.assertEqual(ctx.exception.motivo, 'revocado')

    def test_usuario_inactivo_no_entra(self):
        """Si el usuario se desactiva, su QR deja de funcionar."""
        token = crear_token(self.operario)
        self.operario.estado = 'inactivo'
        self.operario.save(update_fields=['estado'])
        with self.assertRaises(TokenDemoInvalido) as ctx:
            leer_token(token)
        self.assertEqual(ctx.exception.motivo, 'usuario')


@override_settings(**DEMO)
class AccesoQrTest(BaseSigmap):

    def _url(self, usuario):
        return f'/demo/q/{crear_token(usuario)}/'

    def test_get_muestra_la_animacion_sin_iniciar_sesion(self):
        """Los visores de enlaces (WhatsApp, cámara) no consumen el acceso."""
        respuesta = self.client.get(self._url(self.operario))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Operario')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_post_inicia_sesion_y_lleva_al_panel_del_rol(self):
        """Camino feliz: escanear y entrar."""
        respuesta = self.client.post(self._url(self.aprendiz))

        self.assertRedirects(respuesta, '/aprendiz/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.aprendiz.pk)
        self.assertEqual(self.client.session['acceso_demo'], 'aprendiz')
        self.assertEqual(self.client.session.get_expiry_age(), 120 * 60)

    def test_el_ingreso_queda_en_auditoria(self):
        """Cada ingreso por QR se registra con su rol."""
        self.client.post(self._url(self.instructor))

        evento = EventoSistema.objects.get(tipo_evento='sesion_inicio')
        self.assertEqual(evento.usuario, self.instructor)
        self.assertEqual(evento.datos['via'], 'qr_demo')
        self.assertEqual(evento.datos['rol'], 'instructor')

    def test_token_invalido_muestra_pantalla_amable(self):
        """Error: QR falso o roto."""
        respuesta = self.client.get('/demo/q/123.1:abc:falso/')

        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, 'no es válido', status_code=403)

    @override_settings(DEMO_QR_ACTIVO=False)
    def test_con_la_demo_apagada_no_existe(self):
        """Fuera de la sustentación las rutas devuelven 404."""
        self.assertEqual(self.client.get(self._url(self.operario)).status_code, 404)
        self.assertEqual(self.client.post(self._url(self.operario)).status_code, 404)


@override_settings(**DEMO)
class PresentacionTest(BaseSigmap):

    def test_instructor_ve_los_tres_qr(self):
        """La pantalla para proyectar trae un QR SVG por rol."""
        self.client.force_login(self.instructor)
        respuesta = self.client.get('/demo/presentacion/')

        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        for slug in ('instructor', 'operario', 'aprendiz'):
            self.assertIn(f'data-card="{slug}"', html)
        self.assertEqual(html.count('aria-label="Código QR de acceso'), 3)
        self.assertIn('https://demo.devtunnels.ms', html)  # base visible
        self.assertNotIn('/demo/q/', html)  # el token solo viaja dentro del QR

    def test_otros_roles_no_ven_la_presentacion(self):
        """Error de permisos: solo el Instructor Líder proyecta los QR."""
        self.client.force_login(self.operario)
        respuesta = self.client.get('/demo/presentacion/')
        self.assertEqual(respuesta.status_code, 302)

    def test_feed_devuelve_solo_ingresos_nuevos_por_qr(self):
        """El feed en vivo responde {success, data, message} desde un id."""
        self.client.post(f'/demo/q/{crear_token(self.operario)}/')
        self.client.force_login(self.instructor)

        respuesta = self.client.get('/demo/actividad/?despues=0').json()

        self.assertTrue(respuesta['success'])
        self.assertEqual([e['rol'] for e in respuesta['data']], ['operario'])
        ultimo = respuesta['data'][-1]['id']
        self.assertEqual(self.client.get(f'/demo/actividad/?despues={ultimo}').json()['data'], [])

    def test_feed_rechaza_parametro_invalido(self):
        """Validación de entrada del feed."""
        self.client.force_login(self.instructor)
        respuesta = self.client.get('/demo/actividad/?despues=abc')
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['success'])


@override_settings(**DEMO)
class GenerarQrsDemoTest(BaseSigmap):

    def test_genera_png_y_svg_por_rol(self):
        """El comando deja los archivos listos para imprimir."""
        with tempfile.TemporaryDirectory() as carpeta:
            call_command('generar_qrs_demo', '--salida', carpeta, '--escala', '10', stdout=mock.MagicMock())
            archivos = sorted(p.name for p in Path(carpeta).iterdir())

        self.assertEqual(archivos, [
            'qr_aprendiz.png', 'qr_aprendiz.svg', 'qr_instructor.png',
            'qr_instructor.svg', 'qr_operario.png', 'qr_operario.svg',
        ])

    def test_sin_url_falla_con_mensaje_claro(self):
        """Error: no hay URL pública configurada."""
        from django.core.management.base import CommandError

        with override_settings(DEMO_QR_URL_BASE=''):
            with self.assertRaises(CommandError):
                call_command('generar_qrs_demo', stdout=mock.MagicMock())

    def test_svg_es_valido_y_lleva_el_robot(self):
        """El SVG del QR es autocontenido."""
        svg = qr_svg('https://demo.devtunnels.ms/demo/q/1.1:x:y/', '#2f80ed', '#22d3ee')
        self.assertTrue(svg.startswith('<svg') and svg.endswith('</svg>'))
        self.assertIn('linearGradient', svg)
