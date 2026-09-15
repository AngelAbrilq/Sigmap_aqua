from django.contrib import admin

from .models import ComparacionDatos, Reporte


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'geomembrana', 'tipo_reporte',
                    'fecha_inicio', 'fecha_fin', 'generado_por')
    list_filter = ('tipo_reporte', 'geomembrana')
    readonly_fields = ('datos_reporte', 'fecha_creacion')
    list_select_related = ('geomembrana', 'generado_por')


@admin.register(ComparacionDatos)
class ComparacionDatosAdmin(admin.ModelAdmin):
    list_display = ('geomembrana', 'periodo_1_inicio', 'periodo_2_inicio', 'fecha_creacion')
    readonly_fields = ('resultados_comparacion', 'fecha_creacion')
    list_select_related = ('geomembrana',)
