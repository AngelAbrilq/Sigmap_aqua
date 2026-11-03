"""
Serializers de la API móvil.

Separados a propósito de los del ESP32: distinto consumidor, distinto
contrato. El firmware necesita lo mínimo para confirmar una ingesta; la app
necesita datos legibles para una persona.

Regla de seguridad: aquí nunca se expone `password`, ni el `token` de un
Dispositivo, ni nada que no deba salir del servidor.
"""
from rest_framework import serializers

from apps.alertas.models import Alerta, Notificacion
from apps.ia.models import AnalisisIA, Prediccion
from apps.monitoreo.models import Lectura, Sensor, TipoParametro
from apps.piscinas.models import Geomembrana
from apps.usuarios.models import Usuario


class UsuarioMovilSerializer(serializers.ModelSerializer):
    """Perfil del usuario autenticado."""

    rol = serializers.CharField(source='rol.nombre_rol', read_only=True)
    foto_perfil = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'nombre_completo', 'email', 'rol', 'estado',
                  'numero_celular', 'foto_perfil']
        read_only_fields = fields

    def get_foto_perfil(self, obj):
        """
        URL absoluta de la foto, o None.

        La app corre en otro host: una ruta relativa como /media/x.jpg no le
        sirve, necesita el esquema y el dominio completos.
        """
        if not obj.foto_perfil:
            return None
        peticion = self.context.get('request')
        url = obj.foto_perfil.url
        return peticion.build_absolute_uri(url) if peticion else url


class GeomembranaListaSerializer(serializers.ModelSerializer):
    """Fila del listado de piscinas: lo justo para pintar una tarjeta."""

    etapa = serializers.CharField(source='etapa_actual.nombre_etapa',
                                  read_only=True, default=None)
    estado_operativo = serializers.CharField(read_only=True)
    estado_operativo_label = serializers.CharField(read_only=True)
    vida_util_restante_pct = serializers.IntegerField(read_only=True)
    alertas_activas = serializers.SerializerMethodField()

    class Meta:
        model = Geomembrana
        fields = ['id', 'nombre_piscina', 'codigo_identificacion', 'ubicacion',
                  'estado', 'apta_para_produccion', 'etapa',
                  'estado_operativo', 'estado_operativo_label',
                  'vida_util_restante_pct', 'alertas_activas']

    def get_alertas_activas(self, obj):
        """
        Cuenta de alertas abiertas.

        Usa el `annotate` del queryset cuando está disponible: contar aquí con
        obj.alertas.count() sería una consulta por fila (N+1).
        """
        return getattr(obj, 'total_alertas_activas', None) or obj.alertas_activas.count()


class GeomembranaDetalleSerializer(GeomembranaListaSerializer):
    """Ficha completa, para la pantalla de detalle."""

    class Meta(GeomembranaListaSerializer.Meta):
        fields = GeomembranaListaSerializer.Meta.fields + [
            'descripcion', 'area_m2', 'profundidad_promedio', 'volumen_agua_m3',
            'capacidad_maxima_peces', 'material', 'espesor_mm', 'proveedor',
            'fecha_instalacion', 'fecha_ultimo_mantenimiento',
        ]


class LecturaSerializer(serializers.ModelSerializer):
    """
    Una medición.

    `valor_medida` sale como string porque es un DecimalField: DRF lo serializa
    así para no perder precisión al pasar por float. El cliente convierte solo
    cuando necesita graficar.
    """

    parametro_id = serializers.IntegerField(source='tipo_parametro_id', read_only=True)
    parametro = serializers.CharField(source='tipo_parametro.nombre_parametro',
                                      read_only=True)
    unidad = serializers.CharField(source='tipo_parametro.unidad_medida',
                                   read_only=True)
    sensor = serializers.CharField(source='sensor.codigo_hardware', read_only=True)
    rango_min = serializers.DecimalField(
        source='tipo_parametro.rango_normal_min', max_digits=10,
        decimal_places=4, read_only=True)
    rango_max = serializers.DecimalField(
        source='tipo_parametro.rango_normal_max', max_digits=10,
        decimal_places=4, read_only=True)

    class Meta:
        model = Lectura
        fields = ['id', 'parametro_id', 'parametro', 'unidad', 'sensor', 'valor_medida',
                  'estado_lectura', 'dentro_rango', 'timestamp_lectura',
                  'rango_min', 'rango_max']
        read_only_fields = fields


