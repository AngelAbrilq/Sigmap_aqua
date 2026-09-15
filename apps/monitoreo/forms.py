"""
Formularios del modulo de monitoreo (sensores y parametros).

La validacion se mantiene fuera de las vistas: el formulario decide si el dato
es aceptable, la vista solo decide el flujo.
"""
from datetime import date

from django import forms

from apps.piscinas.models import Geomembrana

from .models import Sensor, TipoParametro


class SensorForm(forms.ModelForm):
    """Alta y edicion de sensores fisicos instalados en una piscina."""

    class Meta:
        model = Sensor
        fields = [
            'nombre_sensor', 'codigo_hardware', 'geomembrana', 'tipo_parametro',
            'ubicacion_exacta', 'modelo_sensor', 'marca_sensor',
            'rango_medicion_min', 'rango_medicion_max', 'precision_valor',
            'intervalo_lectura_segundos', 'bateria_nivel_actual',
            'ultima_calibracion', 'proxima_calibracion',
            'mac_address', 'ip_address', 'firmware_version', 'estado',
        ]
        widgets = {
            'nombre_sensor': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. Sonda de pH piscina 1'}),
            'codigo_hardware': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. SEN-009',
                'style': 'text-transform:uppercase;'}),
            'geomembrana': forms.Select(attrs={'class': 'gm-form-input'}),
            'tipo_parametro': forms.Select(attrs={'class': 'gm-form-input'}),
            'ubicacion_exacta': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. Borde norte, 40 cm de profundidad'}),
            'modelo_sensor': forms.TextInput(attrs={'class': 'gm-form-input'}),
            'marca_sensor': forms.TextInput(attrs={'class': 'gm-form-input'}),
            'rango_medicion_min': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'rango_medicion_max': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'precision_valor': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'intervalo_lectura_segundos': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'min': '10', 'placeholder': '300'}),
            'bateria_nivel_actual': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'min': '0', 'max': '100'}),
            'ultima_calibracion': forms.DateInput(attrs={'class': 'gm-form-input', 'type': 'date'},
                                                  format='%Y-%m-%d'),
            'proxima_calibracion': forms.DateInput(attrs={'class': 'gm-form-input', 'type': 'date'},
                                                   format='%Y-%m-%d'),
            'mac_address': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'AA:BB:CC:DD:EE:FF', 'maxlength': 17}),
            'ip_address': forms.TextInput(attrs={'class': 'gm-form-input', 'placeholder': '192.168.1.50'}),
            'firmware_version': forms.TextInput(attrs={'class': 'gm-form-input', 'placeholder': 'v1.0.3'}),
            'estado': forms.Select(attrs={'class': 'gm-form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un sensor no se instala en una piscina dada de baja.
        self.fields['geomembrana'].queryset = Geomembrana.objects.operativas()
        self.fields['tipo_parametro'].queryset = TipoParametro.objects.filter(estado='activo')
        self.fields['intervalo_lectura_segundos'].help_text = (
            'Cada cuánto reporta el nodo. Menos de 60 s satura la tabla de lecturas.'
        )

    def clean_codigo_hardware(self):
        """Normaliza el codigo y valida unicidad con un error legible."""
        codigo = (self.cleaned_data.get('codigo_hardware') or '').strip().upper()
        duplicado = Sensor.objects.filter(codigo_hardware=codigo)
        if self.instance.pk:
            duplicado = duplicado.exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise forms.ValidationError(f'Ya existe un sensor con el código {codigo}.')
        return codigo

    def clean_mac_address(self):
        """Normaliza la MAC a mayusculas con dos puntos, o la deja vacia."""
        mac = (self.cleaned_data.get('mac_address') or '').strip().upper().replace('-', ':')
        if not mac:
            # Vacia como None: el campo es unique y '' colisionaria entre sensores.
            return None
        partes = mac.split(':')
        if len(partes) != 6 or not all(len(p) == 2 for p in partes):
            raise forms.ValidationError('Formato de MAC inválido. Usa AA:BB:CC:DD:EE:FF.')
        return mac

    def clean(self):
        """Coherencia entre rangos de medicion y fechas de calibracion."""
        datos = super().clean()

        minimo = datos.get('rango_medicion_min')
        maximo = datos.get('rango_medicion_max')
        ultima = datos.get('ultima_calibracion')
        proxima = datos.get('proxima_calibracion')
        tipo = datos.get('tipo_parametro')
        intervalo = datos.get('intervalo_lectura_segundos')

        if minimo is not None and maximo is not None and minimo >= maximo:
            self.add_error('rango_medicion_max',
                           'El máximo del rango debe ser mayor que el mínimo.')

        if ultima and ultima > date.today():
            self.add_error('ultima_calibracion', 'La calibración no puede ser futura.')

        if ultima and proxima and proxima <= ultima:
            self.add_error('proxima_calibracion',
                           'La próxima calibración debe ser posterior a la última.')

        # El sensor debe cubrir el rango critico del parametro que mide; si no,
        # nunca podra reportar el valor que dispara la alerta.
        if tipo and minimo is not None and maximo is not None:
            if tipo.rango_normal_min is not None and tipo.rango_normal_min < minimo:
                self.add_error('rango_medicion_min',
                               f'No cubre el rango normal de {tipo.nombre_parametro} '
                               f'(desde {tipo.rango_normal_min}).')
            if tipo.rango_normal_max is not None and tipo.rango_normal_max > maximo:
                self.add_error('rango_medicion_max',
                               f'No cubre el rango normal de {tipo.nombre_parametro} '
                               f'(hasta {tipo.rango_normal_max}).')

        if intervalo is not None and intervalo < 10:
            self.add_error('intervalo_lectura_segundos',
                           'Un intervalo menor a 10 s satura la base de datos.')

        return datos


class TipoParametroForm(forms.ModelForm):
    """
    Configuracion de los umbrales que disparan las alertas.

    Es el formulario mas sensible del sistema: estos rangos deciden cuando el
    agua se considera critica. Por eso valida el anidamiento de los tres
    rangos y no solo que cada par este ordenado.
    """

    class Meta:
        model = TipoParametro
        fields = [
            'nombre_parametro', 'unidad_medida',
            'rango_normal_min', 'rango_normal_max',
            'rango_riesgo_min', 'rango_riesgo_max',
            'rango_critico_min', 'rango_critico_max',
            'descripcion', 'importancia', 'estado',
        ]
        widgets = {
            'nombre_parametro': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. Oxígeno disuelto'}),
            'unidad_medida': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. mg/L'}),
            'rango_normal_min': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'rango_normal_max': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'rango_riesgo_min': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'rango_riesgo_max': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'rango_critico_min': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'rango_critico_max': forms.NumberInput(attrs={'class': 'gm-form-input', 'step': '0.0001'}),
            'descripcion': forms.Textarea(attrs={'class': 'gm-form-input', 'rows': 3}),
            'importancia': forms.Select(attrs={'class': 'gm-form-input'}),
            'estado': forms.Select(attrs={'class': 'gm-form-input'}),
        }

    def clean(self):
        """
        Valida que los tres rangos esten ordenados y anidados correctamente.

        TipoParametro.clasificar() evalua normal, luego riesgo, y cae en
        critico. Si el rango normal no esta contenido en el de riesgo, hay
        valores que saltan de normal a critico sin pasar por riesgo.
        """
        datos = super().clean()

        pares = [
            ('normal', datos.get('rango_normal_min'), datos.get('rango_normal_max')),
            ('riesgo', datos.get('rango_riesgo_min'), datos.get('rango_riesgo_max')),
            ('critico', datos.get('rango_critico_min'), datos.get('rango_critico_max')),
        ]

        for nombre, minimo, maximo in pares:
            if minimo is not None and maximo is not None and minimo >= maximo:
                self.add_error(f'rango_{nombre}_max',
                               f'El máximo del rango {nombre} debe ser mayor que su mínimo.')

        normal_min, normal_max = pares[0][1], pares[0][2]
        riesgo_min, riesgo_max = pares[1][1], pares[1][2]

        if None not in (normal_min, riesgo_min) and riesgo_min > normal_min:
            self.add_error('rango_riesgo_min',
                           'El rango de riesgo debe contener al rango normal.')
        if None not in (normal_max, riesgo_max) and riesgo_max < normal_max:
            self.add_error('rango_riesgo_max',
                           'El rango de riesgo debe contener al rango normal.')

        if normal_min is None or normal_max is None:
            self.add_error('rango_normal_min',
                           'El rango normal es obligatorio: sin él no se puede clasificar '
                           'ninguna lectura y todas se marcarían como críticas.')

        return datos
