"""
Persistencia de los analisis generados por IA (tabla `analisis_ia` del ERD).

Cada analisis guarda los datos con los que se genero y la salida cruda del
modelo. Sin eso, una recomendacion no es auditable: el Instructor Lider no
puede saber sobre que evidencia se emitio.
"""
from django.db import models


class AnalisisIA(models.Model):
    TIPOS = [
        ('diagnostico', 'Diagnóstico del estado actual'),
        ('prediccion', 'Predicción de riesgo'),
        ('recomendacion', 'Recomendación operativa'),
    ]
    ESTADOS = [
        ('generado', 'Generado'),
        ('validado', 'Validado'),
        ('descartado', 'Descartado'),
        ('implementado', 'Implementado'),
    ]

    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT,
        related_name='analisis_ia', verbose_name='Piscina'
    )
    tipo_analisis = models.CharField('Tipo', max_length=15, choices=TIPOS,
                                     default='diagnostico')

    # Evidencia: lo que se le envio al modelo.
    datos_entrada = models.JSONField('Datos de entrada', default=dict)
    # Salida estructurada que devolvio el modelo.
    resultados_salida = models.JSONField('Resultados', default=dict)

    descripcion_analisis = models.TextField('Análisis', blank=True)
    recomendaciones = models.TextField('Recomendaciones', blank=True)
    anomalias_detectadas = models.JSONField('Anomalías', default=list, blank=True)

    confianza = models.DecimalField(
        'Confianza', max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='0 a 100. La declara el modelo, no es una medida estadística.'
    )
    modelo_usado = models.CharField('Modelo', max_length=60, blank=True)

    estado = models.CharField(max_length=15, choices=ESTADOS, default='generado')

    validado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        related_name='analisis_validados', null=True, blank=True
    )
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    fecha_validacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'analisis_ia'
        verbose_name = 'Análisis de IA'
        verbose_name_plural = 'Análisis de IA'
        ordering = ['-fecha_generacion']
        indexes = [
            models.Index(fields=['geomembrana', '-fecha_generacion'],
                         name='idx_ia_geo_fecha'),
            models.Index(fields=['estado'], name='idx_ia_estado'),
        ]

    def __str__(self):
        return f'{self.get_tipo_analisis_display()} · {self.geomembrana_id}'

    @property
    def nivel_confianza(self):
        """Clasifica la confianza declarada para pintarla con color."""
        if self.confianza is None:
            return 'desconocida'
        if self.confianza >= 75:
            return 'alta'
        if self.confianza >= 50:
            return 'media'
        return 'baja'


class PrediccionQuerySet(models.QuerySet):
    """Filtros de negocio reutilizados por el panel y el comando de evaluación."""

    def pendientes(self):
        """Predicciones cuya ventana objetivo todavía no vence."""
        return self.filter(estado='pendiente')

    def vencidas(self):
        """
        Pendientes cuya fecha objetivo ya pasó: listas para contrastar.

        Se evalúan al día siguiente de la fecha objetivo para que la ventana
        completa tenga lecturas; evaluar el mismo día dejaría fuera las
        mediciones de la tarde.
        """
        from django.utils import timezone
        return self.pendientes().filter(fecha_objetivo__lt=timezone.localdate())

    def evaluadas(self):
        """Predicciones que ya se contrastaron contra datos reales."""
        return self.filter(estado__in=['acertada', 'fallida'])

    def con_relaciones(self):
        """Evita el N+1 al listar: se muestran parámetro y piscina en cada fila."""
        return self.select_related('tipo_parametro', 'geomembrana', 'analisis')


