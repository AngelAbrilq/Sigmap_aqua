from django.contrib import admin
from .models import Alerta, HistorialEstadoAgua


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ('fecha_generacion', 'geomembrana', 'tipo_parametro',
                    'severidad', 'valor_que_disparo', 'estado')
    list_filter = ('estado', 'severidad', 'tipo_alerta', 'geomembrana')
    search_fields = ('mensaje_alerta',)
    date_hierarchy = 'fecha_generacion'
    list_select_related = ('geomembrana', 'tipo_parametro')


@admin.register(HistorialEstadoAgua)
class HistorialEstadoAguaAdmin(admin.ModelAdmin):
    list_display = ('fecha_evaluacion', 'geomembrana', 'estado_general', 'apta_produccion')
    list_filter = ('estado_general', 'apta_produccion', 'geomembrana')
    date_hierarchy = 'fecha_evaluacion'