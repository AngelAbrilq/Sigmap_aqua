"""
API REST de la app móvil.

Es la superficie que va a exponer el sistema a internet cuando la app salga
del laboratorio: el RBAC y la autenticación se prueban aquí con la misma
severidad que en la web.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.alertas.models import Alerta, Notificacion
from apps.ia.models import AnalisisIA, Prediccion

from .base import BaseSigmap, CLAVE_VALIDA

BASE = '/api/v1/movil'


class BaseAPI(BaseSigmap):
    """Cliente DRF y utilidades de autenticación."""

    def setUp(self):
        self.api = APIClient()
        # DRF guarda el historial del throttle en la caché. Sin limpiarla, las
        # propias pruebas agotan el límite de login (8/min) y las que corren
        # después reciben 429 en vez de su token. El throttle sigue activo:
        # hay una prueba dedicada más abajo que lo verifica.
        cache.clear()

    def autenticar(self, usuario):
        """
        Obtiene un access token real por el endpoint de login.

        Se usa el login completo en vez de force_authenticate para que las
        pruebas recorran el mismo camino que la app: si el login se rompe,
        estas pruebas se caen, que es justo lo que se quiere.
        """
        respuesta = self.api.post(f'{BASE}/auth/token/', {
            'email': usuario.email, 'password': CLAVE_VALIDA}, format='json')
        token = respuesta.json()['data']['access']
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return token


class LoginTest(BaseAPI):
    """Autenticación JWT."""

    def test_login_devuelve_access_refresh_y_usuario(self):
        """Camino feliz."""
        respuesta = self.api.post(f'{BASE}/auth/token/', {
            'email': 'operario@sena.edu.co', 'password': CLAVE_VALIDA}, format='json')
        cuerpo = respuesta.json()

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(cuerpo['success'])
        self.assertIn('access', cuerpo['data'])
        self.assertIn('refresh', cuerpo['data'])
        self.assertEqual(cuerpo['data']['usuario']['rol'], 'Operario')

    def test_el_token_nunca_incluye_la_contrasena(self):
        """Seguridad: ningún serializer expone el hash."""
        respuesta = self.api.post(f'{BASE}/auth/token/', {
            'email': 'operario@sena.edu.co', 'password': CLAVE_VALIDA}, format='json')
        self.assertNotIn('password', respuesta.content.decode())

    def test_credenciales_incorrectas_dan_401_con_formato_estandar(self):
        """Caso de error: el cliente no debe encontrar otra forma de respuesta."""
        respuesta = self.api.post(f'{BASE}/auth/token/', {
            'email': 'operario@sena.edu.co', 'password': 'incorrecta'}, format='json')
        cuerpo = respuesta.json()

        self.assertEqual(respuesta.status_code, 401)
        self.assertFalse(cuerpo['success'])
        self.assertEqual(cuerpo['message'], 'Correo o contraseña incorrectos.')

    def test_una_cuenta_inactiva_no_obtiene_token(self):
        """Caso límite: la baja lógica debe cerrar también la puerta del móvil."""
        from apps.usuarios.models import Usuario
        Usuario.objects.filter(pk=self.operario.pk).update(estado='inactivo')

        respuesta = self.api.post(f'{BASE}/auth/token/', {
            'email': 'operario@sena.edu.co', 'password': CLAVE_VALIDA}, format='json')
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn('inactiva', respuesta.json()['message'].lower())

    def test_una_cuenta_desactivada_despues_del_login_pierde_el_acceso(self):
        """
        Caso límite importante: el token sigue siendo criptográficamente
        válido hasta que expire. PermisoModulo revalida el estado en cada
        petición, así que la baja surte efecto de inmediato.
        """
        self.autenticar(self.operario)
        from apps.usuarios.models import Usuario
        Usuario.objects.filter(pk=self.operario.pk).update(estado='inactivo')

        respuesta = self.api.get(f'{BASE}/geomembranas/')
        self.assertEqual(respuesta.status_code, 403)

    def test_sin_token_los_datos_no_se_entregan(self):
        """Caso de error: petición anónima."""
        self.assertEqual(self.api.get(f'{BASE}/geomembranas/').status_code, 401)

    def test_un_token_inventado_devuelve_401(self):
        """Caso de error: credencial forjada."""
        self.api.credentials(HTTP_AUTHORIZATION='Bearer token.falso.aqui')
        self.assertEqual(self.api.get(f'{BASE}/geomembranas/').status_code, 401)


class RefrescoYLogoutTest(BaseAPI):
    """Rotación de tokens y cierre de sesión real."""

    def _tokens(self):
        respuesta = self.api.post(f'{BASE}/auth/token/', {
            'email': 'operario@sena.edu.co', 'password': CLAVE_VALIDA}, format='json')
        return respuesta.json()['data']

    def test_el_refresh_entrega_un_access_nuevo(self):
        """Camino feliz de la renovación silenciosa."""
        tokens = self._tokens()
        respuesta = self.api.post(f'{BASE}/auth/refresh/',
                                  {'refresh': tokens['refresh']}, format='json')
        cuerpo = respuesta.json()

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(cuerpo['success'])
        self.assertIn('access', cuerpo['data'])

    def test_el_refresh_rota_y_el_anterior_deja_de_servir(self):
        """
        Seguridad: ROTATE + BLACKLIST. Un refresh robado sirve una sola vez.
        """
        tokens = self._tokens()
        primero = tokens['refresh']

        self.api.post(f'{BASE}/auth/refresh/', {'refresh': primero}, format='json')
        segundo = self.api.post(f'{BASE}/auth/refresh/',
                                {'refresh': primero}, format='json')

        self.assertEqual(segundo.status_code, 401)

    def test_un_refresh_invalido_devuelve_401_no_500(self):
        """Caso de error: basura en el campo."""
        respuesta = self.api.post(f'{BASE}/auth/refresh/',
                                  {'refresh': 'no-es-un-token'}, format='json')
        self.assertEqual(respuesta.status_code, 401)
        self.assertFalse(respuesta.json()['success'])

    def test_el_logout_invalida_el_refresh(self):
        """
        Cerrar sesión de verdad: sin blacklist, solo se borraría el token del
        teléfono y una copia seguiría funcionando.
        """
        tokens = self._tokens()
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        salida = self.api.post(f'{BASE}/auth/logout/',
                               {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(salida.status_code, 200)

        reintento = self.api.post(f'{BASE}/auth/refresh/',
                                  {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(reintento.status_code, 401)


class PerfilTest(BaseAPI):
    """auth/me/ arma el menú de la app."""

    def test_devuelve_el_rol_y_los_modulos_permitidos(self):
        self.autenticar(self.operario)
        cuerpo = self.api.get(f'{BASE}/auth/me/').json()

        self.assertEqual(cuerpo['data']['rol'], 'Operario')
        self.assertIn('geomembranas', cuerpo['data']['modulos']['lectura'])

    def test_el_instructor_tiene_acceso_total(self):
        """La matriz usa None para 'todos': se traduce explícitamente."""
        self.autenticar(self.instructor)
        modulos = self.api.get(f'{BASE}/auth/me/').json()['data']['modulos']

        self.assertEqual(modulos['lectura'], 'todos')
        self.assertEqual(modulos['escritura'], 'todos')

    def test_el_aprendiz_no_declara_permisos_de_escritura(self):
        """Su rol es de consulta."""
        self.autenticar(self.aprendiz)
        modulos = self.api.get(f'{BASE}/auth/me/').json()['data']['modulos']
        self.assertEqual(modulos['escritura'], [])


class GeomembranasAPITest(BaseAPI):
    """Listado, detalle y estado actual."""

    def test_el_listado_pagina_y_respeta_el_contrato(self):
        self.autenticar(self.operario)
        cuerpo = self.api.get(f'{BASE}/geomembranas/').json()

        self.assertTrue(cuerpo['success'])
        self.assertIn('resultados', cuerpo['data'])
        self.assertIn('total', cuerpo['data'])

    def test_el_detalle_trae_la_ficha_completa(self):
        self.autenticar(self.operario)
        datos = self.api.get(f'{BASE}/geomembranas/{self.piscina.pk}/').json()['data']

        self.assertEqual(datos['codigo_identificacion'], 'GEO-TEST')
        self.assertIn('material', datos)

    def test_las_ultimas_lecturas_incluyen_sensores_sin_datos(self):
        """
        Caso límite decisivo: un sensor que no ha reportado debe aparecer en
        gris, no desaparecer. Omitirlo escondería justo lo que hay que ver.
        """
        self.autenticar(self.operario)
        self.enviar_lectura('SEN-PH', 7.2)

        datos = self.api.get(
            f'{BASE}/geomembranas/{self.piscina.pk}/ultimas-lecturas/').json()['data']
        por_parametro = {p['parametro']: p for p in datos['parametros']}

        self.assertEqual(por_parametro['pH']['valor_medida'], '7.2000')
        self.assertIsNone(por_parametro['Oxígeno disuelto']['valor_medida'])
        self.assertEqual(por_parametro['Oxígeno disuelto']['estado_lectura'], 'sin_datos')
        self.assertEqual(por_parametro['pH']['parametro_id'], self.ph.pk)

    def test_los_valores_decimales_viajan_como_texto(self):
        """
        DRF serializa DecimalField como string para no perder precisión al
        pasar por float. El cliente Flutter lo espera así.
        """
        self.autenticar(self.operario)
        self.enviar_lectura('SEN-PH', 7.25)

        datos = self.api.get(
            f'{BASE}/geomembranas/{self.piscina.pk}/ultimas-lecturas/').json()['data']
        # Se busca por nombre, no por indice: el orden alfabetico pone
        # 'Oxigeno disuelto' antes que 'pH', y ese sensor no ha reportado.
        por_parametro = {p['parametro']: p for p in datos['parametros']}
        self.assertIsInstance(por_parametro['pH']['valor_medida'], str)
        self.assertEqual(por_parametro['pH']['valor_medida'], '7.2500')


class HistorialAPITest(BaseAPI):
    """Filtros validados antes de tocar el ORM."""

    def setUp(self):
        super().setUp()
        for valor in (7.0, 7.2, 7.4):
            self.enviar_lectura('SEN-PH', valor)
        self.autenticar(self.operario)

    def test_devuelve_las_lecturas_paginadas(self):
        cuerpo = self.api.get(f'{BASE}/lecturas/').json()
        self.assertEqual(cuerpo['data']['total'], 3)

    def test_filtra_por_geomembrana_y_parametro(self):
        cuerpo = self.api.get(
            f'{BASE}/lecturas/?geomembrana={self.piscina.pk}&parametro={self.ph.pk}').json()
        self.assertEqual(cuerpo['data']['total'], 3)

    def test_page_size_permite_pedir_mas_puntos_para_la_grafica(self):
        """La app pide hasta 500 puntos; sin page_size_query_param llegarían 20."""
        datos = self.api.get(f'{BASE}/lecturas/?page_size=2').json()['data']
        self.assertLessEqual(len(datos['resultados']), 2)

    def test_page_size_tiene_tope(self):
        """Caso límite: nadie descarga la tabla completa de un solo golpe."""
        from apps.api_movil.paginacion import PaginacionMovil
        self.assertEqual(PaginacionMovil.max_page_size, 500)

    def test_cada_lectura_trae_el_id_del_parametro(self):
        """La app usa parametro_id para abrir el historial de ese parámetro."""
        datos = self.api.get(f'{BASE}/lecturas/').json()['data']
        self.assertIn('parametro_id', datos['resultados'][0])

    def test_una_fecha_malformada_da_400_y_no_revienta(self):
        """
        Caso de error: sin el serializer de filtros, esto llegaría al ORM y
        lanzaría un ValidationError crudo a mitad de la consulta.
        """
        respuesta = self.api.get(f'{BASE}/lecturas/?desde=ayer')
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()['success'])

    def test_un_rango_invertido_se_rechaza(self):
        """Caso límite: desde posterior a hasta."""
        respuesta = self.api.get(f'{BASE}/lecturas/?desde=2026-09-10&hasta=2026-09-01')
        self.assertEqual(respuesta.status_code, 400)


class AlertasAPITest(BaseAPI):
    """El módulo que justifica la app: atender desde el campo."""

    def setUp(self):
        super().setUp()
        self.enviar_lectura('SEN-PH', 9.5)
        self.alerta = Alerta.objects.get(estado='activa')

    def test_el_listado_muestra_las_activas_por_defecto(self):
        self.autenticar(self.operario)
        cuerpo = self.api.get(f'{BASE}/alertas/').json()
        self.assertEqual(cuerpo['data']['total'], 1)

    def test_el_operario_reconoce_una_alerta(self):
        """Camino feliz."""
        self.autenticar(self.operario)
        respuesta = self.api.post(f'{BASE}/alertas/{self.alerta.pk}/reconocer/')

        self.alerta.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.alerta.estado, 'reconocida')
        self.assertEqual(self.alerta.usuario_reconocimiento, self.operario)

    def test_reconocer_dos_veces_devuelve_409(self):
        """Caso límite: la acción ya no aplica."""
        self.autenticar(self.operario)
        self.api.post(f'{BASE}/alertas/{self.alerta.pk}/reconocer/')
        segunda = self.api.post(f'{BASE}/alertas/{self.alerta.pk}/reconocer/')
        self.assertEqual(segunda.status_code, 409)

    def test_resolver_exige_la_accion_tomada(self):
        """
        Caso de error: una alerta crítica cerrada sin explicación no sirve
        para la trazabilidad del cultivo.
        """
        self.autenticar(self.operario)
        respuesta = self.api.post(f'{BASE}/alertas/{self.alerta.pk}/resolver/',
                                  {'accion_tomada': ''}, format='json')

        self.alerta.refresh_from_db()
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.alerta.estado, 'activa')

    def test_resolver_guarda_la_accion(self):
        """Camino feliz del cierre."""
        self.autenticar(self.operario)
        self.api.post(f'{BASE}/alertas/{self.alerta.pk}/resolver/',
                      {'accion_tomada': 'Se hizo recambio parcial de agua.'},
                      format='json')

        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'resuelta')
        self.assertIn('recambio', self.alerta.accion_tomada)

    def test_el_aprendiz_ve_las_alertas(self):
        """Su rol es de consulta: sí puede mirar."""
        self.autenticar(self.aprendiz)
        self.assertEqual(self.api.get(f'{BASE}/alertas/').status_code, 200)

    def test_el_aprendiz_no_puede_resolver_aunque_fuerce_la_peticion(self):
        """
        Caso de error crítico: ocultar el botón en la app no es control de
        acceso. El backend es la autoridad.
        """
        self.autenticar(self.aprendiz)
        respuesta = self.api.post(f'{BASE}/alertas/{self.alerta.pk}/resolver/',
                                  {'accion_tomada': 'Intento'}, format='json')

        self.alerta.refresh_from_db()
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.alerta.estado, 'activa')


class NotificacionesAPITest(BaseAPI):
    """Bandeja personal."""

    def setUp(self):
        super().setUp()
        self.enviar_lectura('SEN-PH', 9.5)
        self.autenticar(self.operario)

    def test_cada_usuario_ve_solo_sus_notificaciones(self):
        """Seguridad: la bandeja es personal, no global."""
        cuerpo = self.api.get(f'{BASE}/notificaciones/').json()
        total_propias = Notificacion.objects.filter(usuario=self.operario).count()
        self.assertEqual(len(cuerpo['data']['resultados']), total_propias)

    def test_marcar_leidas_actualiza_solo_las_propias(self):
        """Caso límite: no debe tocar la bandeja del Instructor."""
        antes_instructor = Notificacion.objects.filter(
            usuario=self.instructor, leida=False).count()

        self.api.post(f'{BASE}/notificaciones/leidas/')

        self.assertEqual(
            Notificacion.objects.filter(usuario=self.operario, leida=False).count(), 0)
        self.assertEqual(
            Notificacion.objects.filter(usuario=self.instructor, leida=False).count(),
            antes_instructor)


class PrediccionesAPITest(BaseAPI):
    """Predicciones con su precisión, para que el operario sepa cuánto confiar."""

    def setUp(self):
        super().setUp()
        analisis = AnalisisIA.objects.create(
            geomembrana=self.piscina, tipo_analisis='prediccion',
            datos_entrada={}, resultados_salida={})
        Prediccion.objects.create(
            analisis=analisis, geomembrana=self.piscina, tipo_parametro=self.ph,
            valor_esperado=Decimal('7.5'), valor_min=Decimal('7.2'),
            valor_max=Decimal('7.8'), horizonte_dias=3,
            fecha_objetivo=timezone.localdate() + timedelta(days=3))
        self.autenticar(self.operario)

    def test_devuelve_las_predicciones_con_la_precision_del_modelo(self):
        """
        Una predicción sin su porcentaje de acierto es una opinión: ambas
        cosas viajan juntas.
        """
        cuerpo = self.api.get(f'{BASE}/predicciones/').json()

        self.assertEqual(cuerpo['data']['total'], 1)
        self.assertIn('precision', cuerpo['data'])
        self.assertIn('tasa_acierto', cuerpo['data']['precision'])


class SeguridadAPITest(BaseAPI):
    """Lo que la API nunca debe dejar salir."""

    def test_ningun_endpoint_expone_el_token_de_un_dispositivo(self):
        """
        Seguridad: con el token de un ESP32, cualquiera podría inyectar
        lecturas falsas en el sistema.
        """
        self.autenticar(self.instructor)

        for ruta in ('/geomembranas/', f'/geomembranas/{self.piscina.pk}/',
                     f'/geomembranas/{self.piscina.pk}/ultimas-lecturas/'):
            with self.subTest(ruta=ruta):
                contenido = self.api.get(f'{BASE}{ruta}').content.decode()
                self.assertNotIn(self.dispositivo.token, contenido)

    def test_la_api_del_firmware_sigue_respondiendo_su_formato(self):
        """
        Regresión: el EXCEPTION_HANDLER es global y también afecta a la API
        de los ESP32. El firmware no debe notar el cambio.
        """
        respuesta = self.client.post(
            '/api/v1/lecturas/', {'lecturas': []},
            content_type='application/json',
            HTTP_AUTHORIZATION='Device token-invalido')

        cuerpo = respuesta.json()
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn('success', cuerpo)
        self.assertIn('message', cuerpo)
        self.assertFalse(cuerpo['success'])


class ThrottleLoginTest(BaseAPI):
    """
    El login es el único endpoint público de la API.

    Sin límite de intentos sería un oráculo de fuerza bruta contra las
    contraseñas de todo el equipo.
    """

    def test_demasiados_intentos_devuelven_429(self):
        """Caso límite: se supera la tasa configurada."""
        credenciales = {'email': 'operario@sena.edu.co', 'password': 'incorrecta'}

        ultimo = None
        for _ in range(12):
            ultimo = self.api.post(f'{BASE}/auth/token/', credenciales, format='json')
            if ultimo.status_code == 429:
                break

        self.assertEqual(ultimo.status_code, 429)
        self.assertFalse(ultimo.json()['success'])
