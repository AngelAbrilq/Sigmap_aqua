from django.contrib import admin

from .models import EventoSistema


@admin.register(EventoSistema)
class EventoSistemaAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tipo_evento', 'nivel', 'usuario', 'geomembrana', 'descripcion')
    list_filter = ('tipo_evento', 'nivel', 'created_at')
    search_fields = ('descripcion', 'usuario__email')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
