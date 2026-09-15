"""
API de ingesta del ESP32 y motor de alertas.

Es el nucleo del sistema: si esto falla, el proyecto no monitorea nada.
"""
from apps.alertas.models import Alerta, Notificacion
from apps.monitoreo.models import Lectura

from .base import BaseSigmap


class AutenticacionDispositivoTest(BaseSigmap):
    """Solo un nodo con token valido puede escribir lecturas."""

    def test_handshake_con_token_valido(self):
        """Camino feliz: el nodo verifica el enlace antes de cablear sensores."""
        respuesta = self.client.post(
            '/api/v1/dispositivos/handshake/',
            {'mac': 'AA:BB:CC:DD:EE:01', 'firmware': 'v1.0.3'},
            content_type='application/json', **self.cabecera_dispositivo())
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['success'])

    def test_el_handshake_devuelve_los_sensores_esperados(self):
        """El nodo necesita saber que sensores le tocan."""
        respuesta = self.client.post(
            '/api/v1/dispositivos/handshake/', {},
            content_type='application/json', **self.cabecera_dispositivo())
        codigos = {s['codigo_hardware']
                   for s in respuesta.json()['data']['sensores_esperados']}
        self.assertEqual(codigos, {'SEN-PH', 'SEN-OX'})

    def test_token_invalido_devuelve_401(self):
        """Caso de error: credencial desconocida."""
        respuesta = self.enviar_lectura('SEN-PH', 7.0, token='token-inventado')
        self.assertEqual(respuesta.status_code, 401)

    def test_sin_cabecera_authorization_devuelve_401(self):
        """Caso de error: peticion anonima."""
        respuesta = self.client.post(
            '/api/v1/lecturas/', {'lecturas': []}, content_type='application/json')
        self.assertEqual(respuesta.status_code, 401)

    def test_dispositivo_inactivo_devuelve_403(self):
        """Caso limite: token valido pero nodo dado de baja."""
        self.dispositivo.estado = 'inactivo'
        self.dispositivo.save(update_fields=['estado'])
        respuesta = self.enviar_lectura('SEN-PH', 7.0)
        self.assertEqual(respuesta.status_code, 403)


class ClasificacionDeLecturasTest(BaseSigmap):
    """El servidor clasifica, nunca el nodo."""

    def test_lectura_dentro_de_rango_se_marca_normal(self):
        """pH 7.2 está entre 6.5 y 8.5."""
        self.enviar_lectura('SEN-PH', 7.2)
        lectura = Lectura.objects.get(sensor=self.sensor_ph)
        self.assertEqual(lectura.estado_lectura, 'normal')
        self.assertTrue(lectura.dentro_rango)

    def test_lectura_en_zona_de_riesgo_se_marca_riesgo(self):
        """pH 8.8 sale del normal pero cae dentro del rango de riesgo."""
        self.enviar_lectura('SEN-PH', 8.8)
        lectura = Lectura.objects.get(sensor=self.sensor_ph)
        self.assertEqual(lectura.estado_lectura, 'riesgo')

    def test_lectura_fuera_de_todo_rango_se_marca_critica(self):
        """pH 9.5 excede incluso el rango de riesgo."""
        self.enviar_lectura('SEN-PH', 9.5)
        lectura = Lectura.objects.get(sensor=self.sensor_ph)
        self.assertEqual(lectura.estado_lectura, 'critico')

    def test_rechaza_un_sensor_que_no_pertenece_al_dispositivo(self):
        """Caso de error: el nodo no puede escribir sobre otra piscina."""
        respuesta = self.client.post(
            '/api/v1/lecturas/',
            {'lecturas': [{'codigo_hardware': 'SEN-INEXISTENTE', 'valor': 7}]},
            content_type='application/json', **self.cabecera_dispositivo())
        self.assertEqual(Lectura.objects.count(), 0)
        self.assertIn(respuesta.status_code, (200, 201, 400))


