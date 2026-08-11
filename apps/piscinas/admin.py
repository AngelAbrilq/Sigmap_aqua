from django.contrib import admin
from .models import EtapaProduccion, Geomembrana


@admin.register(EtapaProduccion)
class EtapaProduccionAdmin(admin.ModelAdmin):
    list_display = ('nombre_etapa', 'dias_duracion', 'densidad_peces_por_m2', 'estado')
    list_filter = ('estado',)


@admin.register(Geomembrana)
class GeomembranaAdmin(admin.ModelAdmin):
    list_display = ('codigo_identificacion', 'nombre_piscina', 'etapa_actual',
                    'area_m2', 'apta_para_produccion', 'estado')
    list_filter = ('estado', 'etapa_actual', 'apta_para_produccion')
    search_fields = ('codigo_identificacion', 'nombre_piscina', 'ubicacion')
    list_select_related = ('etapa_actual',)