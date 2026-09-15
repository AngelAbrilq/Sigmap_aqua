from django.contrib import admin

from .models import AnalisisIA


@admin.register(AnalisisIA)
class AnalisisIAAdmin(admin.ModelAdmin):
    list_display = ('geomembrana', 'tipo_analisis', 'confianza', 'estado', 'fecha_generacion')
    list_filter = ('tipo_analisis', 'estado', 'geomembrana')
    readonly_fields = ('datos_entrada', 'resultados_salida', 'fecha_generacion')
    list_select_related = ('geomembrana',)
