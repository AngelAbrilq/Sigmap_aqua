"""
Reportes persistidos y comparaciones entre periodos.

Corresponde a las tablas `reportes` y `comparaciones_datos` del ERD. Un
reporte guarda sus propios datos agregados: si se recalculara al abrirlo,
un reporte de marzo cambiaria cada vez que llegan lecturas nuevas y dejaria
de servir como evidencia.
"""
from django.db import models


class Reporte(models.Model):
    TIPOS = [
        ('diario', 'Diario'),
        ('semanal', 'Semanal'),
        ('mensual', 'Mensual'),
        ('personalizado', 'Personalizado'),
    ]

    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT,
        related_name='reportes', verbose_name='Piscina'
    )
    titulo = models.CharField('Título', max_length=255)
    tipo_reporte = models.CharField('Tipo', max_length=15, choices=TIPOS, default='semanal')
    descripcion = models.TextField('Descripción', blank=True)

    fecha_inicio = models.DateField('Desde')
    fecha_fin = models.DateField('Hasta')

    # Congelado al generar: es la evidencia del periodo, no una vista viva.
    datos_reporte = models.JSONField('Datos agregados', default=dict)
    resumen_ejecutivo = models.TextField('Resumen', blank=True)
    conclusiones = models.TextField('Conclusiones', blank=True)

    generado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        related_name='reportes_generados', null=True, blank=True
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reportes'
        verbose_name = 'Reporte'
        verbose_name_plural = 'Reportes'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['geomembrana', '-fecha_creacion'],
                         name='idx_rep_geo_fecha'),
        ]

    def __str__(self):
        return f'{self.titulo} ({self.fecha_inicio} – {self.fecha_fin})'

    @property
    def dias_cubiertos(self):
        """Cantidad de dias que abarca el reporte, ambos extremos incluidos."""
        return (self.fecha_fin - self.fecha_inicio).days + 1


class ComparacionDatos(models.Model):
    """
    Comparacion entre dos periodos de la misma piscina (tabla `comparaciones_datos`).

    Responde a la pregunta operativa real: ¿el agua está mejor o peor que el
    ciclo anterior?
    """

    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT,
        related_name='comparaciones', verbose_name='Piscina'
    )
    usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        related_name='comparaciones', null=True, blank=True
    )

    periodo_1_inicio = models.DateField('Periodo 1 desde')
    periodo_1_fin = models.DateField('Periodo 1 hasta')
    periodo_2_inicio = models.DateField('Periodo 2 desde')
    periodo_2_fin = models.DateField('Periodo 2 hasta')

    resultados_comparacion = models.JSONField('Resultados', default=dict)
    diferencias_principales = models.TextField('Diferencias', blank=True)
    conclusiones = models.TextField('Conclusiones', blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'comparaciones_datos'
        verbose_name = 'Comparación de periodos'
        verbose_name_plural = 'Comparaciones de periodos'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.geomembrana_id}: {self.periodo_1_inicio} vs {self.periodo_2_inicio}'
