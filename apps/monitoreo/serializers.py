"""
Serializers de la API de ingesta de BioAqua.

Regla de diseno: el ESP32 es un mensajero. Toda validacion de plausibilidad
fisica vive aqui, en el servidor. Una sonda descalibrada que reporta pH 14.8
debe ser rechazada antes de contaminar el historico del cultivo.
"""
from decimal import Decimal

from rest_framework import serializers

from .models import Lectura, Sensor


class LecturaEntradaSerializer(serializers.Serializer):
    """Una sola medicion cruda proveniente del hardware."""

    codigo_hardware = serializers.CharField(max_length=50)
    valor = serializers.DecimalField(max_digits=10, decimal_places=4)
    secuencia = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    timestamp = serializers.DateTimeField(required=False, allow_null=True)

    def validate_codigo_hardware(self, valor):
        """El sensor debe existir, estar operativo y pertenecer a este dispositivo."""
        dispositivo = self.context['dispositivo']

        try:
            sensor = Sensor.objects.select_related('tipo_parametro', 'geomembrana').get(
                codigo_hardware=valor
            )
        except Sensor.DoesNotExist:
            raise serializers.ValidationError(
                f'No existe un sensor registrado con codigo "{valor}".'
            )

        if sensor.estado != 'activo':
            raise serializers.ValidationError(
                f'El sensor "{valor}" esta en estado "{sensor.get_estado_display()}"; '
                'sus lecturas no se registran.'
            )

        if sensor.geomembrana_id != dispositivo.geomembrana_id:
            raise serializers.ValidationError(
                f'El sensor "{valor}" pertenece a otra piscina distinta a la del '
                f'dispositivo {dispositivo.codigo}.'
            )

        self._sensor = sensor
        return valor

    def validate(self, datos):
        """Rechaza valores fuera del rango fisico que el sensor puede medir."""
        sensor = getattr(self, '_sensor', None)
        if sensor is None:
            return datos

        valor = datos['valor']
        minimo = sensor.rango_medicion_min
        maximo = sensor.rango_medicion_max

        if minimo is not None and valor < minimo:
            raise serializers.ValidationError({
                'valor': f'{valor} esta por debajo del rango medible del sensor '
                         f'({minimo} a {maximo}). Lectura descartada: probable fallo '
                         f'de sonda o cableado.'
            })
        if maximo is not None and valor > maximo:
            raise serializers.ValidationError({
                'valor': f'{valor} supera el rango medible del sensor '
                         f'({minimo} a {maximo}). Lectura descartada: probable fallo '
                         f'de sonda o cableado.'
            })

        datos['_sensor'] = sensor
        return datos


class LoteLecturasSerializer(serializers.Serializer):
    """
    Lote de lecturas enviado por un nodo.

    El envio por lotes es deliberado: agrupar varias mediciones en un POST cada
    pocos minutos reduce el consumo de radio del ESP32 y el numero de escrituras
    en MySQL, frente a un POST por cada muestra.
    """

    firmware = serializers.CharField(max_length=20, required=False, allow_blank=True)
    mac = serializers.CharField(max_length=17, required=False, allow_blank=True)
    lecturas = serializers.ListField(
        child=serializers.DictField(), allow_empty=False, max_length=100
    )

    def validate_lecturas(self, elementos):
        dispositivo = self.context['dispositivo']
        validadas = []
        errores = []

        for indice, bruto in enumerate(elementos):
            item = LecturaEntradaSerializer(data=bruto, context={'dispositivo': dispositivo})
            if item.is_valid():
                validadas.append(item.validated_data)
            else:
                errores.append({'indice': indice, 'errores': item.errors})

        if not validadas:
            raise serializers.ValidationError(
                {'message': 'Ninguna lectura del lote resulto valida.', 'detalle': errores}
            )

        self.errores_parciales = errores
        return validadas


class LecturaSalidaSerializer(serializers.ModelSerializer):
    """Confirmacion devuelta al dispositivo por cada lectura persistida."""

    sensor = serializers.CharField(source='sensor.codigo_hardware', read_only=True)
    parametro = serializers.CharField(source='tipo_parametro.nombre_parametro', read_only=True)

    class Meta:
        model = Lectura
        fields = ['id', 'sensor', 'parametro', 'valor_medida',
                  'estado_lectura', 'dentro_rango', 'timestamp_lectura']
        read_only_fields = fields