class Prediccion(models.Model):
    """
    Una proyección concreta y falsable sobre un parámetro del agua.

    Es lo que separa un sistema predictivo de uno que solo opina: la IA no
    dice "el pH podría subir", dice "el pH estará entre 7.8 y 8.3 el día X".
    Cuando llega ese día, el sistema compara contra lo que midieron los
    sensores y deja constancia de si acertó.

    Sin este contraste, ninguna recomendación de IA es auditable.
    """

    ESTADOS = [
        ('pendiente', 'Pendiente de evaluar'),
        ('acertada', 'Acertada'),
        ('fallida', 'Fallida'),
        ('sin_datos', 'Sin datos para evaluar'),
    ]

    analisis = models.ForeignKey(
        AnalisisIA, on_delete=models.CASCADE,
        related_name='predicciones', verbose_name='Análisis de origen'
    )
    # Desnormalizados a propósito: el panel filtra por piscina y parámetro sin
    # tener que pasar por analisis_ia en cada consulta.
    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT,
        related_name='predicciones', verbose_name='Piscina'
    )
    tipo_parametro = models.ForeignKey(
        'monitoreo.TipoParametro', on_delete=models.PROTECT,
        related_name='predicciones', verbose_name='Parámetro'
    )

    # --- Lo que se predijo ---
    valor_esperado = models.DecimalField(
        'Valor esperado', max_digits=10, decimal_places=4)
    valor_min = models.DecimalField(
        'Mínimo previsto', max_digits=10, decimal_places=4)
    valor_max = models.DecimalField(
        'Máximo previsto', max_digits=10, decimal_places=4)
    probabilidad_fuera_rango = models.PositiveSmallIntegerField(
        'Probabilidad de salirse de rango (%)', null=True, blank=True)
    justificacion = models.TextField('Justificación', blank=True)

    # --- Ventana objetivo ---
    horizonte_dias = models.PositiveSmallIntegerField('Horizonte (días)', default=3)
    fecha_objetivo = models.DateField(
        'Fecha objetivo',
        help_text='Día cuyo promedio real se comparará contra esta predicción.')
    fecha_generacion = models.DateTimeField(auto_now_add=True)

    # --- Resultado del contraste ---
    estado = models.CharField(max_length=12, choices=ESTADOS, default='pendiente')
    valor_real = models.DecimalField(
        'Valor real medido', max_digits=10, decimal_places=4, null=True, blank=True)
    error_absoluto = models.DecimalField(
        'Error absoluto', max_digits=10, decimal_places=4, null=True, blank=True)
    lecturas_evaluadas = models.PositiveIntegerField(
        'Lecturas contrastadas', null=True, blank=True)
    fecha_evaluacion = models.DateTimeField(null=True, blank=True)

    objects = PrediccionQuerySet.as_manager()

    class Meta:
        db_table = 'predicciones_ia'
        verbose_name = 'Predicción'
        verbose_name_plural = 'Predicciones'
        ordering = ['-fecha_generacion', 'tipo_parametro']
        indexes = [
            # El comando de evaluación filtra exactamente por este par.
            models.Index(fields=['estado', 'fecha_objetivo'],
                         name='idx_pred_estado_fecha'),
            models.Index(fields=['geomembrana', '-fecha_generacion'],
                         name='idx_pred_geo_fecha'),
        ]

    def __str__(self):
        return (f'{self.tipo_parametro_id} → {self.valor_esperado} '
                f'el {self.fecha_objetivo} ({self.estado})')

    # ------------------------------------------------------------------
    # Lógica de contraste
    # ------------------------------------------------------------------
    @property
    def rango_previsto(self):
        """Texto del intervalo predicho, para pintarlo sin formatear en el template."""
        return f'{self.valor_min} – {self.valor_max}'

    @property
    def acerto(self):
        """True si el valor real cayó dentro del intervalo previsto."""
        if self.valor_real is None:
            return None
        return self.valor_min <= self.valor_real <= self.valor_max

    @property
    def error_relativo_pct(self):
        """
        Error como porcentaje del valor real.

        Un error de 0.3 significa cosas distintas en pH (mucho) y en turbidez
        (nada): el porcentaje permite comparar parámetros entre sí.

        :return: float redondeado, o None si no se puede calcular
        """
        if self.valor_real is None or not self.valor_real:
            return None
        return round(abs(self.error_absoluto or 0) / abs(self.valor_real) * 100, 1)

    @property
    def vencida(self):
        """True si ya pasó su fecha objetivo y sigue sin evaluarse."""
        from django.utils import timezone
        return self.estado == 'pendiente' and self.fecha_objetivo < timezone.localdate()

    def evaluar(self, guardar=True):
        """
        Contrasta la predicción contra las lecturas reales del día objetivo.

        Si ese día no hubo mediciones, la predicción queda 'sin_datos': no
        cuenta como acierto ni como fallo. Contarla como fallo castigaría al
        modelo por una falla del hardware, y contarla como acierto inflaría
        la precisión con datos que nunca existieron.

        :param guardar: persistir el resultado (False para simular)
        :return: str con el estado resultante
        """
        from django.db.models import Avg, Count
        from django.utils import timezone

        from apps.monitoreo.models import Lectura

        medido = Lectura.objects.filter(
            geomembrana_id=self.geomembrana_id,
            tipo_parametro_id=self.tipo_parametro_id,
            timestamp_lectura__date=self.fecha_objetivo,
        ).aggregate(promedio=Avg('valor_medida'), cuantas=Count('id'))

        self.lecturas_evaluadas = medido['cuantas'] or 0
        self.fecha_evaluacion = timezone.now()

        if not self.lecturas_evaluadas:
            self.estado = 'sin_datos'
            self.valor_real = None
            self.error_absoluto = None
        else:
            self.valor_real = medido['promedio']
            self.error_absoluto = abs(self.valor_real - self.valor_esperado)
            self.estado = 'acertada' if self.acerto else 'fallida'

        if guardar:
            self.save(update_fields=[
                'estado', 'valor_real', 'error_absoluto',
                'lecturas_evaluadas', 'fecha_evaluacion',
            ])
        return self.estado