class UltimaLecturaSerializer(serializers.Serializer):
    """
    Estado actual de un parámetro.

    No es un ModelSerializer porque incluye parámetros que todavía NO tienen
    lectura: la app necesita mostrar la tarjeta en gris con 'Sin datos' en vez
    de omitirla, o el operario no sabría que ese sensor existe y está mudo.
    """

    parametro_id = serializers.IntegerField()
    parametro = serializers.CharField()
    unidad = serializers.CharField()
    sensor = serializers.CharField(allow_null=True)
    valor_medida = serializers.CharField(allow_null=True)
    estado_lectura = serializers.CharField()
    timestamp_lectura = serializers.DateTimeField(allow_null=True)
    rango_min = serializers.CharField(allow_null=True)
    rango_max = serializers.CharField(allow_null=True)
    # Mismos campos extra que el tablero web.
    sensor_nombre = serializers.CharField(allow_null=True, required=False)
    rango_fuente = serializers.CharField(allow_null=True, required=False)
    simulado = serializers.BooleanField(default=False)


class AlertaSerializer(serializers.ModelSerializer):
    """Alerta con los nombres ya resueltos, para no hacer joins en el cliente."""

    piscina = serializers.CharField(source='geomembrana.nombre_piscina', read_only=True)
    parametro = serializers.CharField(source='tipo_parametro.nombre_parametro',
                                      read_only=True, default=None)
    severidad_label = serializers.CharField(source='get_severidad_display', read_only=True)
    estado_label = serializers.CharField(source='get_estado_display', read_only=True)
    atendida_por = serializers.CharField(
        source='usuario_reconocimiento.nombre_completo', read_only=True, default=None)

    class Meta:
        model = Alerta
        fields = ['id', 'geomembrana', 'piscina', 'parametro', 'tipo_alerta',
                  'severidad', 'severidad_label', 'estado', 'estado_label',
                  'valor_que_disparo', 'mensaje_alerta', 'accion_tomada',
                  'atendida_por', 'fecha_generacion', 'fecha_resolucion']
        read_only_fields = fields


class ResolverAlertaSerializer(serializers.Serializer):
    """
    Entrada para cerrar una alerta.

    La acción tomada es obligatoria: una alerta crítica cerrada sin explicación
    no sirve para la trazabilidad del cultivo.
    """

    accion_tomada = serializers.CharField(
        max_length=2000, allow_blank=False, trim_whitespace=True,
        error_messages={'blank': 'Describe la acción tomada antes de cerrar la alerta.',
                        'required': 'Describe la acción tomada antes de cerrar la alerta.'})


class NotificacionSerializer(serializers.ModelSerializer):
    """Bandeja del usuario autenticado."""

    class Meta:
        model = Notificacion
        fields = ['id', 'titulo', 'mensaje', 'canal', 'leida',
                  'fecha_creacion', 'alerta']
        read_only_fields = fields


class PrediccionSerializer(serializers.ModelSerializer):
    """Proyección de IA con su resultado, si ya fue contrastada."""

    piscina = serializers.CharField(source='geomembrana.nombre_piscina', read_only=True)
    parametro = serializers.CharField(source='tipo_parametro.nombre_parametro',
                                      read_only=True)
    unidad = serializers.CharField(source='tipo_parametro.unidad_medida', read_only=True)
    estado_label = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Prediccion
        fields = ['id', 'geomembrana', 'piscina', 'parametro', 'unidad',
                  'valor_esperado', 'valor_min', 'valor_max',
                  'probabilidad_fuera_rango', 'justificacion',
                  'fecha_objetivo', 'horizonte_dias',
                  'estado', 'estado_label', 'valor_real', 'error_absoluto',
                  'fecha_generacion']
        read_only_fields = fields


class FiltroHistorialSerializer(serializers.Serializer):
    """
    Valida los query params del historial ANTES de tocar la base de datos.

    Sin esto, un `?desde=ayer` provocaría un ValidationError crudo de Django
    en medio del ORM. Validado aquí, devuelve un 400 con el campo señalado.
    """

    geomembrana = serializers.IntegerField(required=False, min_value=1)
    parametro = serializers.IntegerField(required=False, min_value=1)
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    estado = serializers.ChoiceField(
        choices=Lectura.ESTADOS_LECTURA, required=False)

    def validate(self, datos):
        """El rango debe estar bien orientado."""
        desde, hasta = datos.get('desde'), datos.get('hasta')
        if desde and hasta and desde > hasta:
            raise serializers.ValidationError(
                {'desde': 'La fecha inicial no puede ser posterior a la final.'})
        return datos


# ---------------------------------------------------------------------------
# Inteligencia artificial
# ---------------------------------------------------------------------------
# Mismas opciones que el formulario del panel web de IA (apps/ia/views.py).
VENTANAS_IA = (3, 7, 15, 30)
HORIZONTES_IA = (1, 3, 5, 7)


