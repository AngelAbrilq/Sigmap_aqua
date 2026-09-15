"""
Modelos del dominio de infraestructura piscicola.

EtapaProduccion define los rangos objetivo por fase de cultivo.
Geomembrana es la entidad raiz del sistema: sin ella no existen sensores,
dispositivos, lecturas ni alertas (todas la referencian con PROTECT).
"""
from datetime import timedelta
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


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


class GeomembranaQuerySet(models.QuerySet):
    """QuerySet con los filtros de negocio reutilizados por vistas y reportes."""

    def operativas(self):
        """Solo las que pueden alojar produccion hoy."""
        return self.filter(estado='activo', apta_para_produccion=True)

    def con_relaciones(self):
        """Evita el N+1 al listar: la etapa se muestra en cada tarjeta."""
        return self.select_related('etapa_actual')

    def buscar(self, termino):
        """
        Busqueda libre sobre los campos que el operario escribe de memoria.

        :param termino: texto ingresado en el buscador
        :return: GeomembranaQuerySet filtrado
        """
        termino = (termino or '').strip()
        if not termino:
            return self
        return self.filter(
            models.Q(nombre_piscina__icontains=termino)
            | models.Q(codigo_identificacion__icontains=termino)
            | models.Q(ubicacion__icontains=termino)
            | models.Q(material__icontains=termino)
        )


