from django.db import models
from django.utils import timezone


class Alerta(models.Model):
    TIPOS = [
        ('riesgo', 'Riesgo'),
        ('critico', 'Crítico'),
        ('sensor', 'Falla de sensor'),
        ('desconexion', 'Dispositivo sin conexión'),
    ]
    SEVERIDADES = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]
    ESTADOS = [
        ('activa', 'Activa'),
        ('reconocida', 'Reconocida'),
        ('resuelta', 'Resuelta'),
        ('descartada', 'Descartada'),
    ]

    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT,
        related_name='alertas', verbose_name='Piscina'
    )
    sensor = models.ForeignKey(
        'monitoreo.Sensor', on_delete=models.PROTECT,
        related_name='alertas', null=True, blank=True
    )
    tipo_parametro = models.ForeignKey(
        'monitoreo.TipoParametro', on_delete=models.PROTECT,
        related_name='alertas', null=True, blank=True
    )
    lectura = models.ForeignKey(
        'monitoreo.Lectura', on_delete=models.PROTECT,
        related_name='alertas', null=True, blank=True
    )

    tipo_alerta = models.CharField('Tipo', max_length=15, choices=TIPOS)
    severidad = models.CharField('Severidad', max_length=10, choices=SEVERIDADES)
    valor_que_disparo = models.DecimalField(
        'Valor', max_digits=10, decimal_places=4, null=True, blank=True
    )
    mensaje_alerta = models.TextField('Mensaje')

    estado = models.CharField(max_length=15, choices=ESTADOS, default='activa')

    fecha_generacion = models.DateTimeField(auto_now_add=True)
    fecha_reconocimiento = models.DateTimeField(null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    usuario_reconocimiento = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        related_name='alertas_reconocidas', null=True, blank=True
    )
    accion_tomada = models.TextField('Acción tomada', blank=True)

    class Meta:
        db_table = 'alertas'
        verbose_name = 'Alerta'
        verbose_name_plural = 'Alertas'
        ordering = ['-fecha_generacion']
        indexes = [
            models.Index(fields=['estado', '-fecha_generacion']),
            models.Index(fields=['geomembrana', 'estado']),
        ]

    def __str__(self):
        return f'[{self.get_severidad_display()}] {self.mensaje_alerta[:60]}'

    def reconocer(self, usuario):
        self.estado = 'reconocida'
        self.usuario_reconocimiento = usuario
        self.fecha_reconocimiento = timezone.now()
        self.save(update_fields=[
            'estado', 'usuario_reconocimiento', 'fecha_reconocimiento'
        ])

    def resolver(self, usuario, accion=''):
        self.estado = 'resuelta'
        self.fecha_resolucion = timezone.now()
        if accion:
            self.accion_tomada = accion
        if not self.usuario_reconocimiento:
            self.usuario_reconocimiento = usuario
        self.save()


class HistorialEstadoAgua(models.Model):
    ESTADOS = [
        ('optimo', 'Óptimo'),
        ('riesgo', 'Riesgo'),
        ('critico', 'Crítico'),
    ]

    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT,
        related_name='historial_estado'
    )
    estado_general = models.CharField(max_length=10, choices=ESTADOS)
    apta_produccion = models.BooleanField('Apta para producción', default=True)
    observaciones = models.TextField('Observaciones', blank=True)
    fecha_evaluacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historial_estado_agua'
        verbose_name = 'Estado del agua'
        verbose_name_plural = 'Historial de estado del agua'
        ordering = ['-fecha_evaluacion']
        indexes = [
            models.Index(fields=['geomembrana', '-fecha_evaluacion']),
        ]

    def __str__(self):
        return f'{self.geomembrana.codigo_identificacion}: {self.get_estado_general_display()}'