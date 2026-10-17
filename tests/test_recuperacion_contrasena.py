"""
Recuperacion de contrasena (RF025 / HU 025).

Cada clase cubre un escenario de la historia de usuario.
"""
import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.auditoria.models import EventoSistema
from apps.usuarios.models import Usuario

from .base import BaseSigmap, CLAVE_VALIDA

URL_SOLICITUD = '/auth/recuperar/'
URL_ENVIADO = '/auth/recuperar/enviado/'
NUEVA_CLAVE = 'Tilapia.Roja.2026'
MENSAJE_GENERICO = 'Si el correo está registrado'


def _enlace_de(usuario):
    """Construye el enlace de restablecimiento que Django enviaria por correo."""
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return f'/auth/recuperar/{uid}/{token}/'


class BaseRecuperacion(BaseSigmap):
    """El limite de solicitudes vive en cache: se limpia entre pruebas."""

    def setUp(self):
        cache.clear()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SolicitudRecuperacionTest(BaseRecuperacion):
    """Escenario 1: correo registrado y activo."""

    def test_camino_feliz_envia_un_correo_con_el_enlace(self):
        respuesta = self.client.post(URL_SOLICITUD, {'email': 'operario@sena.edu.co'})

        self.assertRedirects(respuesta, URL_ENVIADO)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['operario@sena.edu.co'])
        self.assertRegex(correo.body, r'/auth/recuperar/[\w-]+/[\w-]+/')
        self.assertIn('30 minutos', correo.body)

    def test_acepta_el_correo_en_mayusculas(self):
        """El login no distingue mayúsculas: la recuperación tampoco."""
        self.client.post(URL_SOLICITUD, {'email': 'OPERARIO@SENA.EDU.CO'})
        self.assertEqual(len(mail.outbox), 1)

    def test_muestra_el_mensaje_generico(self):
        respuesta = self.client.post(
            URL_SOLICITUD, {'email': 'operario@sena.edu.co'}, follow=True)
        self.assertContains(respuesta, MENSAJE_GENERICO)

    def test_registra_la_solicitud_en_el_historial(self):
        self.client.post(URL_SOLICITUD, {'email': 'operario@sena.edu.co'})
        self.assertTrue(EventoSistema.objects.filter(
            tipo_evento=EventoSistema.Tipo.RECUPERACION_SOLICITADA,
            usuario=self.operario,
        ).exists())

    def test_el_enlace_del_correo_abre_el_formulario(self):
        self.client.post(URL_SOLICITUD, {'email': 'operario@sena.edu.co'})
        ruta = re.search(r'/auth/recuperar/[\w-]+/[\w-]+/', mail.outbox[0].body).group()

        respuesta = self.client.get(ruta, follow=True)
        self.assertContains(respuesta, 'Nueva contraseña')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CorreoNoRegistradoTest(BaseRecuperacion):
    """Escenario 2: no se revela si la cuenta existe o está activa."""

    def test_correo_inexistente_no_envia_pero_responde_igual(self):
        respuesta = self.client.post(
            URL_SOLICITUD, {'email': 'nadie@sena.edu.co'}, follow=True)

        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(respuesta, MENSAJE_GENERICO)
        self.assertEqual(respuesta.redirect_chain[-1][0], URL_ENVIADO)

    def test_cuenta_inactiva_no_recibe_enlace(self):
        """Un usuario desactivado no puede volver a entrar cambiando su clave."""
        Usuario.objects.filter(pk=self.aprendiz.pk).update(estado='inactivo')

        respuesta = self.client.post(
            URL_SOLICITUD, {'email': 'aprendiz@sena.edu.co'}, follow=True)

        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(respuesta, MENSAJE_GENERICO)

    def test_correo_inexistente_no_deja_evento(self):
        self.client.post(URL_SOLICITUD, {'email': 'nadie@sena.edu.co'})
        self.assertFalse(EventoSistema.objects.filter(
            tipo_evento=EventoSistema.Tipo.RECUPERACION_SOLICITADA).exists())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CorreoInvalidoTest(BaseRecuperacion):
    """Escenario 3: campo vacío o sin formato de correo."""

    def test_correo_vacio_muestra_el_error(self):
        respuesta = self.client.post(URL_SOLICITUD, {'email': ''})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Escribe el correo con el que ingresas')
        self.assertEqual(len(mail.outbox), 0)

    def test_correo_mal_escrito_muestra_el_error(self):
        respuesta = self.client.post(URL_SOLICITUD, {'email': 'operario@'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Escribe un correo válido')
        self.assertEqual(len(mail.outbox), 0)


class RestablecimientoExitosoTest(BaseRecuperacion):
    """Escenario 4: enlace vigente y contraseña válida."""

    def _cambiar_clave(self, usuario=None):
        usuario = usuario or self.operario
        # Django cambia el token de la URL por uno en sesión y redirige.
        formulario = self.client.get(_enlace_de(usuario), follow=True)
        return self.client.post(formulario.redirect_chain[-1][0], {
            'new_password1': NUEVA_CLAVE, 'new_password2': NUEVA_CLAVE,
        }, follow=True)

    def test_guarda_la_nueva_contrasena_cifrada(self):
        self._cambiar_clave()

        self.operario.refresh_from_db()
        self.assertTrue(self.operario.check_password(NUEVA_CLAVE))
        self.assertFalse(self.operario.check_password(CLAVE_VALIDA))
        self.assertNotEqual(self.operario.password, NUEVA_CLAVE)

    def test_vuelve_al_login_con_mensaje_de_exito(self):
        respuesta = self._cambiar_clave()

        self.assertEqual(respuesta.redirect_chain[-1][0], '/auth/login/')
        self.assertContains(respuesta, 'Tu contraseña se actualizó')

    def test_no_inicia_sesion_automaticamente(self):
        self._cambiar_clave()
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_permite_entrar_con_la_nueva_contrasena(self):
        self._cambiar_clave()
        respuesta = self.client.post(
            '/auth/login/', {'username': 'operario@sena.edu.co', 'password': NUEVA_CLAVE})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_cierra_las_sesiones_abiertas_de_la_cuenta(self):
        """Si alguien tenía la sesión abierta con la clave vieja, la pierde."""
        otro_navegador = self.client_class()
        otro_navegador.force_login(self.operario)
        self.assertEqual(otro_navegador.get('/alertas/').status_code, 200)  # sesión válida

        self._cambiar_clave()

        respuesta = otro_navegador.get('/alertas/')
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/auth/login/', respuesta.url)

    def test_registra_el_cambio_en_el_historial(self):
        self._cambiar_clave()
        self.assertTrue(EventoSistema.objects.filter(
            tipo_evento=EventoSistema.Tipo.CONTRASENA_RESTABLECIDA,
            usuario=self.operario,
        ).exists())


class ContrasenaNoValidaTest(BaseRecuperacion):
    """Escenario 5: la contraseña no cumple requisitos o no coincide."""

    def _enviar(self, clave1, clave2):
        formulario = self.client.get(_enlace_de(self.operario), follow=True)
        return self.client.post(formulario.redirect_chain[-1][0], {
            'new_password1': clave1, 'new_password2': clave2,
        })

    def test_rechaza_contrasena_corta(self):
        respuesta = self._enviar('abc12', 'abc12')

        self.assertEqual(respuesta.status_code, 200)
        self.operario.refresh_from_db()
        self.assertTrue(self.operario.check_password(CLAVE_VALIDA))

    def test_rechaza_contrasena_solo_numerica(self):
        respuesta = self._enviar('83920174655', '83920174655')
        self.assertEqual(respuesta.status_code, 200)
        self.operario.refresh_from_db()
        self.assertTrue(self.operario.check_password(CLAVE_VALIDA))

    def test_rechaza_contrasenas_que_no_coinciden(self):
        respuesta = self._enviar(NUEVA_CLAVE, 'Otra.Clave.2026')

        self.assertContains(respuesta, 'Las dos contraseñas no coinciden')
        self.operario.refresh_from_db()
        self.assertTrue(self.operario.check_password(CLAVE_VALIDA))


class EnlaceInvalidoTest(BaseRecuperacion):
    """Escenario 6: enlace vencido, ya usado o manipulado."""

    def test_enlace_ya_usado_no_sirve(self):
        enlace = _enlace_de(self.operario)
        formulario = self.client.get(enlace, follow=True)
        self.client.post(formulario.redirect_chain[-1][0], {
            'new_password1': NUEVA_CLAVE, 'new_password2': NUEVA_CLAVE})

        respuesta = self.client.get(enlace, follow=True)

        self.assertContains(respuesta, 'Enlace no válido')
        self.assertContains(respuesta, 'Solicitar un enlace nuevo')

    def test_enlace_vencido_no_sirve(self):
        enlace = _enlace_de(self.operario)
        # Se adelanta el reloj del generador de tokens 31 minutos.
        ahora = default_token_generator._now()
        with mock.patch.object(
                default_token_generator, '_now', return_value=ahora + timedelta(minutes=31)):
            respuesta = self.client.get(enlace, follow=True)

        self.assertContains(respuesta, 'Enlace no válido')

    def test_token_manipulado_no_sirve(self):
        uid = urlsafe_base64_encode(force_bytes(self.operario.pk))
        respuesta = self.client.get(f'/auth/recuperar/{uid}/abc-123/', follow=True)
        self.assertContains(respuesta, 'Enlace no válido')

    def test_enlace_de_cuenta_desactivada_despues_no_cambia_nada(self):
        """
        Caso límite: la cuenta se desactiva con el enlace ya enviado. Django
        valida el token, pero el login sigue bloqueado por estado='inactivo'.
        """
        enlace = _enlace_de(self.operario)
        Usuario.objects.filter(pk=self.operario.pk).update(estado='inactivo')
        formulario = self.client.get(enlace, follow=True)
        self.client.post(formulario.redirect_chain[-1][0], {
            'new_password1': NUEVA_CLAVE, 'new_password2': NUEVA_CLAVE})

        self.client.post(
            '/auth/login/', {'username': 'operario@sena.edu.co', 'password': NUEVA_CLAVE})
        self.assertNotIn('_auth_user_id', self.client.session)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    RECUPERACION_MAX_SOLICITUDES=3,
)
class SolicitudesRepetidasTest(BaseRecuperacion):
    """Escenario 7: límite de 3 solicitudes por correo en la ventana."""

    def test_la_cuarta_solicitud_no_envia_correo(self):
        for _ in range(4):
            respuesta = self.client.post(
                URL_SOLICITUD, {'email': 'operario@sena.edu.co'}, follow=True)

        self.assertEqual(len(mail.outbox), 3)
        self.assertContains(respuesta, MENSAJE_GENERICO)

    def test_el_limite_es_por_correo(self):
        for _ in range(4):
            self.client.post(URL_SOLICITUD, {'email': 'operario@sena.edu.co'})
        self.client.post(URL_SOLICITUD, {'email': 'aprendiz@sena.edu.co'})

        self.assertEqual(mail.outbox[-1].to, ['aprendiz@sena.edu.co'])
        self.assertEqual(len(mail.outbox), 4)


class EnlaceDesdeLoginTest(BaseRecuperacion):
    """El login lleva al formulario de recuperación."""

    def test_login_enlaza_la_recuperacion(self):
        respuesta = self.client.get('/auth/login/')
        self.assertContains(respuesta, f'href="{URL_SOLICITUD}"')

    def test_formulario_de_solicitud_carga(self):
        respuesta = self.client.get(URL_SOLICITUD)
        self.assertContains(respuesta, 'Recuperar contraseña')
