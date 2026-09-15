"""
Formularios del modulo de infraestructura.

La validacion vive aqui, separada del controlador: la vista solo decide el
flujo, el formulario decide si el dato es aceptable. Todo campo que llega por
POST pasa por este filtro; nada se escribe con datos crudos del request.
"""
from datetime import date
from decimal import Decimal

from django import forms

from .models import EtapaProduccion, Geomembrana


class GeomembranaForm(forms.ModelForm):
    """
    Alta y edicion de geomembranas.

    Django escapa el HTML por defecto al renderizar, y el ORM parametriza las
    consultas: eso cubre XSS e inyeccion SQL. Lo que este formulario agrega es
    la coherencia del dominio (fechas, geometria, garantia vs vida util).
    """

    class Meta:
        model = Geomembrana
        fields = [
            'nombre_piscina', 'codigo_identificacion', 'descripcion', 'ubicacion',
            'area_m2', 'profundidad_promedio', 'volumen_agua_m3', 'capacidad_maxima_peces',
            'etapa_actual',
            'material', 'espesor_mm', 'proveedor', 'garantia_anios', 'vida_util_anios',
            'fecha_instalacion', 'fecha_ultimo_mantenimiento',
            'apta_para_produccion', 'estado',
        ]
        widgets = {
            'nombre_piscina': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. Geomembrana Piscina 1',
                'maxlength': 100,
            }),
            'codigo_identificacion': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. GEO-001',
                'maxlength': 50, 'style': 'text-transform:uppercase;',
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'gm-form-input', 'rows': 3,
                'placeholder': 'Observaciones relevantes de la lámina...',
            }),
            'ubicacion': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. Lote norte, bloque B',
            }),
            'area_m2': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'step': '0.01', 'min': '0.01', 'placeholder': '2500.00',
            }),
            'profundidad_promedio': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'step': '0.01', 'min': '0.01', 'placeholder': '1.80',
            }),
            'volumen_agua_m3': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'step': '0.01', 'min': '0',
                'placeholder': 'Se calcula solo si lo dejas vacío',
            }),
            'capacidad_maxima_peces': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'min': '0', 'placeholder': '12000',
            }),
            'etapa_actual': forms.Select(attrs={'class': 'gm-form-input'}),
            'material': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. HDPE',
            }),
            'espesor_mm': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'step': '0.01', 'min': '0.01', 'placeholder': '1.50',
            }),
            'proveedor': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Ej. GeoLáminas S.A.S.',
            }),
            'garantia_anios': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'min': '0', 'max': '50', 'placeholder': '10',
            }),
            'vida_util_anios': forms.NumberInput(attrs={
                'class': 'gm-form-input', 'min': '1', 'max': '50', 'placeholder': '10',
            }),
            'fecha_instalacion': forms.DateInput(attrs={
                'class': 'gm-form-input', 'type': 'date',
            }, format='%Y-%m-%d'),
            'fecha_ultimo_mantenimiento': forms.DateInput(attrs={
                'class': 'gm-form-input', 'type': 'date',
            }, format='%Y-%m-%d'),
            'apta_para_produccion': forms.CheckboxInput(attrs={'class': 'gm-form-check'}),
            'estado': forms.Select(attrs={'class': 'gm-form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo se ofrecen etapas vigentes: asignar una etapa retirada deja la
        # piscina con rangos objetivo que ya nadie mantiene.
        self.fields['etapa_actual'].queryset = EtapaProduccion.objects.filter(estado='activo')
        self.fields['etapa_actual'].empty_label = 'Sin etapa asignada'

        # Campos minimos para que la ficha sea util en el listado.
        self.fields['nombre_piscina'].required = True
        self.fields['codigo_identificacion'].required = True

    # ------------------------------------------------------------------
    # Validacion por campo
    # ------------------------------------------------------------------
    def clean_codigo_identificacion(self):
        """
        Normaliza el codigo a mayusculas y verifica que no exista ya.

        La unicidad la garantiza la BD, pero validarla aqui devuelve un error
        de campo legible en vez de un IntegrityError.

        :return: str con el codigo normalizado
        :raises ValidationError: si el codigo ya pertenece a otra geomembrana
        """
        codigo = (self.cleaned_data.get('codigo_identificacion') or '').strip().upper()
        if not codigo:
            raise forms.ValidationError('El código es obligatorio.')

        duplicado = Geomembrana.objects.filter(codigo_identificacion=codigo)
        if self.instance.pk:
            duplicado = duplicado.exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise forms.ValidationError(f'Ya existe una geomembrana con el código {codigo}.')
        return codigo

    def clean_fecha_instalacion(self):
        """Impide registrar una instalacion en el futuro."""
        fecha = self.cleaned_data.get('fecha_instalacion')
        if fecha and fecha > date.today():
            raise forms.ValidationError('La fecha de instalación no puede ser futura.')
        return fecha

    def clean_fecha_ultimo_mantenimiento(self):
        """Impide registrar un mantenimiento en el futuro."""
        fecha = self.cleaned_data.get('fecha_ultimo_mantenimiento')
        if fecha and fecha > date.today():
            raise forms.ValidationError('El último mantenimiento no puede ser una fecha futura.')
        return fecha

    # ------------------------------------------------------------------
    # Validacion cruzada
    # ------------------------------------------------------------------
    def clean(self):
        """
        Reglas que dependen de mas de un campo.

        :return: dict con los datos validados
        """
        datos = super().clean()

        instalacion = datos.get('fecha_instalacion')
        mantenimiento = datos.get('fecha_ultimo_mantenimiento')
        area = datos.get('area_m2')
        profundidad = datos.get('profundidad_promedio')
        volumen = datos.get('volumen_agua_m3')
        garantia = datos.get('garantia_anios')
        vida_util = datos.get('vida_util_anios')
        capacidad = datos.get('capacidad_maxima_peces')
        etapa = datos.get('etapa_actual')
        apta = datos.get('apta_para_produccion')
        estado = datos.get('estado')

        # No se puede mantener algo que todavia no se instalo.
        if instalacion and mantenimiento and mantenimiento < instalacion:
            self.add_error(
                'fecha_ultimo_mantenimiento',
                'El mantenimiento no puede ser anterior a la instalación.',
            )

        # La garantia del fabricante nunca excede la vida util estimada.
        if garantia and vida_util and garantia > vida_util:
            self.add_error(
                'garantia_anios',
                'La garantía no puede superar la vida útil estimada de la lámina.',
            )

        # El volumen declarado debe ser coherente con la geometria (±20%).
        if volumen and area and profundidad:
            teorico = area * profundidad
            if teorico > 0:
                desvio = abs(volumen - teorico) / teorico
                if desvio > Decimal('0.20'):
                    self.add_error(
                        'volumen_agua_m3',
                        f'El volumen no cuadra con área × profundidad '
                        f'(≈ {teorico.quantize(Decimal("0.01"))} m³). '
                        f'Déjalo vacío para calcularlo automáticamente.',
                    )

        # La densidad de siembra de la etapa acota la capacidad declarada.
        if capacidad and area and etapa and etapa.densidad_peces_por_m2:
            maximo = int(area * etapa.densidad_peces_por_m2)
            if capacidad > maximo:
                self.add_error(
                    'capacidad_maxima_peces',
                    f'Supera la densidad de la etapa "{etapa.nombre_etapa}" '
                    f'({etapa.densidad_peces_por_m2} peces/m²). Máximo: {maximo}.',
                )

        # Una piscina inactiva o en mantenimiento no puede quedar marcada apta.
        if apta and estado in ('inactivo', 'mantenimiento'):
            self.add_error(
                'apta_para_produccion',
                'Una geomembrana inactiva o en mantenimiento no puede marcarse apta.',
            )

        return datos
