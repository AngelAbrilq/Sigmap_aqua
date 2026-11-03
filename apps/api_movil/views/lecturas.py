"""
Historial de mediciones.

La tabla `lecturas_sensores` crece sin límite: todo se filtra y pagina en la
base de datos, nunca en Python.
"""
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.monitoreo.models import Lectura

from ..permisos import PermisoModulo
from ..respuestas import respuesta
from ..serializers import FiltroHistorialSerializer, LecturaSerializer


class HistorialLecturasView(ListAPIView):
    """
    GET lecturas/?geomembrana=&parametro=&desde=&hasta=&estado=

    Los query params se validan con un serializer antes de tocar el ORM: así
    un `?desde=ayer` devuelve un 400 con el campo señalado en vez de reventar
    a mitad de la consulta.
    """

    serializer_class = LecturaSerializer
    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'historial'

    def get_queryset(self):
        filtros = FiltroHistorialSerializer(data=self.request.query_params)
        filtros.is_valid(raise_exception=True)
        datos = filtros.validated_data

        queryset = Lectura.objects.select_related(
            'tipo_parametro', 'sensor', 'geomembrana')

        if datos.get('geomembrana'):
            queryset = queryset.filter(geomembrana_id=datos['geomembrana'])
        if datos.get('parametro'):
            queryset = queryset.filter(tipo_parametro_id=datos['parametro'])
        if datos.get('desde'):
            queryset = queryset.filter(timestamp_lectura__date__gte=datos['desde'])
        if datos.get('hasta'):
            queryset = queryset.filter(timestamp_lectura__date__lte=datos['hasta'])
        if datos.get('estado'):
            queryset = queryset.filter(estado_lectura=datos['estado'])

        return queryset

    def list(self, request, *args, **kwargs):
        pagina = self.paginate_queryset(self.get_queryset())
        return respuesta(True, {
            'total': self.paginator.page.paginator.count,
            'pagina': self.paginator.page.number,
            'paginas': self.paginator.page.paginator.num_pages,
            'resultados': self.get_serializer(pagina, many=True).data,
        }, 'Historial de lecturas.')