class Geomembrana(models.Model):
    ESTADOS = [
        ('activo', 'Activa'),
        ('inactivo', 'Inactiva'),
        ('mantenimiento', 'En mantenimiento'),
    ]

    # Periodicidad de inspeccion cuando la etapa no define una propia.
    DIAS_ENTRE_INSPECCIONES = 30
    # Umbrales del semaforo de vida util (porcentaje restante).
    UMBRAL_VIDA_ATENCION = 50
    UMBRAL_VIDA_CRITICA = 20

    # --- Identificacion ---
    nombre_piscina = models.CharField('Nombre', max_length=100)
    codigo_identificacion = models.CharField('Código', max_length=50, unique=True)
    descripcion = models.TextField('Descripción', blank=True)
    ubicacion = models.CharField('Ubicación', max_length=255, blank=True)

    # --- Geometria y capacidad ---
    area_m2 = models.DecimalField(
        'Área (m²)', max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    profundidad_promedio = models.DecimalField(
        'Profundidad (m)', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    volumen_agua_m3 = models.DecimalField(
        'Volumen (m³)', max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Si se deja vacío se calcula como área × profundidad.'
    )
    capacidad_maxima_peces = models.PositiveIntegerField(
        'Capacidad máxima', null=True, blank=True
    )

    etapa_actual = models.ForeignKey(
        EtapaProduccion, on_delete=models.PROTECT,
        related_name='geomembranas', null=True, blank=True,
        verbose_name='Etapa actual'
    )

    # --- Ficha tecnica de la lamina ---
    material = models.CharField('Material', max_length=100, blank=True)
    espesor_mm = models.DecimalField(
        'Espesor (mm)', max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    proveedor = models.CharField('Proveedor', max_length=150, blank=True)
    garantia_anios = models.PositiveSmallIntegerField(
        'Garantía (años)', null=True, blank=True
    )
    vida_util_anios = models.PositiveSmallIntegerField(
        'Vida útil estimada (años)', null=True, blank=True
    )

    # --- Ciclo de vida ---
    fecha_instalacion = models.DateField('Instalación', null=True, blank=True)
    fecha_ultimo_mantenimiento = models.DateField('Último mantenimiento', null=True, blank=True)
    apta_para_produccion = models.BooleanField('Apta para producción', default=True)
    estado = models.CharField(max_length=15, choices=ESTADOS, default='activo')

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_edicion = models.DateTimeField(auto_now=True)

    objects = GeomembranaQuerySet.as_manager()

    class Meta:
        db_table = 'geomembranas'
        verbose_name = 'Geomembrana'
        verbose_name_plural = 'Geomembranas'
        ordering = ['codigo_identificacion']
        indexes = [
            models.Index(fields=['estado', 'apta_para_produccion'], name='idx_geo_estado_apta'),
        ]

    def __str__(self):
        return f'{self.codigo_identificacion} - {self.nombre_piscina}'

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        """
        Normaliza el codigo y deriva el volumen antes de persistir.

        El volumen es un dato calculable: si el usuario no lo escribe, se
        infiere de area x profundidad para no dejar la ficha incompleta.
        """
        self.codigo_identificacion = self.codigo_identificacion.strip().upper()

        if self.volumen_agua_m3 is None and self.area_m2 and self.profundidad_promedio:
            self.volumen_agua_m3 = (self.area_m2 * self.profundidad_promedio).quantize(
                Decimal('0.01')
            )

        return super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Logica de negocio (solo lectura)
    # ------------------------------------------------------------------
    @property
    def esta_operativa(self):
        """True si hoy puede alojar produccion."""
        return self.estado == 'activo' and self.apta_para_produccion

    @property
    def anios_en_servicio(self):
        """
        Años transcurridos desde la instalación.

        :return: float con los años, o None si no hay fecha de instalación
        """
        if not self.fecha_instalacion:
            return None
        return (timezone.localdate() - self.fecha_instalacion).days / 365.25

    @property
    def vida_util_restante_pct(self):
        """
        Porcentaje de vida util que le queda a la lamina.

        Se calcula por desgaste lineal sobre la vida util declarada. Es una
        estimacion, no una medicion: el estado real lo confirma la inspeccion.

        :return: int 0-100, o None si faltan datos para calcularlo
        """
        if not self.vida_util_anios or self.anios_en_servicio is None:
            return None
        consumido = self.anios_en_servicio / self.vida_util_anios
        return max(0, min(100, round((1 - consumido) * 100)))

    # Circunferencia del arco del medidor circular: 2*pi*r con r=26.
    CIRCUNFERENCIA_GAUGE = 163.36

    @property
    def vida_dashoffset(self):
        """
        Desplazamiento del trazo para el medidor circular de vida util.

        El SVG dibuja el arco completo y lo recorta con stroke-dashoffset. El
        calculo vive aqui y no en el template porque es aritmetica, no
        presentacion: el template solo imprime el numero.

        :return: float con el offset, o None si no hay vida util calculable
        """
        vida = self.vida_util_restante_pct
        if vida is None:
            return None
        return round(self.CIRCUNFERENCIA_GAUGE * (1 - vida / 100), 2)

    @property
    def en_garantia(self):
        """True si la lamina sigue cubierta por la garantia del fabricante."""
        if not self.garantia_anios or self.anios_en_servicio is None:
            return False
        return self.anios_en_servicio < self.garantia_anios

    @property
    def proxima_inspeccion(self):
        """
        Fecha sugerida de la proxima inspeccion.

        Se toma la periodicidad de la etapa si la define; si no, el default
        de 30 dias. La base es el ultimo mantenimiento, o la instalacion.

        :return: date, o None si no hay fecha base
        """
        base = self.fecha_ultimo_mantenimiento or self.fecha_instalacion
        if not base:
            return None
        periodicidad = (
            self.etapa_actual.dias_duracion
            if self.etapa_actual and self.etapa_actual.dias_duracion
            else self.DIAS_ENTRE_INSPECCIONES
        )
        return base + timedelta(days=periodicidad)

    @property
    def dias_para_inspeccion(self):
        """Dias que faltan para la proxima inspeccion. Negativo = vencida."""
        proxima = self.proxima_inspeccion
        if not proxima:
            return None
        return (proxima - timezone.localdate()).days

    @property
    def inspeccion_vencida(self):
        """True si ya paso la fecha sugerida de inspeccion."""
        dias = self.dias_para_inspeccion
        return dias is not None and dias < 0

    @property
    def alertas_activas(self):
        """
        Alertas sin resolver de esta piscina.

        Usa el related_name 'alertas' definido en apps.alertas.models.Alerta.
        """
        return self.alertas.filter(estado='activa')

    @property
    def estado_operativo(self):
        """
        Semaforo consolidado de la geomembrana.

        Combina tres senales, de la mas grave a la menos:
        alertas criticas abiertas > vida util agotada > inspeccion vencida.

        :return: 'crit' | 'warn' | 'ok'
        """
        if self.estado == 'inactivo':
            return 'crit'

        if self.alertas_activas.filter(severidad='critica').exists():
            return 'crit'

        vida = self.vida_util_restante_pct
        if vida is not None and vida <= self.UMBRAL_VIDA_CRITICA:
            return 'crit'

        if self.estado == 'mantenimiento' or not self.apta_para_produccion:
            return 'warn'
        if self.alertas_activas.exists():
            return 'warn'
        if vida is not None and vida <= self.UMBRAL_VIDA_ATENCION:
            return 'warn'
        if self.inspeccion_vencida:
            return 'warn'

        return 'ok'

    @property
    def estado_operativo_label(self):
        """Etiqueta legible del semaforo, para pintar en el template."""
        return {'ok': 'Óptimo', 'warn': 'Atención', 'crit': 'Crítico'}[self.estado_operativo]

    @property
    def dependencias(self):
        """
        Cuenta los registros que impiden un borrado fisico.

        Todos los FK hacia Geomembrana son PROTECT, asi que cualquiera de
        estos bloquea el delete. La vista lo usa para decidir entre borrar
        y desactivar antes de intentar la operacion.

        :return: dict {'sensores': int, 'dispositivos': int, 'lecturas': int, 'alertas': int}
        """
        return {
            'sensores': self.sensores.count(),
            'dispositivos': self.dispositivos.count(),
            'lecturas': self.lecturas.count(),
            'alertas': self.alertas.count(),
        }

    @property
    def tiene_dependencias(self):
        """True si existe historico asociado y no se puede borrar fisicamente."""
        return any(self.dependencias.values())
