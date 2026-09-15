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
