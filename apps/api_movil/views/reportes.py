"""
Reportes del historial de lecturas en PDF y Excel.

Usa el MISMO filtrado (`_filtrar_lecturas`) y los MISMOS generadores
(`apps.monitoreo.exportacion`) que los botones de exportar de la web: el
archivo que se descarga en el celular es idéntico al del navegador.
"""
import logging
from types import SimpleNamespace

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.monitoreo import exportacion
from apps.monitoreo.models import TipoParametro
from apps.monitoreo.views_web import MAX_FILAS_EXPORT, _filtrar_lecturas

from ..permisos import PermisoModulo
from ..respuestas import respuesta
from ..serializers import FiltroReporteSerializer, TipoParametroSerializer

logger = logging.getLogger(__name__)

FORMATOS = {
    'pdf': ('application/pdf', exportacion.MAX_FILAS_PDF, exportacion.generar_pdf),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
             MAX_FILAS_EXPORT, exportacion.generar_excel),
}


def _filtros_validados(request):
    """
    Valida los query params y los traduce al formato de `_filtrar_lecturas`.

    :return: (dict validado, queryset filtrado, dict de filtros aplicados)
    """
    entrada = FiltroReporteSerializer(data=request.query_params)
    entrada.is_valid(raise_exception=True)
    datos = entrada.validated_data

    parametros_web = {
        'desde': datos['desde'].isoformat() if datos.get('desde') else '',
        'hasta': datos['hasta'].isoformat() if datos.get('hasta') else '',
        'piscina': str(datos.get('geomembrana') or ''),
        'parametro': str(datos.get('parametro') or ''),
        'estado': datos.get('estado') or '',
    }
    filtros, queryset = _filtrar_lecturas(SimpleNamespace(GET=parametros_web))
    return datos, queryset, filtros


class ParametrosView(ListAPIView):
    """GET parametros/ -> parámetros activos, para los filtros de reportes."""

    serializer_class = TipoParametroSerializer
    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'historial'
    pagination_class = None

    def get_queryset(self):
        return TipoParametro.objects.filter(estado='activo').order_by('nombre_parametro')

    def list(self, request, *args, **kwargs):
        return respuesta(True, self.get_serializer(self.get_queryset(), many=True).data,
                         'Parámetros activos.')


class ResumenReporteView(APIView):
    """
    GET reportes/historial/resumen/?geomembrana=&parametro=&estado=&desde=&hasta=

    Vista previa del reporte: totales y estadísticas por parámetro, para que
    el usuario confirme los filtros antes de descargar el archivo.
    """

    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'historial'

    def get(self, request, *args, **kwargs):
        _, queryset, filtros = _filtros_validados(request)
        ctx = exportacion.construir_contexto(filtros, queryset, request.user, limite=0)

        def numero(valor):
            return None if valor is None else round(float(valor), 4)

        return respuesta(True, {
            'filtros': [{'etiqueta': etiqueta, 'valor': str(valor)}
                        for etiqueta, valor in ctx.filtros],
            'total': ctx.resumen_total.get('total') or 0,
            'fuera_rango': ctx.resumen_total.get('fuera_rango') or 0,
            'criticas': ctx.resumen_total.get('criticas') or 0,
            'riesgo': ctx.resumen_total.get('riesgo') or 0,
            'parametros': [{
                'parametro': fila['tipo_parametro__nombre_parametro'],
                'unidad': fila['tipo_parametro__unidad_medida'] or '',
                'total': fila['total'],
                'fuera_rango': fila['fuera_rango'],
                'pct_fuera': round(fila['pct_fuera'], 1),
                'promedio': numero(fila['promedio']),
                'minimo': numero(fila['minimo']),
                'maximo': numero(fila['maximo']),
            } for fila in ctx.resumen_parametros],
            'max_filas_pdf': exportacion.MAX_FILAS_PDF,
            'max_filas_excel': MAX_FILAS_EXPORT,
        }, 'Vista previa del reporte.')


class DescargaReporteView(APIView):
    """
    GET reportes/historial/?formato=pdf|xlsx&geomembrana=&parametro=&estado=&desde=&hasta=

    Devuelve el archivo binario. Los errores de validación siguen saliendo
    en JSON {success, data, message} para que la app los muestre.
    """

    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'historial'

    def get(self, request, *args, **kwargs):
        datos, queryset, filtros = _filtros_validados(request)
        formato = datos.get('formato', 'pdf')
        tipo, limite, generador = FORMATOS[formato]

        ctx = exportacion.construir_contexto(filtros, queryset, request.user, limite)
        contenido = generador(ctx)
        logger.info('Reporte %s (móvil) por %s: %s filas',
                    formato.upper(), request.user.email, len(ctx.lecturas))

        marca = timezone.localtime().strftime('%Y%m%d_%H%M')
        archivo = HttpResponse(contenido, content_type=tipo)
        archivo['Content-Disposition'] = f'attachment; filename="historial_{marca}.{formato}"'
        return archivo
