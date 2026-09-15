"""
Navegacion y matriz de permisos.

Cubre la regresion del bucle de redirecciones: una URL registrada en dos apps
hacia que core redirigiera al modulo y el modulo resolviera a la misma URL.
"""
from django.urls import reverse

from .base import BaseSigmap

# Las 11 entradas del navbar, con el nombre de ruta que resuelve cada una.
RUTAS_NAVBAR = {
    'Dashboard': 'core:dashboard',
    'Sensores': 'monitoreo:sensores',
    'Monitoreo': 'monitoreo:monitoreo',
    'Historial': 'monitoreo:historial',
    'Gráficas y reportes': 'reportes:graficas',
    'Comparación de periodos': 'reportes:comparacion',
    'Alertas': 'alertas:listar',
    'IA': 'ia:panel',
    'Usuarios': 'usuarios:listar',
    'Geomembranas': 'piscinas:listar',
    'Configuraciones': 'monitoreo:configuraciones',
}


class RutasVivasTest(BaseSigmap):
    """Ningun enlace del navbar puede estar muerto."""

    def test_todas_las_rutas_del_navbar_resuelven(self):
        """Camino feliz: reverse() no lanza NoReverseMatch en ninguna."""
        for etiqueta, nombre in RUTAS_NAVBAR.items():
            with self.subTest(modulo=etiqueta):
                self.assertTrue(reverse(nombre).startswith('/'))

    def test_el_instructor_abre_los_11_modulos(self):
        """El rol con acceso total no encuentra ningun 404 ni 500."""
        self.client.force_login(self.instructor)
        for etiqueta, nombre in RUTAS_NAVBAR.items():
            with self.subTest(modulo=etiqueta):
                respuesta = self.client.get(reverse(nombre), follow=True)
                self.assertEqual(respuesta.status_code, 200)

    def test_ninguna_ruta_entra_en_bucle_de_redirecciones(self):
        """
        Regresion del ERR_TOO_MANY_REDIRECTS.

        Una cadena de mas de dos saltos delata que dos apps se estan pasando
        la misma URL entre si.
        """
        self.client.force_login(self.instructor)
        for etiqueta, nombre in RUTAS_NAVBAR.items():
            with self.subTest(modulo=etiqueta):
                respuesta = self.client.get(reverse(nombre), follow=True)
                self.assertLessEqual(len(respuesta.redirect_chain), 2)

    def test_la_ruta_de_geomembranas_la_sirve_solo_el_app_piscinas(self):
        """Regresion concreta: core ya no registra /geomembranas/."""
        from apps.core import urls as core_urls
        nombres = {p.name for p in core_urls.urlpatterns}
        self.assertNotIn('geomembranas', nombres)


class AccesoSinSesionTest(BaseSigmap):
    """Ningun modulo debe abrirse sin autenticar."""

    def test_los_modulos_exigen_sesion(self):
        """Caso de error: visitante anonimo."""
        for etiqueta, nombre in RUTAS_NAVBAR.items():
            with self.subTest(modulo=etiqueta):
                respuesta = self.client.get(reverse(nombre))
                self.assertIn(respuesta.status_code, (301, 302))


