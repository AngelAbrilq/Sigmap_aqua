"""
Geomembranas y su estado actual.

La pantalla principal de la app: qué piscinas hay y cómo está el agua en cada
una ahora mismo.
"""
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.monitoreo.models import TipoParametro
# Misma fuente de verdad que el tablero web: si cambian los rangos por etapa,
# el oxigeno simulado o el intervalo de refresco, la app cambia con la web.
from apps.monitoreo.views_web import _estado_sensores, _intervalo_refresco

from ..permisos import PermisoModulo
from ..respuestas import respuesta
from ..serializers import (
    GeomembranaDetalleSerializer,
    GeomembranaListaSerializer,
    UltimaLecturaSerializer,
)
from apps.piscinas.models import Geomembrana


class GeomembranaViewSet(ReadOnlyModelViewSet):
    """
    Solo lectura: el alta y la edición de piscinas siguen siendo de la web.

    Un operario en campo consulta desde el celular; dar de alta una geomembrana
    con veinte campos en una pantalla de 5 pulgadas no le sirve a nadie.
    """

    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'geomembranas'

    def get_queryset(self):
        """
        Listado con el conteo de alertas resuelto en la misma consulta.

        Sin el annotate, el serializer contaría alertas por cada fila: N+1
        contra la tabla más consultada del módulo.
        """
        return (
            Geomembrana.objects
            .select_related('etapa_actual')
            .annotate(total_alertas_activas=Count(
                'alertas', filter=Q(alertas__estado='activa'), distinct=True))
            .order_by('codigo_identificacion')
        )

    def get_serializer_class(self):
        return (GeomembranaDetalleSerializer if self.action == 'retrieve'
                else GeomembranaListaSerializer)

    def list(self, request, *args, **kwargs):
        pagina = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        datos = self.get_serializer(pagina, many=True).data
        # paginator.get_paginated_response devolvería {count, next, results}:
        # se re-envuelve para mantener el contrato de la API.
        return respuesta(True, {
            'total': self.paginator.page.paginator.count,
            'pagina': self.paginator.page.number,
            'paginas': self.paginator.page.paginator.num_pages,
            'resultados': datos,
        }, 'Listado de geomembranas.')

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return respuesta(True, serializer.data, 'Detalle de la geomembrana.')

    @action(detail=True, url_path='ultimas-lecturas')
    def ultimas_lecturas(self, request, pk=None):
        """
        Estado actual de la piscina, identico al tablero web de monitoreo.

        Reutiliza `_estado_sensores` de la web: ultima lectura por sensor activo,
        rangos efectivos segun la etapa de produccion y la tarjeta de oxigeno
        simulado mientras no haya sensor real. Asi el celular y el navegador
        muestran exactamente los mismos valores, estados y rangos.

        Incluye los sensores SIN lectura ('sin_datos'): omitirlos esconderia un
        sensor mudo, que es justo lo que el operario necesita ver.
        """
        geomembrana = self.get_object()
        tarjetas = _estado_sensores(geomembrana)
        ids_por_nombre = dict(
            TipoParametro.objects.values_list('nombre_parametro', 'id'))

        parametros = [{
            'parametro_id': ids_por_nombre.get(t['parametro'], 0),
            'parametro': t['parametro'],
            'unidad': t['unidad'] or '',
            'sensor': t['sensor'].codigo_hardware,
            'sensor_nombre': t['sensor'].nombre_sensor,
            'valor_medida': _texto_decimal(t['valor']),
            'estado_lectura': t['estado'],
            'timestamp_lectura': t['momento'],
            'rango_min': _texto_decimal(t['rango_min']),
            'rango_max': _texto_decimal(t['rango_max']),
            'rango_fuente': t['rango_fuente'],
            'simulado': t.get('simulado', False),
        } for t in tarjetas]

        return respuesta(True, {
            'geomembrana': geomembrana.id,
            'nombre': geomembrana.nombre_piscina,
            'estado_operativo': geomembrana.estado_operativo,
            'estado_operativo_label': geomembrana.estado_operativo_label,
            'alertas_activas': geomembrana.alertas_activas.count(),
            # Segundos entre refrescos: la app usa el mismo ritmo que la web.
            'intervalo_refresco': _intervalo_refresco(geomembrana),
            'actualizado': timezone.now(),
            'parametros': UltimaLecturaSerializer(parametros, many=True).data,
        }, f'Estado actual de {geomembrana.nombre_piscina}.')


def _texto_decimal(valor):
    """
    Decimal como texto exacto ('7.2000'); float con 4 decimales; None se respeta.

    Se envia como texto para que el celular no pierda precision al parsear.
    """
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return str(valor)
    return f'{float(valor):.4f}'
