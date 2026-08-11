from django.contrib import admin
from .models import TipoParametro, Sensor, Dispositivo, Lectura


@admin.register(TipoParametro)
class TipoParametroAdmin(admin.ModelAdmin):
    list_display = ('nombre_parametro', 'unidad_medida', 'rango_normal_min',
                    'rango_normal_max', 'importancia', 'estado')
    list_filter = ('importancia', 'estado')


@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'geomembrana', 'firmware_version',
                    'ultima_conexion', 'estado')
    list_filter = ('estado', 'geomembrana')
    search_fields = ('codigo', 'mac_address')
    readonly_fields = ('token',)


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ('codigo_hardware', 'nombre_sensor', 'geomembrana',
                    'tipo_parametro', 'bateria_nivel_actual',
                    'proxima_calibracion', 'estado')
    list_filter = ('estado', 'geomembrana', 'tipo_parametro')
    search_fields = ('codigo_hardware', 'nombre_sensor', 'mac_address')
    list_select_related = ('geomembrana', 'tipo_parametro')


@admin.register(Lectura)
class LecturaAdmin(admin.ModelAdmin):
    list_display = ('timestamp_lectura', 'sensor', 'valor_medida',
                    'estado_lectura', 'dentro_rango')
    list_filter = ('estado_lectura', 'dentro_rango', 'geomembrana', 'tipo_parametro')
    date_hierarchy = 'timestamp_lectura'
    list_select_related = ('sensor', 'geomembrana', 'tipo_parametro')
    readonly_fields = ('fecha_recepcion',)