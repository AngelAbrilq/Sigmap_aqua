"""
Registro de eventos del sistema (auditoría) — RF018.

Las alertas ya quedan registradas en la tabla `alertas`. Este modelo cubre lo
que un histórico de alertas NO captura y que el requerimiento sí exige: los
cambios de configuración (umbrales de parámetros) y las acciones de usuario
(altas/bajas de cuentas, inicios de sesión, reconocimiento y cierre de alertas).

Corresponde a la tabla `eventos_sistema` del ERD. Un evento nunca debe tumbar la
acción que lo origina: la escritura se hace desde `services.registrar_evento`,
que atrapa cualquier fallo para que auditar sea un efecto secundario, no un
punto de falla.
"""
from django.db import models


class EventoSistema(models.Model):
    class Tipo(models.TextChoices):
        CONFIG_UMBRAL = 'config_umbral', 'Cambio de umbrales'
        USUARIO_ALTA = 'usuario_alta', 'Alta de usuario'
        USUARIO_EDICION = 'usuario_edicion', 'Edición de usuario'
        USUARIO_ESTADO = 'usuario_estado', 'Cambio de estado de usuario'
        SESION_INICIO = 'sesion_inicio', 'Inicio de sesión'
        ALERTA_RECONOCIDA = 'alerta_reconocida', 'Alerta reconocida'
        ALERTA_RESUELTA = 'alerta_resuelta', 'Alerta resuelta'
        SISTEMA = 'sistema', 'Evento del sistema'

    class Nivel(models.TextChoices):
        INFO = 'info', 'Informativo'
        ADVERTENCIA = 'advertencia', 'Advertencia'
        CRITICO = 'critico', 'Crítico'

    tipo_evento = models.CharField('Tipo', max_length=30, choices=Tipo.choices)
    nivel = models.CharField('Nivel', max_length=12, choices=Nivel.choices, default=Nivel.INFO)

    usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        related_name='eventos', null=True, blank=True, verbose_name='Responsable',
    )
    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.SET_NULL,
        related_name='eventos', null=True, blank=True, verbose_name='Piscina',
    )

    descripcion = models.CharField('Descripción', max_length=255)
    datos = models.JSONField('Datos', default=dict, blank=True)
    ip_origen = models.GenericIPAddressField('IP de origen', null=True, blank=True)

    created_at = models.DateTimeField('Fecha', auto_now_add=True)

    class Meta:
        db_table = 'eventos_sistema'
        verbose_name = 'Evento del sistema'
        verbose_name_plural = 'Eventos del sistema'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tipo_evento', '-created_at'], name='idx_evt_tipo_fecha'),
            models.Index(fields=['geomembrana', '-created_at'], name='idx_evt_geo_fecha'),
        ]

    def __str__(self):
        return f'[{self.get_tipo_evento_display()}] {self.descripcion}'
