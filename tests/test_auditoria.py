"""
Registro de eventos del sistema (auditoría) — RF018.

Cubre: el servicio registrar_evento (camino feliz, evento del sistema sin
usuario y truncado), el control de acceso (solo Instructor Líder), y que las
acciones sensibles dejen rastro (login, alta de usuario, cambio de umbrales).
"""
from django.urls import reverse

from apps.auditoria.models import EventoSistema
from apps.auditoria.services import registrar_evento
from apps.monitoreo.forms import TipoParametroForm
from apps.usuarios.models import Usuario

from .base import BaseSigmap, CLAVE_VALIDA


class RegistrarEventoServicioTest(BaseSigmap):
    """El servicio es el único punto de escritura de la auditoría."""

    def test_camino_feliz_persiste_el_evento(self):
        evento = registrar_evento(
            EventoSistema.Tipo.SISTEMA, 'Prueba de auditoría',
            usuario=self.instructor, nivel='info',
        )
        self.assertIsNotNone(evento)
        self.assertEqual(evento.usuario, self.instructor)
        self.assertEqual(EventoSistema.objects.count(), 1)

    def test_evento_sin_usuario_queda_como_del_sistema(self):
        """Una acción automática (sin request) se registra con usuario nulo."""
        evento = registrar_evento(EventoSistema.Tipo.SISTEMA, 'Tarea automática')
        self.assertIsNotNone(evento)
        self.assertIsNone(evento.usuario)

    def test_la_descripcion_se_trunca_a_255(self):
        """Caso límite: una descripción larga no debe reventar la columna."""
        evento = registrar_evento(EventoSistema.Tipo.SISTEMA, 'x' * 500)
        self.assertEqual(len(evento.descripcion), 255)


class AccesoEventosTest(BaseSigmap):
    """RF018: el historial de eventos lo consulta el administrador."""

    def test_instructor_ve_el_historial(self):
        self.client.force_login(self.instructor)
        respuesta = self.client.get(reverse('auditoria:lista'))
        self.assertEqual(respuesta.status_code, 200)

    def test_operario_no_tiene_acceso(self):
        self.client.force_login(self.operario)
        respuesta = self.client.get(reverse('auditoria:lista'))
        self.assertEqual(respuesta.status_code, 302)

    def test_aprendiz_no_tiene_acceso(self):
        self.client.force_login(self.aprendiz)
        respuesta = self.client.get(reverse('auditoria:lista'))
        self.assertEqual(respuesta.status_code, 302)


class HooksAuditoriaTest(BaseSigmap):
    """Las acciones sensibles dejan rastro sin que el usuario haga nada extra."""

    def test_login_registra_evento(self):
        self.client.post('/auth/login/', {
            'username': 'instructor@sena.edu.co', 'password': CLAVE_VALIDA,
        }, follow=True)
        self.assertTrue(
            EventoSistema.objects.filter(
                tipo_evento=EventoSistema.Tipo.SESION_INICIO,
                usuario=self.instructor,
            ).exists()
        )

    def test_crear_usuario_registra_evento(self):
        self.client.force_login(self.instructor)
        self.client.post('/usuarios/crear/', {
            'nombre_completo': 'Ana Mendoza', 'email': 'ana@sena.edu.co',
            'rol': self.rol_operario.pk, 'documento_identidad': '1075123456',
            'numero_celular': '3001234567', 'numero_whatsapp': '',
            'estado': 'activo',
            'password1': CLAVE_VALIDA, 'password2': CLAVE_VALIDA,
        }, follow=True)
        self.assertTrue(Usuario.objects.filter(email='ana@sena.edu.co').exists())
        self.assertTrue(
            EventoSistema.objects.filter(
                tipo_evento=EventoSistema.Tipo.USUARIO_ALTA,
                usuario=self.instructor,
            ).exists()
        )

    def test_cambio_de_umbral_registra_evento(self):
        """El cambio de rangos es la acción de configuración crítica del RF018."""
        self.client.force_login(self.instructor)
        datos = {
            k: ('' if v is None else v)
            for k, v in TipoParametroForm(instance=self.ph).initial.items()
        }
        datos['rango_normal_max'] = '8.6'
        self.client.post(f'/configuraciones/{self.ph.pk}/editar/', datos, follow=True)
        self.assertTrue(
            EventoSistema.objects.filter(
                tipo_evento=EventoSistema.Tipo.CONFIG_UMBRAL,
            ).exists()
        )


class FiltroEventosTest(BaseSigmap):
    """El listado se filtra por tipo (RF018: filtrable por tipo/fecha/piscina)."""

    def test_filtra_por_tipo(self):
        registrar_evento(EventoSistema.Tipo.SISTEMA, 'A', usuario=self.instructor)
        registrar_evento(EventoSistema.Tipo.USUARIO_ALTA, 'B', usuario=self.instructor)
        self.client.force_login(self.instructor)
        respuesta = self.client.get(
            reverse('auditoria:lista'), {'tipo': EventoSistema.Tipo.USUARIO_ALTA}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['eventos']), 1)