class AnalisisIASerializer(serializers.ModelSerializer):
    """Análisis de IA con lo que el panel web muestra: diagnóstico, anomalías,
    recomendaciones, riesgo y confianza."""

    piscina = serializers.CharField(source='geomembrana.nombre_piscina', read_only=True)
    tipo_label = serializers.CharField(source='get_tipo_analisis_display', read_only=True)
    estado_label = serializers.CharField(source='get_estado_display', read_only=True)
    nivel_confianza = serializers.CharField(read_only=True)
    recomendaciones = serializers.SerializerMethodField()
    anomalias = serializers.SerializerMethodField()
    riesgo_proyectado = serializers.SerializerMethodField()
    total_lecturas = serializers.SerializerMethodField()
    ventana_dias = serializers.SerializerMethodField()
    total_predicciones = serializers.SerializerMethodField()

    class Meta:
        model = AnalisisIA
        fields = ['id', 'geomembrana', 'piscina', 'tipo_analisis', 'tipo_label',
                  'estado', 'estado_label', 'descripcion_analisis',
                  'recomendaciones', 'anomalias', 'riesgo_proyectado',
                  'confianza', 'nivel_confianza', 'modelo_usado',
                  'total_lecturas', 'ventana_dias', 'total_predicciones',
                  'fecha_generacion']
        read_only_fields = fields

    def get_recomendaciones(self, obj):
        """En la BD es texto con una recomendación por línea; la app quiere lista."""
        return [linea.strip() for linea in (obj.recomendaciones or '').splitlines()
                if linea.strip()]

    def get_anomalias(self, obj):
        """Solo anomalías bien formadas: el JSON viene de un modelo de lenguaje."""
        anomalias = []
        for item in obj.anomalias_detectadas or []:
            if isinstance(item, dict) and item.get('descripcion'):
                gravedad = str(item.get('gravedad', 'media')).lower()
                anomalias.append({
                    'parametro': str(item.get('parametro') or ''),
                    'descripcion': str(item['descripcion']),
                    'gravedad': gravedad if gravedad in ('baja', 'media', 'alta') else 'media',
                })
            elif isinstance(item, str) and item.strip():
                anomalias.append({'parametro': '', 'descripcion': item, 'gravedad': 'media'})
        return anomalias

    def get_riesgo_proyectado(self, obj):
        riesgo = (obj.resultados_salida or {}).get('riesgo_proyectado')
        return riesgo if riesgo in ('bajo', 'medio', 'alto') else None

    def get_total_lecturas(self, obj):
        return (obj.datos_entrada or {}).get('total_lecturas')

    def get_ventana_dias(self, obj):
        return (obj.datos_entrada or {}).get('ventana_dias')

    def get_total_predicciones(self, obj):
        # Anotado en la vista para evitar N+1; 0 si no viene.
        return getattr(obj, 'num_predicciones', 0)


class GenerarAnalisisSerializer(serializers.Serializer):
    """Valida la petición de un análisis nuevo con las reglas del panel web."""

    geomembrana = serializers.PrimaryKeyRelatedField(
        queryset=Geomembrana.objects.operativas(),
        error_messages={'does_not_exist': 'La geomembrana no existe o no está operativa.'})
    tipo = serializers.ChoiceField(choices=AnalisisIA.TIPOS, default='diagnostico')
    dias = serializers.ChoiceField(choices=VENTANAS_IA, default=7)
    horizonte = serializers.ChoiceField(choices=HORIZONTES_IA, default=3)


class PreguntaAsistenteSerializer(serializers.Serializer):
    """Pregunta libre al asistente; mismo límite de largo que el chat web."""

    pregunta = serializers.CharField(max_length=500, trim_whitespace=True,
                                     error_messages={'blank': 'Escribe una pregunta.'})

    def validate_pregunta(self, valor):
        if len(valor) < 2:
            raise serializers.ValidationError('Escribe una pregunta.')
        return valor


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------
MAX_DIAS_REPORTE = 366


class TipoParametroSerializer(serializers.ModelSerializer):
    """Parámetro medible, para los filtros de reportes."""

    class Meta:
        model = TipoParametro
        fields = ['id', 'nombre_parametro', 'unidad_medida']
        read_only_fields = fields


class FiltroReporteSerializer(FiltroHistorialSerializer):
    """
    Filtros del reporte: los del historial + el formato de descarga.

    Acota el rango a un año: un reporte de varios años bloquearía el servidor
    generando el PDF mientras el operario espera en el celular.
    """

    formato = serializers.ChoiceField(choices=[('pdf', 'PDF'), ('xlsx', 'Excel')],
                                      required=False, default='pdf')

    def validate(self, datos):
        datos = super().validate(datos)
        desde, hasta = datos.get('desde'), datos.get('hasta')
        if desde and hasta and (hasta - desde).days > MAX_DIAS_REPORTE:
            raise serializers.ValidationError(
                {'desde': f'El rango no puede superar {MAX_DIAS_REPORTE} días.'})
        return datos
