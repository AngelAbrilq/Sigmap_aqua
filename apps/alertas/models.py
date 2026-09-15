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


class Notificacion(models.Model):
    """
    Aviso dirigido a un usuario concreto (tabla `notificaciones_push` del ERD).

    Una Alerta describe el problema del agua una sola vez; la Notificacion es
    su entrega a cada persona que debe enterarse. Separarlas permite que el
    Operario marque la suya como leida sin alterar el estado de la alerta ni
    el aviso que le llego al Instructor Lider.
    """

    CANALES = [
        ('sistema', 'En el sistema'),
        ('push', 'Push'),
        ('whatsapp', 'WhatsApp'),
        ('email', 'Correo'),
    ]

    usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.CASCADE,
        related_name='notificaciones', verbose_name='Destinatario'
    )
    alerta = models.ForeignKey(
        Alerta, on_delete=models.CASCADE,
        related_name='notificaciones', null=True, blank=True
    )

    titulo = models.CharField('Título', max_length=255)
    mensaje = models.TextField('Mensaje')
    canal = models.CharField(max_length=10, choices=CANALES, default='sistema')

    enviada = models.BooleanField('Enviada', default=True)
    leida = models.BooleanField('Leída', default=False)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_lectura = models.DateTimeField('Leída en', null=True, blank=True)

    class Meta:
        db_table = 'notificaciones_push'
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha_creacion']
        indexes = [
            # La campanita del header consulta exactamente por este par.
            models.Index(fields=['usuario', 'leida', '-fecha_creacion'],
                         name='idx_notif_usuario_leida'),
        ]

    def __str__(self):
        return f'{self.usuario_id}: {self.titulo}'

    def marcar_leida(self):
        """Marca la notificacion como leida. Idempotente."""
        if self.leida:
            return
        self.leida = True
        self.fecha_lectura = timezone.now()
        self.save(update_fields=['leida', 'fecha_lectura'])
