"""
Geomembranas y su estado actual.

La pantalla principal de la app: qué piscinas hay y cómo está el agua en cada
una ahora mismo.
"""
from django.db.models import Count, Max, Q, Subquery
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.monitoreo.models import Lectura

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
        Última medición de cada parámetro que mide esta piscina.

        Una consulta con subquery en vez de una por sensor. Se apoya en el
        índice (geomembrana, -timestamp_lectura) que ya existe.

        Incluye los parámetros SIN lectura: la app los pinta en gris con
        'Sin datos'. Omitirlos escondería un sensor mudo, que es justo la
        información que el operario necesita ver.
        """
        geomembrana = self.get_object()

        sensores = (
            geomembrana.sensores
            .filter(estado='activo')
            .select_related('tipo_parametro')
            .order_by('tipo_parametro__nombre_parametro')
        )

        ultimos_ids = (
            Lectura.objects
            .filter(geomembrana=geomembrana)
            .values('tipo_parametro')
            .annotate(ultimo=Max('id'))
            .values('ultimo')
        )
        recientes = {
            lectura.tipo_parametro_id: lectura
            for lectura in Lectura.objects
            .filter(id__in=Subquery(ultimos_ids))
            .select_related('tipo_parametro', 'sensor')
        }

        tarjetas = []
        for sensor in sensores:
            tipo = sensor.tipo_parametro
            lectura = recientes.get(tipo.id)
            tarjetas.append({
                'parametro_id': tipo.id,
                'parametro': tipo.nombre_parametro,
                'unidad': tipo.unidad_medida,
                'sensor': sensor.codigo_hardware,
                'valor_medida': str(lectura.valor_medida) if lectura else None,
                'estado_lectura': lectura.estado_lectura if lectura else 'sin_datos',
                'timestamp_lectura': lectura.timestamp_lectura if lectura else None,
                'rango_min': str(tipo.rango_normal_min) if tipo.rango_normal_min is not None else None,
                'rango_max': str(tipo.rango_normal_max) if tipo.rango_normal_max is not None else None,
            })

        return respuesta(True, {
            'geomembrana': geomembrana.id,
            'nombre': geomembrana.nombre_piscina,
            'estado_operativo': geomembrana.estado_operativo,
            'estado_operativo_label': geomembrana.estado_operativo_label,
            'alertas_activas': geomembrana.alertas_activas.count(),
            'parametros': UltimaLecturaSerializer(tarjetas, many=True).data,
        }, f'Estado actual de {geomembrana.nombre_piscina}.')
