"""
Predicción con seguimiento: lo que hace al sistema predictivo y no solo opinante.

Lo crítico aquí no es que la IA acierte, sino que el sistema mida honestamente
si acertó. Una métrica de precisión mal calculada es peor que no tener ninguna.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone

from apps.ia.models import AnalisisIA, Prediccion
from apps.ia.services import (
    evaluar_predicciones_vencidas,
    generar_analisis,
    precision_historica,
)
from apps.monitoreo.models import Lectura

from .base import BaseSigmap

# Respuesta simulada del modelo: dos predicciones sobre parámetros medibles.
RESPUESTA_PREDICCION = {
    'diagnostico': 'El pH muestra una tendencia estable al alza.',
    'anomalias': [],
    'recomendaciones': ['Vigilar el pH los próximos días.'],
    'riesgo_proyectado': 'medio',
    'confianza': 72,
    'predicciones': [
        {'parametro': 'pH', 'valor_esperado': 7.5, 'valor_min': 7.2,
         'valor_max': 7.8, 'probabilidad_fuera_de_rango': 15,
         'justificacion': 'La media de los últimos días se mantiene en 7.4.'},
        {'parametro': 'Oxígeno disuelto', 'valor_esperado': 6.5, 'valor_min': 6.0,
         'valor_max': 7.0, 'probabilidad_fuera_de_rango': 10,
         'justificacion': 'Sin variaciones bruscas en el periodo.'},
    ],
}


class GenerarPrediccionesTest(BaseSigmap):
    """La IA produce proyecciones falsables, no frases vagas."""

    def setUp(self):
        for valor in (7.3, 7.4, 7.5):
            self.enviar_lectura('SEN-PH', valor)
        self.enviar_lectura('SEN-OX', 6.4)

    @patch('apps.ia.services._llamar_gemini')
    def test_persiste_una_prediccion_por_parametro(self, simulada):
        """Camino feliz: dos parámetros medibles, dos predicciones."""
        simulada.return_value = RESPUESTA_PREDICCION
        analisis = generar_analisis(self.piscina, tipo='prediccion', dias=7, horizonte=3)
        self.assertEqual(analisis.predicciones.count(), 2)

    @patch('apps.ia.services._llamar_gemini')
    def test_la_fecha_objetivo_respeta_el_horizonte(self, simulada):
        """Un horizonte de 5 días apunta a dentro de 5 días."""
        simulada.return_value = RESPUESTA_PREDICCION
        analisis = generar_analisis(self.piscina, tipo='prediccion', dias=7, horizonte=5)
        esperada = timezone.localdate() + timedelta(days=5)
        self.assertEqual(analisis.predicciones.first().fecha_objetivo, esperada)

    @patch('apps.ia.services._llamar_gemini')
    def test_descarta_predicciones_de_parametros_sin_sensor(self, simulada):
        """
        Caso de error: el modelo proyecta algo que la piscina no mide.

        Guardarla generaría un 'sin_datos' perpetuo que ensucia la métrica.
        """
        simulada.return_value = {
            **RESPUESTA_PREDICCION,
            'predicciones': RESPUESTA_PREDICCION['predicciones'] + [
                {'parametro': 'Amoníaco', 'valor_esperado': 0.2, 'valor_min': 0.1,
                 'valor_max': 0.3, 'justificacion': 'x'},
            ],
        }
        analisis = generar_analisis(self.piscina, tipo='prediccion', horizonte=3)
        nombres = set(analisis.predicciones.values_list(
            'tipo_parametro__nombre_parametro', flat=True))
        self.assertEqual(nombres, {'pH', 'Oxígeno disuelto'})

    @patch('apps.ia.services._llamar_gemini')
    def test_corrige_un_intervalo_invertido(self, simulada):
        """Caso límite: el modelo devuelve min > max."""
        simulada.return_value = {
            **RESPUESTA_PREDICCION,
            'predicciones': [{'parametro': 'pH', 'valor_esperado': 7.5,
                              'valor_min': 7.8, 'valor_max': 7.2,
                              'justificacion': 'x'}],
        }
        analisis = generar_analisis(self.piscina, tipo='prediccion', horizonte=3)
        prediccion = analisis.predicciones.get()
        self.assertLess(prediccion.valor_min, prediccion.valor_max)

    @patch('apps.ia.services._llamar_gemini')
    def test_reencuadra_un_esperado_fuera_de_su_intervalo(self, simulada):
        """
        Caso límite: el valor esperado cae fuera de su propio rango.

        Se recentra en el punto medio; dejarlo fuera haría que la predicción
        se contradijera a sí misma.
        """
        simulada.return_value = {
            **RESPUESTA_PREDICCION,
            'predicciones': [{'parametro': 'pH', 'valor_esperado': 9.9,
                              'valor_min': 7.0, 'valor_max': 8.0,
                              'justificacion': 'x'}],
        }
        analisis = generar_analisis(self.piscina, tipo='prediccion', horizonte=3)
        prediccion = analisis.predicciones.get()
        self.assertTrue(prediccion.valor_min <= prediccion.valor_esperado <= prediccion.valor_max)

    @patch('apps.ia.services._llamar_gemini')
    def test_ignora_predicciones_con_valores_ilegibles(self, simulada):
        """Caso de error: el modelo devuelve texto donde iba un número."""
        simulada.return_value = {
            **RESPUESTA_PREDICCION,
            'predicciones': [{'parametro': 'pH', 'valor_esperado': 'siete',
                              'valor_min': 'x', 'valor_max': 'y',
                              'justificacion': 'x'}],
        }
        analisis = generar_analisis(self.piscina, tipo='prediccion', horizonte=3)
        self.assertEqual(analisis.predicciones.count(), 0)

    @patch('apps.ia.services._llamar_gemini')
    def test_un_diagnostico_no_genera_predicciones(self, simulada):
        """Solo el tipo 'prediccion' proyecta hacia adelante."""
        simulada.return_value = {k: v for k, v in RESPUESTA_PREDICCION.items()
                                 if k != 'predicciones'}
        analisis = generar_analisis(self.piscina, tipo='diagnostico', dias=7)
        self.assertEqual(analisis.predicciones.count(), 0)


class EvaluarPrediccionesTest(BaseSigmap):
    """El contraste contra la realidad."""

    def setUp(self):
        self.ayer = timezone.localdate() - timedelta(days=1)
        self.analisis = AnalisisIA.objects.create(
            geomembrana=self.piscina, tipo_analisis='prediccion',
            datos_entrada={}, resultados_salida={})

    def _crear_prediccion(self, minimo, maximo, esperado, fecha=None):
        """Crea una predicción de pH lista para contrastar."""
        return Prediccion.objects.create(
            analisis=self.analisis, geomembrana=self.piscina,
            tipo_parametro=self.ph,
            valor_esperado=Decimal(str(esperado)),
            valor_min=Decimal(str(minimo)), valor_max=Decimal(str(maximo)),
            horizonte_dias=1, fecha_objetivo=fecha or self.ayer)

    def _medir(self, valor, cuando=None):
        """Registra una lectura real en la fecha objetivo."""
        momento = timezone.make_aware(
            timezone.datetime.combine(cuando or self.ayer, timezone.datetime.min.time())
        ) + timedelta(hours=10)
        Lectura.objects.create(
            sensor=self.sensor_ph, geomembrana=self.piscina, tipo_parametro=self.ph,
            valor_medida=Decimal(str(valor)), estado_lectura='normal',
            dentro_rango=True, timestamp_lectura=momento)

    def test_acierta_cuando_el_valor_real_cae_dentro_del_intervalo(self):
        """Camino feliz."""
        prediccion = self._crear_prediccion(7.2, 7.8, 7.5)
        self._medir(7.4)
        self.assertEqual(prediccion.evaluar(), 'acertada')

    def test_falla_cuando_el_valor_real_queda_fuera(self):
        """Caso de error del modelo, correctamente registrado."""
        prediccion = self._crear_prediccion(7.2, 7.8, 7.5)
        self._medir(8.9)
        self.assertEqual(prediccion.evaluar(), 'fallida')

    def test_el_limite_exacto_cuenta_como_acierto(self):
        """Caso límite: el valor real coincide con el borde del intervalo."""
        prediccion = self._crear_prediccion(7.2, 7.8, 7.5)
        self._medir(7.8)
        self.assertEqual(prediccion.evaluar(), 'acertada')

    def test_sin_lecturas_ese_dia_queda_sin_datos(self):
        """
        Caso límite decisivo: no hubo mediciones.

        Marcarla como fallida castigaría al modelo por un sensor caído.
        """
        prediccion = self._crear_prediccion(7.2, 7.8, 7.5)
        self.assertEqual(prediccion.evaluar(), 'sin_datos')
        self.assertIsNone(prediccion.valor_real)

    def test_contrasta_contra_el_promedio_del_dia(self):
        """Varias lecturas ese día: se compara contra su promedio."""
        prediccion = self._crear_prediccion(7.0, 8.0, 7.5)
        self._medir(7.0)
        self._medir(8.0)
        prediccion.evaluar()
        self.assertEqual(float(prediccion.valor_real), 7.5)

    def test_guarda_el_error_absoluto(self):
        """El error alimenta la métrica de desviación media."""
        prediccion = self._crear_prediccion(7.0, 8.0, 7.5)
        self._medir(7.9)
        prediccion.evaluar()
        self.assertAlmostEqual(float(prediccion.error_absoluto), 0.4, places=2)

    def test_ignora_lecturas_de_otro_dia(self):
        """Caso límite: solo cuenta la fecha objetivo."""
        prediccion = self._crear_prediccion(7.2, 7.8, 7.5)
        self._medir(7.4, cuando=self.ayer - timedelta(days=3))
        self.assertEqual(prediccion.evaluar(), 'sin_datos')

    def test_una_prediccion_futura_no_se_evalua(self):
        """No se contrasta lo que todavía no ha ocurrido."""
        futura = self._crear_prediccion(
            7.2, 7.8, 7.5, fecha=timezone.localdate() + timedelta(days=3))
        evaluar_predicciones_vencidas()
        futura.refresh_from_db()
        self.assertEqual(futura.estado, 'pendiente')

    def test_la_evaluacion_masiva_es_idempotente(self):
        """Correr el comando dos veces no altera los resultados."""
        self._crear_prediccion(7.2, 7.8, 7.5)
        self._medir(7.4)
        primera = evaluar_predicciones_vencidas()
        segunda = evaluar_predicciones_vencidas()
        self.assertEqual(primera['acertada'], 1)
        self.assertEqual(sum(segunda.values()), 0)


class PrecisionHistoricaTest(BaseSigmap):
    """La métrica que se defiende en la sustentación."""

    def setUp(self):
        self.ayer = timezone.localdate() - timedelta(days=1)
        self.analisis = AnalisisIA.objects.create(
            geomembrana=self.piscina, tipo_analisis='prediccion',
            datos_entrada={}, resultados_salida={})

    def _prediccion(self, estado, error=None):
        """Crea una predicción ya evaluada con el estado dado."""
        return Prediccion.objects.create(
            analisis=self.analisis, geomembrana=self.piscina,
            tipo_parametro=self.ph, valor_esperado=Decimal('7.5'),
            valor_min=Decimal('7.2'), valor_max=Decimal('7.8'),
            horizonte_dias=1, fecha_objetivo=self.ayer, estado=estado,
            valor_real=Decimal('7.4') if estado != 'sin_datos' else None,
            error_absoluto=Decimal(str(error)) if error is not None else None)

    def test_calcula_la_tasa_de_acierto(self):
        """3 acertadas de 4 evaluadas = 75 %."""
        for _ in range(3):
            self._prediccion('acertada', 0.1)
        self._prediccion('fallida', 0.9)
        self.assertEqual(precision_historica(self.piscina)['tasa_acierto'], 75.0)

    def test_las_sin_datos_no_entran_en_el_porcentaje(self):
        """
        Regla central de honestidad de la métrica.

        1 acertada + 1 fallida + 5 sin datos debe dar 50 %, no 14 % ni 86 %.
        """
        self._prediccion('acertada', 0.1)
        self._prediccion('fallida', 0.9)
        for _ in range(5):
            self._prediccion('sin_datos')

        stats = precision_historica(self.piscina)
        self.assertEqual(stats['tasa_acierto'], 50.0)
        self.assertEqual(stats['evaluadas'], 2)
        self.assertEqual(stats['sin_datos'], 5)

    def test_las_pendientes_tampoco_entran(self):
        """Una predicción sin contrastar no puede contar como acierto."""
        self._prediccion('acertada', 0.1)
        self._prediccion('pendiente')
        stats = precision_historica(self.piscina)
        self.assertEqual(stats['tasa_acierto'], 100.0)
        self.assertEqual(stats['evaluadas'], 1)

    def test_sin_evaluadas_la_tasa_es_none_y_no_cero(self):
        """
        Caso límite: 0 % sugeriría que el modelo falla siempre; None dice
        que todavía no se sabe. No son lo mismo.
        """
        self._prediccion('pendiente')
        self.assertIsNone(precision_historica(self.piscina)['tasa_acierto'])

    def test_desglosa_el_acierto_por_parametro(self):
        """Permite ver qué parámetro predice peor."""
        self._prediccion('acertada', 0.1)
        self._prediccion('fallida', 0.5)
        detalle = precision_historica(self.piscina)['por_parametro']
        self.assertEqual(len(detalle), 1)
        self.assertEqual(detalle[0]['parametro'], 'pH')
        self.assertEqual(detalle[0]['tasa_acierto'], 50.0)


class PanelPrediccionesTest(BaseSigmap):
    """La interfaz del seguimiento."""

    def setUp(self):
        self.client.force_login(self.instructor)

    def test_el_panel_abre_sin_predicciones(self):
        """Caso límite: sistema recién instalado."""
        respuesta = self.client.get('/ai/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Seguimiento de predicciones')

    def test_el_boton_de_contrastar_solo_aparece_si_hay_vencidas(self):
        """No se ofrece una acción que no haría nada."""
        respuesta = self.client.get('/ai/')
        self.assertNotContains(respuesta, 'ia:evaluar')

    def test_contrastar_evalua_las_vencidas(self):
        """Camino feliz del botón manual."""
        analisis = AnalisisIA.objects.create(
            geomembrana=self.piscina, tipo_analisis='prediccion',
            datos_entrada={}, resultados_salida={})
        Prediccion.objects.create(
            analisis=analisis, geomembrana=self.piscina, tipo_parametro=self.ph,
            valor_esperado=Decimal('7.5'), valor_min=Decimal('7.2'),
            valor_max=Decimal('7.8'), horizonte_dias=1,
            fecha_objetivo=timezone.localdate() - timedelta(days=1))

        self.client.post('/ai/evaluar/', {'piscina': self.piscina.pk}, follow=True)
        self.assertEqual(Prediccion.objects.get().estado, 'sin_datos')

    def test_el_aprendiz_no_puede_contrastar(self):
        """Caso de error de permisos."""
        analisis = AnalisisIA.objects.create(
            geomembrana=self.piscina, tipo_analisis='prediccion',
            datos_entrada={}, resultados_salida={})
        prediccion = Prediccion.objects.create(
            analisis=analisis, geomembrana=self.piscina, tipo_parametro=self.ph,
            valor_esperado=Decimal('7.5'), valor_min=Decimal('7.2'),
            valor_max=Decimal('7.8'), horizonte_dias=1,
            fecha_objetivo=timezone.localdate() - timedelta(days=1))

        self.client.force_login(self.aprendiz)
        self.client.post('/ai/evaluar/', {'piscina': self.piscina.pk}, follow=True)
        prediccion.refresh_from_db()
        self.assertEqual(prediccion.estado, 'pendiente')
