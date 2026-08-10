from django.db import models


class EtapaProduccion(models.Model):
    ESTADOS = [('activo', 'Activo'), ('inactivo', 'Inactivo')]

    nombre_etapa = models.CharField('Etapa', max_length=50, unique=True)
    descripcion = models.TextField('Descripción', blank=True)
    dias_duracion = models.PositiveIntegerField('Duración (días)', null=True, blank=True)

    peso_inicial_promedio = models.DecimalField(
        'Peso inicial (g)', max_digits=10, decimal_places=2, null=True, blank=True
    )
    peso_final_promedio = models.DecimalField(
        'Peso final (g)', max_digits=10, decimal_places=2, null=True, blank=True
    )
    densidad_peces_por_m2 = models.DecimalField(
        'Densidad (peces/m²)', max_digits=10, decimal_places=2, null=True, blank=True
    )

    rango_temperatura_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rango_temperatura_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rango_ph_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rango_ph_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rango_oxigeno_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rango_oxigeno_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rango_turbidez_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rango_turbidez_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    estado = models.CharField(max_length=10, choices=ESTADOS, default='activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'etapas_produccion'
        verbose_name = 'Etapa de producción'
        verbose_name_plural = 'Etapas de producción'
        ordering = ['id']

    def __str__(self):
        return self.nombre_etapa


class Geomembrana(models.Model):
    ESTADOS = [
        ('activo', 'Activa'),
        ('inactivo', 'Inactiva'),
        ('mantenimiento', 'En mantenimiento'),
    ]

    nombre_piscina = models.CharField('Nombre', max_length=100)
    codigo_identificacion = models.CharField('Código', max_length=50, unique=True)
    descripcion = models.TextField('Descripción', blank=True)
    ubicacion = models.CharField('Ubicación', max_length=255, blank=True)

    area_m2 = models.DecimalField('Área (m²)', max_digits=10, decimal_places=2, null=True, blank=True)
    profundidad_promedio = models.DecimalField(
        'Profundidad (m)', max_digits=5, decimal_places=2, null=True, blank=True
    )
    volumen_agua_m3 = models.DecimalField(
        'Volumen (m³)', max_digits=12, decimal_places=2, null=True, blank=True
    )
    capacidad_maxima_peces = models.PositiveIntegerField(
        'Capacidad máxima', null=True, blank=True
    )

    etapa_actual = models.ForeignKey(
        EtapaProduccion, on_delete=models.PROTECT,
        related_name='geomembranas', null=True, blank=True,
        verbose_name='Etapa actual'
    )

    fecha_instalacion = models.DateField('Instalación', null=True, blank=True)
    fecha_ultimo_mantenimiento = models.DateField('Último mantenimiento', null=True, blank=True)
    material = models.CharField('Material', max_length=100, blank=True)
    apta_para_produccion = models.BooleanField('Apta para producción', default=True)
    estado = models.CharField(max_length=15, choices=ESTADOS, default='activo')

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_edicion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geomembranas'
        verbose_name = 'Geomembrana'
        verbose_name_plural = 'Geomembranas'
        ordering = ['codigo_identificacion']

    def __str__(self):
        return f'{self.codigo_identificacion} - {self.nombre_piscina}'

    @property
    def esta_operativa(self):
        return self.estado == 'activo' and self.apta_para_produccion