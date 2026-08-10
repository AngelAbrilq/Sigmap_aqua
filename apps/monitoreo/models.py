from django.db import models
from django.utils import timezone


class TipoParametro(models.Model):
    IMPORTANCIAS = [('alta', 'Alta'), ('media', 'Media'), ('baja', 'Baja')]
    ESTADOS = [('activo', 'Activo'), ('inactivo', 'Inactivo')]

    nombre_parametro = models.CharField('Parámetro', max_length=50, unique=True)
    unidad_medida = models.CharField('Unidad', max_length=20, blank=True)

    rango_normal_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rango_normal_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rango_riesgo_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rango_riesgo_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rango_critico_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rango_critico_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    descripcion = models.TextField('Descripción', blank=True)
    importancia = models.CharField(max_length=10, choices=IMPORTANCIAS, default='alta')
    estado = models.CharField(max_length=10, choices=ESTADOS, default='activo')

    class Meta:
        db_table = 'tipos_parametros'
        verbose_name = 'Tipo de parámetro'
        verbose_name_plural = 'Tipos de parámetros'
        ordering = ['id']

    def __str__(self):
        return f'{self.nombre_parametro} ({self.unidad_medida})'

    def clasificar(self, valor):
        """Devuelve 'normal', 'riesgo' o 'critico' segun el valor medido."""
        if self.rango_normal_min is not None and self.rango_normal_max is not None:
            if self.rango_normal_min <= valor <= self.rango_normal_max:
                return 'normal'
        if self.rango_riesgo_min is not None and self.rango_riesgo_max is not None:
            if self.rango_riesgo_min <= valor <= self.rango_riesgo_max:
                return 'riesgo'
        return 'critico'


class Sensor(models.Model):
    ESTADOS = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('mantenimiento', 'En mantenimiento'),
        ('averiado', 'Averiado'),
    ]

    nombre_sensor = models.CharField('Nombre', max_length=100)
    codigo_hardware = models.CharField('Código de hardware', max_length=50, unique=True)

    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT,
        related_name='sensores', verbose_name='Piscina'
    )
    tipo_parametro = models.ForeignKey(
        TipoParametro, on_delete=models.PROTECT,
        related_name='sensores', verbose_name='Parámetro que mide'
    )

    ubicacion_exacta = models.CharField('Ubicación exacta', max_length=255, blank=True)
    modelo_sensor = models.CharField('Modelo', max_length=100, blank=True)
    marca_sensor = models.CharField('Marca', max_length=100, blank=True)

    rango_medicion_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rango_medicion_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    precision_valor = models.DecimalField(
        'Precisión', max_digits=10, decimal_places=4, null=True, blank=True
    )

    intervalo_lectura_segundos = models.PositiveIntegerField('Intervalo (s)', default=300)
    bateria_nivel_actual = models.PositiveSmallIntegerField('Batería (%)', null=True, blank=True)

    ultima_calibracion = models.DateField('Última calibración', null=True, blank=True)
    proxima_calibracion = models.DateField('Próxima calibración', null=True, blank=True)

    mac_address = models.CharField('MAC', max_length=17, blank=True, null=True, unique=True)
    ip_address = models.GenericIPAddressField('IP', blank=True, null=True)
    firmware_version = models.CharField('Firmware', max_length=20, blank=True)

    estado = models.CharField(max_length=15, choices=ESTADOS, default='activo')
    fecha_instalacion = models.DateTimeField(auto_now_add=True)
    fecha_edicion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sensores'
        verbose_name = 'Sensor'
        verbose_name_plural = 'Sensores'
        ordering = ['geomembrana', 'tipo_parametro']

    def __str__(self):
        return f'{self.codigo_hardware} - {self.nombre_sensor}'

    @property
    def calibracion_vencida(self):
        if not self.proxima_calibracion:
            return False
        return self.proxima_calibracion < timezone.localdate()


class Dispositivo(models.Model):
    """Nodo fisico (ESP32) que agrupa sensores y envia lecturas a la API."""

    ESTADOS = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('sin_conexion', 'Sin conexión'),
    ]

    codigo = models.CharField('Código', max_length=50, unique=True)
    descripcion = models.CharField('Descripción', max_length=255, blank=True)
    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT,
        related_name='dispositivos', verbose_name='Piscina'
    )
    token = models.CharField('Token de autenticación', max_length=64, unique=True)
    mac_address = models.CharField('MAC', max_length=17, blank=True, null=True)
    firmware_version = models.CharField('Firmware', max_length=20, blank=True)
    ultima_conexion = models.DateTimeField('Última conexión', null=True, blank=True)
    estado = models.CharField(max_length=15, choices=ESTADOS, default='activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dispositivos'
        verbose_name = 'Dispositivo'
        verbose_name_plural = 'Dispositivos'
        ordering = ['codigo']

    def __str__(self):
        return self.codigo

    @staticmethod
    def generar_token():
        import secrets
        return secrets.token_hex(32)


class Lectura(models.Model):
    ESTADOS_LECTURA = [
        ('normal', 'Normal'),
        ('riesgo', 'Riesgo'),
        ('critico', 'Crítico'),
    ]

    sensor = models.ForeignKey(
        Sensor, on_delete=models.PROTECT, related_name='lecturas'
    )
    geomembrana = models.ForeignKey(
        'piscinas.Geomembrana', on_delete=models.PROTECT, related_name='lecturas'
    )
    tipo_parametro = models.ForeignKey(
        TipoParametro, on_delete=models.PROTECT, related_name='lecturas'
    )

    valor_medida = models.DecimalField('Valor', max_digits=10, decimal_places=4)
    estado_lectura = models.CharField(max_length=10, choices=ESTADOS_LECTURA, default='normal')
    dentro_rango = models.BooleanField('Dentro de rango', default=True)

    timestamp_lectura = models.DateTimeField('Momento de la lectura', default=timezone.now)
    fecha_recepcion = models.DateTimeField('Recibida en', auto_now_add=True)

    dispositivo = models.ForeignKey(
        Dispositivo, on_delete=models.PROTECT,
        related_name='lecturas', null=True, blank=True
    )
    secuencia = models.PositiveIntegerField('N.º de secuencia', null=True, blank=True)

    validada = models.BooleanField('Validada', default=False)
    usuario_validacion = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        related_name='lecturas_validadas', null=True, blank=True
    )

    class Meta:
        db_table = 'lecturas_sensores'
        verbose_name = 'Lectura'
        verbose_name_plural = 'Lecturas'
        ordering = ['-timestamp_lectura']
        indexes = [
            models.Index(fields=['-timestamp_lectura']),
            models.Index(fields=['geomembrana', '-timestamp_lectura']),
            models.Index(fields=['sensor', '-timestamp_lectura']),
            models.Index(fields=['estado_lectura']),
        ]

    def __str__(self):
        return f'{self.sensor.codigo_hardware}: {self.valor_medida} ({self.estado_lectura})'