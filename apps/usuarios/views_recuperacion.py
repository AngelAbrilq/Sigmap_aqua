"""
Recuperacion de contrasena por correo (RF025 / HU 025).

Se apoya en las vistas de Django, que ya resuelven lo delicado:
- El token del enlace se firma con SECRET_KEY y con el hash de la contrasena
  actual, asi que deja de servir en cuanto la contrasena cambia (un solo uso).
- Vence a los PASSWORD_RESET_TIMEOUT segundos (30 minutos en settings).
- Al cambiar la contrasena, AuthenticationMiddleware detecta que el hash de
  sesion ya no coincide y cierra las sesiones abiertas de esa cuenta.

Lo que se agrega aqui: mensaje identico exista o no el correo, limite de
solicitudes por correo y registro de ambos pasos en el historial de eventos.
"""
import hashlib
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse_lazy

from apps.auditoria.models import EventoSistema
from apps.auditoria.services import ip_de, registrar_evento

from .forms import NuevaContrasenaForm, SolicitudRecuperacionForm

logger = logging.getLogger(__name__)

PLANTILLAS_CORREO = 'usuarios/correos/'


def _clave_limite(email):
    """
    Clave de cache para contar solicitudes de un correo.
    Se guarda el hash, no el correo, para no dejar datos personales en cache.

    :param email: correo normalizado
    :return: str
    """
    return 'recuperacion:' + hashlib.sha256(email.encode('utf-8')).hexdigest()


def supero_limite_solicitudes(email):
    """
    Registra una solicitud y dice si el correo ya paso el limite de la ventana.

    :param email: correo normalizado
    :return: True si se debe bloquear el envio
    """
    clave = _clave_limite(email)
    ventana = settings.RECUPERACION_VENTANA_SEGUNDOS
    # add() solo crea la clave si no existe: el plazo corre desde la primera.
    cache.add(clave, 0, timeout=ventana)
    try:
        intentos = cache.incr(clave)
    except ValueError:
        # La clave expiro entre add() e incr().
        cache.set(clave, 1, timeout=ventana)
        intentos = 1
    return intentos > settings.RECUPERACION_MAX_SOLICITUDES


class SolicitarRecuperacionView(auth_views.PasswordResetView):
    """Paso 1: formulario "¿Olvidaste tu contraseña?"."""

    form_class = SolicitudRecuperacionForm
    template_name = 'usuarios/recuperar_solicitud.html'
    subject_template_name = PLANTILLAS_CORREO + 'recuperar_asunto.txt'
    email_template_name = PLANTILLAS_CORREO + 'recuperar_cuerpo.txt'
    html_email_template_name = PLANTILLAS_CORREO + 'recuperar_cuerpo.html'
    success_url = reverse_lazy('usuarios:recuperar_enviado')

    def form_valid(self, form):
        """
        Envia el enlace solo si el correo esta dentro del limite. En todos los
        casos responde igual, para no revelar si la cuenta existe.
        """
        email = form.cleaned_data['email']

        if supero_limite_solicitudes(email):
            logger.warning('Recuperacion bloqueada por limite de solicitudes')
            return redirect(self.get_success_url())

        for usuario in form.get_users(email):
            registrar_evento(
                EventoSistema.Tipo.RECUPERACION_SOLICITADA,
                f'Solicitud de recuperación de contraseña de {usuario.nombre_completo}',
                usuario=usuario, ip=ip_de(self.request),
            )
        self.extra_email_context = {
            'minutos_vigencia': settings.PASSWORD_RESET_TIMEOUT // 60,
        }
        return super().form_valid(form)


class RecuperacionEnviadaView(auth_views.PasswordResetDoneView):
    """Confirmacion generica despues de enviar el formulario."""

    template_name = 'usuarios/recuperar_enviado.html'

    def get_context_data(self, **kwargs):
        """Agrega la vigencia del enlace para mostrarla al usuario."""
        contexto = super().get_context_data(**kwargs)
        contexto['minutos_vigencia'] = settings.PASSWORD_RESET_TIMEOUT // 60
        return contexto


class ConfirmarRecuperacionView(auth_views.PasswordResetConfirmView):
    """Paso 2: el usuario llega por el enlace y define la nueva contrasena."""

    form_class = NuevaContrasenaForm
    template_name = 'usuarios/recuperar_confirmar.html'
    success_url = reverse_lazy('usuarios:login')
    post_reset_login = False

    def form_valid(self, form):
        """Guarda la contrasena, deja constancia y vuelve al login."""
        respuesta = super().form_valid(form)
        usuario = form.user
        registrar_evento(
            EventoSistema.Tipo.CONTRASENA_RESTABLECIDA,
            f'{usuario.nombre_completo} restableció su contraseña',
            usuario=usuario, nivel=EventoSistema.Nivel.ADVERTENCIA,
            ip=ip_de(self.request),
        )
        messages.success(
            self.request, 'Tu contraseña se actualizó. Ya puedes iniciar sesión.')
        return respuesta
