"""
Alertas y notificaciones desde el móvil.

Es el módulo que justifica la app: un operario en campo recibe el aviso y
resuelve ahí mismo, sin volver al computador.
"""
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.alertas.models import Alerta, Notificacion
from apps.alertas.services import AccionInvalida, reconocer_alerta, resolver_alerta

from ..permisos import PermisoModulo
from ..respuestas import respuesta
from ..serializers import (
    AlertaSerializer,
    NotificacionSerializer,
    ResolverAlertaSerializer,
)


class AlertaViewSet(ReadOnlyModelViewSet):
    """
    Bandeja de alertas con las acciones de atención.

    Las alertas no se crean a mano: las genera el motor cuando la API de
    ingesta recibe una lectura fuera de rango. Por eso es ReadOnly + acciones.
    """

    serializer_class = AlertaSerializer
    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'alertas'

    def get_queryset(self):
        """
        Base sin filtrar.

        Los filtros del listado NO se aplican aqui a proposito: get_object()
        usa este mismo queryset, y filtrar por estado='activa' dejaria en 404
        cualquier accion sobre una alerta que acaba de cambiar de estado.
        La app reconoce una alerta y, al intentar resolverla, ya no la
        encontraria.
        """
        return Alerta.objects.select_related(
            'geomembrana', 'tipo_parametro', 'sensor', 'usuario_reconocimiento')

    def _queryset_listado(self):
        """
        Queryset del listado, con los filtros de la querystring.

        :return: QuerySet de Alerta filtrado
        """
        queryset = self.get_queryset()

        # Por defecto la bandeja muestra lo pendiente: es lo que el operario
        # abre la app para ver. `?estado=` (vacio) trae todas.
        estado = self.request.query_params.get('estado', 'activa')
        if estado and estado in dict(Alerta.ESTADOS):
            queryset = queryset.filter(estado=estado)

        severidad = self.request.query_params.get('severidad')
        if severidad in dict(Alerta.SEVERIDADES):
            queryset = queryset.filter(severidad=severidad)

        geomembrana = self.request.query_params.get('geomembrana')
        if geomembrana and geomembrana.isdigit():
            queryset = queryset.filter(geomembrana_id=geomembrana)

        return queryset

    def list(self, request, *args, **kwargs):
        pagina = self.paginate_queryset(self._queryset_listado())
        return respuesta(True, {
            'total': self.paginator.page.paginator.count,
            'pagina': self.paginator.page.number,
            'paginas': self.paginator.page.paginator.num_pages,
            'resultados': self.get_serializer(pagina, many=True).data,
        }, 'Listado de alertas.')

    def retrieve(self, request, *args, **kwargs):
        return respuesta(True, self.get_serializer(self.get_object()).data,
                         'Detalle de la alerta.')

    @action(detail=True, methods=['post'])
    def reconocer(self, request, pk=None):
        """
        POST alertas/{id}/reconocer/

        Es POST y no GET porque cambia el estado del sistema: exige permiso de
        escritura, que PermisoModulo verifica por el método HTTP.
        """
        alerta = self.get_object()
        try:
            reconocer_alerta(alerta, request.user)
        except AccionInvalida as error:
            return respuesta(False, None, str(error), 409)

        return respuesta(True, self.get_serializer(alerta).data, 'Alerta reconocida.')

    @action(detail=True, methods=['post'])
    def resolver(self, request, pk=None):
        """POST alertas/{id}/resolver/ con {accion_tomada}."""
        entrada = ResolverAlertaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        alerta = self.get_object()
        try:
            resolver_alerta(alerta, request.user, entrada.validated_data['accion_tomada'])
        except AccionInvalida as error:
            return respuesta(False, None, str(error), 409)

        return respuesta(True, self.get_serializer(alerta).data, 'Alerta resuelta.')


class NotificacionesView(APIView):
    """
    Bandeja personal del usuario autenticado.

    Sin `modulo`: cada quien ve las suyas, no depende del RBAC por módulo.
    """

    permission_classes = [IsAuthenticated, PermisoModulo]

    def get(self, request):
        """GET notificaciones/?solo_no_leidas=1"""
        queryset = Notificacion.objects.filter(
            usuario=request.user).select_related('alerta')

        if request.query_params.get('solo_no_leidas') in ('1', 'true', 'True'):
            queryset = queryset.filter(leida=False)

        limite = queryset[:50]
        return respuesta(True, {
            'no_leidas': Notificacion.objects.filter(
                usuario=request.user, leida=False).count(),
            'resultados': NotificacionSerializer(limite, many=True).data,
        }, 'Notificaciones.')

    def post(self, request):
        """
        POST notificaciones/leidas/ → marca todas como leídas.

        Un solo UPDATE en vez de recorrer e ir guardando una por una.
        """
        actualizadas = Notificacion.objects.filter(
            usuario=request.user, leida=False
        ).update(leida=True, fecha_lectura=timezone.now())

        return respuesta(True, {'actualizadas': actualizadas},
                         f'{actualizadas} notificación(es) marcadas como leídas.')
