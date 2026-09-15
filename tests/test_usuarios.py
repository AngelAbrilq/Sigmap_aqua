"""
Gestion de cuentas y seguridad de contrasenas.
"""
from apps.usuarios.models import Usuario

from .base import BaseSigmap, CLAVE_VALIDA


class CrearUsuarioTest(BaseSigmap):
    """Alta de cuentas por el Instructor Lider."""

    def setUp(self):
        self.client.force_login(self.instructor)
        self.datos = {
            'nombre_completo': 'Ana Mendoza', 'email': 'ANA@sena.edu.co',
            'rol': self.rol_operario.pk, 'documento_identidad': '1075123456',
            'numero_celular': '300 123 4567', 'numero_whatsapp': '',
            'estado': 'activo',
            'password1': CLAVE_VALIDA, 'password2': CLAVE_VALIDA,
        }

    def test_camino_feliz_crea_la_cuenta(self):
        self.client.post('/usuarios/crear/', self.datos, follow=True)
        self.assertTrue(Usuario.objects.filter(email='ana@sena.edu.co').exists())

    def test_normaliza_el_correo_a_minusculas(self):
        """El email es la credencial de login: no puede depender de mayúsculas."""
        self.client.post('/usuarios/crear/', self.datos, follow=True)
        self.assertTrue(Usuario.objects.filter(email='ana@sena.edu.co').exists())

    def test_la_contrasena_se_guarda_hasheada(self):
        """
        Seguridad: un ModelForm plano guardaria el texto plano en la columna.
        El formulario pasa por set_password().
        """
        self.client.post('/usuarios/crear/', self.datos, follow=True)
        ana = Usuario.objects.get(email='ana@sena.edu.co')
        self.assertNotEqual(ana.password, CLAVE_VALIDA)
        self.assertTrue(ana.password.startswith('pbkdf2_'))
        self.assertTrue(ana.check_password(CLAVE_VALIDA))

    def test_normaliza_el_celular_quitando_separadores(self):
        """'300 123 4567' se guarda como '3001234567'."""
        self.client.post('/usuarios/crear/', self.datos, follow=True)
        ana = Usuario.objects.get(email='ana@sena.edu.co')
        self.assertEqual(ana.numero_celular, '3001234567')

    def test_rechaza_contrasenas_que_no_coinciden(self):
        """Caso de error clasico."""
        self.datos.update(email='otro@sena.edu.co', password2='Otra.Clave.2026')
        self.client.post('/usuarios/crear/', self.datos, follow=True)
        self.assertFalse(Usuario.objects.filter(email='otro@sena.edu.co').exists())

    def test_rechaza_contrasena_debil(self):
        """Caso limite: aplica AUTH_PASSWORD_VALIDATORS."""
        self.datos.update(email='debil@sena.edu.co', password1='123', password2='123')
        self.client.post('/usuarios/crear/', self.datos, follow=True)
        self.assertFalse(Usuario.objects.filter(email='debil@sena.edu.co').exists())

    def test_rechaza_correo_duplicado(self):
        """Caso de error: el email es unico."""
        self.datos.update(email='operario@sena.edu.co')
        antes = Usuario.objects.count()
        self.client.post('/usuarios/crear/', self.datos, follow=True)
        self.assertEqual(Usuario.objects.count(), antes)

    def test_rechaza_celular_con_letras(self):
        """Caso de error de formato."""
        self.datos.update(email='malcel@sena.edu.co', numero_celular='abc123')
        self.client.post('/usuarios/crear/', self.datos, follow=True)
        self.assertFalse(Usuario.objects.filter(email='malcel@sena.edu.co').exists())


class DesactivarUsuarioTest(BaseSigmap):
    """Las cuentas se desactivan, nunca se borran."""

    def setUp(self):
        self.client.force_login(self.instructor)

    def test_nadie_puede_desactivar_su_propia_cuenta(self):
        """
        Caso limite: evita que el unico administrador se deje fuera del
        sistema por accidente.
        """
        self.client.post(f'/usuarios/{self.instructor.pk}/estado/', follow=True)
        self.instructor.refresh_from_db()
        self.assertEqual(self.instructor.estado, 'activo')

    def test_no_deja_un_rol_sin_ningun_usuario_activo(self):
        """
        Caso limite: si se desactiva al unico Operario, nadie recibe las
        notificaciones de alerta.
        """
        self.client.post(f'/usuarios/{self.operario.pk}/estado/', follow=True)
        self.operario.refresh_from_db()
        self.assertEqual(self.operario.estado, 'activo')

    def test_desactiva_cuando_hay_otro_usuario_del_mismo_rol(self):
        """Camino feliz: con relevo disponible, la baja procede."""
        Usuario.objects.create_user('relevo@sena.edu.co', 'Relevo',
                                    CLAVE_VALIDA, rol=self.rol_operario)
        self.client.post(f'/usuarios/{self.operario.pk}/estado/', follow=True)
        self.operario.refresh_from_db()
        self.assertEqual(self.operario.estado, 'inactivo')

    def test_la_cuenta_nunca_se_borra_de_la_base_de_datos(self):
        """Los usuarios quedan referenciados en alertas y reportes."""
        Usuario.objects.create_user('relevo2@sena.edu.co', 'Relevo 2',
                                    CLAVE_VALIDA, rol=self.rol_operario)
        self.client.post(f'/usuarios/{self.operario.pk}/estado/', follow=True)
        self.assertTrue(Usuario.objects.filter(pk=self.operario.pk).exists())


class LoginTest(BaseSigmap):
    """Autenticacion por correo."""

    def test_login_correcto_redirige_al_panel_del_rol(self):
        """Camino feliz: cada rol aterriza en su propio panel."""
        respuesta = self.client.post('/auth/login/', {
            'username': 'operario@sena.edu.co', 'password': CLAVE_VALIDA,
        }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('/operario/', respuesta.redirect_chain[-1][0])

    def test_contrasena_incorrecta_no_autentica(self):
        """Caso de error."""
        respuesta = self.client.post('/auth/login/', {
            'username': 'operario@sena.edu.co', 'password': 'incorrecta',
        })
        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)

    def test_una_cuenta_inactiva_no_puede_entrar(self):
        """Caso limite: la baja logica debe bloquear el acceso."""
        Usuario.objects.create_user('relevo3@sena.edu.co', 'Relevo 3',
                                    CLAVE_VALIDA, rol=self.rol_operario)
        self.operario.estado = 'inactivo'
        self.operario.save(update_fields=['estado'])
        respuesta = self.client.post('/auth/login/', {
            'username': 'operario@sena.edu.co', 'password': CLAVE_VALIDA,
        })
        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)
