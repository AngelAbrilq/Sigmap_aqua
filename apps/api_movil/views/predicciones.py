"""
Predicciones de IA vigentes.

Solo lectura: generar un análisis consume cuota de la API de Gemini y es una
decisión que se toma desde la web, no desde el celular en medio del estanque.
"""
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.ia.models import Prediccion
from apps.ia.services import precision_historica
from apps.piscinas.models import Geomembrana

from ..permisos import PermisoModulo
from ..respuestas import respuesta
from ..serializers import PrediccionSerializer


class PrediccionesView(ListAPIView):
    """
    GET predicciones/?geomembrana=&estado=

    Devuelve además la precisión histórica del modelo: una predicción sin su
    porcentaje de acierto es una opinión, y la app debe mostrar ambas cosas
    juntas para que el operario sepa cuánto confiar.
    """

    serializer_class = PrediccionSerializer
    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'ai'

    def get_queryset(self):
        queryset = Prediccion.objects.con_relaciones()

        geomembrana = self.request.query_params.get('geomembrana')
        if geomembrana and geomembrana.isdigit():
            queryset = queryset.filter(geomembrana_id=geomembrana)

        estado = self.request.query_params.get('estado')
        if estado in dict(Prediccion.ESTADOS):
            queryset = queryset.filter(estado=estado)

        return queryset

    def list(self, request, *args, **kwargs):
        piscina = None
        crudo = request.query_params.get('geomembrana')
        if crudo and crudo.isdigit():
            piscina = Geomembrana.objects.filter(pk=crudo).first()

        pagina = self.paginate_queryset(self.get_queryset())
        return respuesta(True, {
            'total': self.paginator.page.paginator.count,
            'pagina': self.paginator.page.number,
            'paginas': self.paginator.page.paginator.num_pages,
            'precision': precision_historica(piscina),
            'resultados': self.get_serializer(pagina, many=True).data,
        }, 'Predicciones de IA.')