class MotorDeAlertasTest(BaseSigmap):
    """
    El eslabon que faltaba: antes las lecturas se guardaban pero nunca se
    generaba una sola alerta.
    """

    def test_una_lectura_normal_no_genera_alerta(self):
        """Camino feliz: agua en condiciones, bandeja vacia."""
        self.enviar_lectura('SEN-PH', 7.2)
        self.assertEqual(Alerta.objects.count(), 0)

    def test_una_lectura_critica_genera_una_alerta_critica(self):
        """Camino principal del motor."""
        self.enviar_lectura('SEN-PH', 9.5)
        alerta = Alerta.objects.get()
        self.assertEqual(alerta.severidad, 'critica')
        self.assertEqual(alerta.estado, 'activa')

    def test_una_lectura_de_riesgo_genera_alerta_de_severidad_media(self):
        """El riesgo avisa, pero no con la misma urgencia."""
        self.enviar_lectura('SEN-PH', 8.8)
        self.assertEqual(Alerta.objects.get().severidad, 'media')

    def test_la_respuesta_de_la_api_informa_cuantas_alertas_genero(self):
        """El nodo puede registrar en su log que el servidor reacciono."""
        respuesta = self.enviar_lectura('SEN-PH', 9.5)
        self.assertEqual(respuesta.json()['data']['alertas_generadas'], 1)

    def test_no_duplica_alertas_del_mismo_problema(self):
        """
        Caso limite: un sensor a 300 s genera 288 lecturas al dia. Sin esta
        regla, un pH alto durante ocho horas crearia 96 alertas identicas.
        """
        self.enviar_lectura('SEN-PH', 9.5)
        self.enviar_lectura('SEN-PH', 9.7)
        self.enviar_lectura('SEN-PH', 9.9)
        self.assertEqual(Alerta.objects.filter(estado='activa').count(), 1)

    def test_cierra_la_alerta_cuando_el_parametro_se_normaliza(self):
        """
        Caso limite critico: sin este cierre automatico, la regla
        anti-duplicados bloquearia para siempre las alertas de ese parametro.
        """
        self.enviar_lectura('SEN-PH', 9.5)
        self.enviar_lectura('SEN-PH', 7.0)
        self.assertEqual(Alerta.objects.filter(estado='activa').count(), 0)
        self.assertEqual(Alerta.objects.filter(estado='resuelta').count(), 1)

    def test_alertas_de_parametros_distintos_conviven(self):
        """Caso limite: el anti-duplicados es por parametro, no por piscina."""
        self.enviar_lectura('SEN-PH', 9.5)
        self.enviar_lectura('SEN-OX', 2.0)
        self.assertEqual(Alerta.objects.filter(estado='activa').count(), 2)


class NotificacionesTest(BaseSigmap):
    """Una alerta describe el problema; la notificacion lo entrega a alguien."""

    def test_alerta_critica_notifica_a_instructor_y_operario(self):
        """Camino feliz de la entrega."""
        self.enviar_lectura('SEN-PH', 9.5)
        destinatarios = set(
            Notificacion.objects.values_list('usuario__email', flat=True))
        self.assertEqual(destinatarios,
                         {'instructor@sena.edu.co', 'operario@sena.edu.co'})

    def test_alerta_media_notifica_solo_al_operario(self):
        """No se despierta al Instructor Lider por un riesgo leve."""
        self.enviar_lectura('SEN-PH', 8.8)
        destinatarios = set(
            Notificacion.objects.values_list('usuario__email', flat=True))
        self.assertEqual(destinatarios, {'operario@sena.edu.co'})

    def test_el_aprendiz_nunca_recibe_notificaciones_operativas(self):
        """Su rol es de consulta: no se le asignan incidencias."""
        self.enviar_lectura('SEN-PH', 9.5)
        self.assertFalse(Notificacion.objects.filter(usuario=self.aprendiz).exists())

    def test_no_notifica_a_usuarios_inactivos(self):
        """Caso limite: una cuenta suspendida no debe recibir avisos."""
        self.operario.estado = 'inactivo'
        self.operario.save(update_fields=['estado'])
        self.enviar_lectura('SEN-PH', 9.5)
        self.assertFalse(Notificacion.objects.filter(usuario=self.operario).exists())


class AtencionDeAlertasTest(BaseSigmap):
    """Flujo reconocer → resolver."""

    def setUp(self):
        self.enviar_lectura('SEN-OX', 2.0)
        self.alerta = Alerta.objects.get(estado='activa')
        self.client.force_login(self.operario)

    def test_reconocer_registra_quien_se_hizo_cargo(self):
        """Reconocer no es resolver: deja constancia mientras sigue abierta."""
        self.client.post(f'/alertas/{self.alerta.pk}/reconocer/', follow=True)
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'reconocida')
        self.assertEqual(self.alerta.usuario_reconocimiento, self.operario)

    def test_no_se_puede_cerrar_sin_describir_la_accion(self):
        """
        Caso de error: una alerta critica cerrada sin explicacion no sirve
        para la trazabilidad del cultivo.
        """
        self.client.post(f'/alertas/{self.alerta.pk}/resolver/',
                         {'accion_tomada': ''}, follow=True)
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'activa')

    def test_resolver_guarda_la_accion_correctiva(self):
        """Camino feliz del cierre."""
        self.client.post(f'/alertas/{self.alerta.pk}/resolver/',
                         {'accion_tomada': 'Se encendió el aireador.'}, follow=True)
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'resuelta')
        self.assertIn('aireador', self.alerta.accion_tomada)

    def test_el_aprendiz_no_puede_atender_alertas(self):
        """Caso de error de permisos."""
        self.client.force_login(self.aprendiz)
        self.client.post(f'/alertas/{self.alerta.pk}/reconocer/', follow=True)
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, 'activa')