class PermisosDeLecturaTest(BaseSigmap):
    """Ver un modulo depende de la matriz MODULOS_POR_ROL."""

    def test_el_operario_no_entra_a_gestion_de_usuarios(self):
        """Caso de error: administrar cuentas es del Instructor Lider."""
        self.client.force_login(self.operario)
        respuesta = self.client.get(reverse('usuarios:listar'), follow=True)
        self.assertGreater(len(respuesta.redirect_chain), 0)

    def test_el_aprendiz_no_entra_a_gestion_de_usuarios(self):
        """Caso de error equivalente para el rol de consulta."""
        self.client.force_login(self.aprendiz)
        respuesta = self.client.get(reverse('usuarios:listar'), follow=True)
        self.assertGreater(len(respuesta.redirect_chain), 0)

    def test_el_instructor_si_entra_a_gestion_de_usuarios(self):
        """Camino feliz del rol administrador."""
        self.client.force_login(self.instructor)
        respuesta = self.client.get(reverse('usuarios:listar'))
        self.assertEqual(respuesta.status_code, 200)

    def test_el_aprendiz_consulta_los_modulos_de_analisis(self):
        """Su rol es de consulta: debe poder ver, aunque no escribir."""
        self.client.force_login(self.aprendiz)
        for nombre in ('reportes:graficas', 'reportes:comparacion',
                       'monitoreo:historial', 'ia:panel'):
            with self.subTest(ruta=nombre):
                respuesta = self.client.get(reverse(nombre), follow=True)
                self.assertEqual(respuesta.status_code, 200)


class PermisosDeEscrituraTest(BaseSigmap):
    """
    Ocultar el boton no es control de acceso: la vista revalida en el servidor.
    """

    def setUp(self):
        self.client.force_login(self.aprendiz)

    def test_el_aprendiz_no_crea_geomembranas(self):
        """Caso de error: POST directo saltandose la interfaz."""
        from apps.piscinas.models import Geomembrana
        antes = Geomembrana.objects.count()
        self.client.post('/geomembranas/crear/', {
            'nombre_piscina': 'Intento', 'codigo_identificacion': 'HACK-1',
            'area_m2': '10', 'profundidad_promedio': '1', 'estado': 'activo',
        }, follow=True)
        self.assertEqual(Geomembrana.objects.count(), antes)

    def test_el_aprendiz_no_crea_sensores(self):
        """Mismo caso en el modulo de sensores."""
        from apps.monitoreo.models import Sensor
        antes = Sensor.objects.count()
        self.client.post('/sensores/crear/', {
            'nombre_sensor': 'Intento', 'codigo_hardware': 'HACK-S',
            'geomembrana': self.piscina.pk, 'tipo_parametro': self.ph.pk,
            'intervalo_lectura_segundos': '300', 'estado': 'activo',
        }, follow=True)
        self.assertEqual(Sensor.objects.count(), antes)

    def test_el_aprendiz_no_modifica_los_umbrales_de_alerta(self):
        """
        Caso limite mas sensible: estos rangos deciden cuando hay alerta.
        """
        original = self.ph.rango_normal_max
        self.client.post(f'/configuraciones/{self.ph.pk}/editar/', {
            'nombre_parametro': 'pH', 'unidad_medida': 'pH',
            'rango_normal_min': '0', 'rango_normal_max': '14',
            'rango_riesgo_min': '0', 'rango_riesgo_max': '14',
            'rango_critico_min': '0', 'rango_critico_max': '14',
            'descripcion': '', 'importancia': 'alta', 'estado': 'activo',
        }, follow=True)
        self.ph.refresh_from_db()
        self.assertEqual(self.ph.rango_normal_max, original)


class ProteccionCsrfTest(BaseSigmap):
    """Todo POST del sistema viaja con token CSRF."""

    def test_un_post_sin_token_csrf_es_rechazado(self):
        """Caso de error: peticion forjada desde otro sitio."""
        cliente = self.client_class(enforce_csrf_checks=True)
        cliente.force_login(self.operario)
        respuesta = cliente.post('/geomembranas/crear/', {
            'nombre_piscina': 'Sin CSRF', 'codigo_identificacion': 'CSRF-1',
            'area_m2': '10', 'profundidad_promedio': '1', 'estado': 'activo',
        })
        self.assertEqual(respuesta.status_code, 403)

    def test_los_formularios_renderizan_el_token(self):
        """Camino feliz: el template incluye csrfmiddlewaretoken."""
        self.client.force_login(self.operario)
        respuesta = self.client.get('/geomembranas/')
        self.assertContains(respuesta, 'csrfmiddlewaretoken')
