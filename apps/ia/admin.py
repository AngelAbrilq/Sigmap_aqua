from django.contrib import admin

from .models import AnalisisIA, Prediccion


class PrediccionInline(admin.TabularInline):
    """Las predicciones se leen junto al analisis que las generó."""
    model = Prediccion
    extra = 0
    readonly_fields = ('valor_real', 'error_absoluto', 'lecturas_evaluadas',
                       'fecha_evaluacion')


@admin.register(AnalisisIA)
class AnalisisIAAdmin(admin.ModelAdmin):
    list_display = ('geomembrana', 'tipo_analisis', 'confianza', 'estado',
                    'fecha_generacion')
    list_filter = ('tipo_analisis', 'estado', 'geomembrana')
    readonly_fields = ('datos_entrada', 'resultados_salida', 'fecha_generacion')
    list_select_related = ('geomembrana',)
    inlines = [PrediccionInline]


@admin.register(Prediccion)
class PrediccionAdmin(admin.ModelAdmin):
    list_display = ('geomembrana', 'tipo_parametro', 'fecha_objetivo',
                    'valor_esperado', 'valor_real', 'estado')
    list_filter = ('estado', 'tipo_parametro', 'geomembrana')
    readonly_fields = ('valor_real', 'error_absoluto', 'lecturas_evaluadas',
                       'fecha_evaluacion', 'fecha_generacion')
    list_select_related = ('geomembrana', 'tipo_parametro')
    date_hierarchy = 'fecha_objetivo'
