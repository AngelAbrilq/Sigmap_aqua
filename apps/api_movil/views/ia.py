"""
Inteligencia artificial desde la app: análisis predictivo y asistente.

Reutiliza los servicios del módulo web (apps.ia), así el celular y el panel
web consultan el mismo modelo (DeepSeek, con Gemini de respaldo), guardan en
las mismas tablas y aplican los mismos límites.
"""
import logging

from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.ia.asistente import LimiteConsultas, generar_excel, preguntar
from apps.ia.models import AnalisisIA, ConsultaIA
from apps.ia.services import ErrorIA, generar_analisis, ia_configurada
from apps.usuarios.permissions import ROL_INSTRUCTOR, obtener_nombre_rol

from ..permisos import PermisoLecturaModulo, PermisoModulo
from ..respuestas import respuesta
from ..serializers import (
    AnalisisIASerializer,
    GenerarAnalisisSerializer,
    PreguntaAsistenteSerializer,
)

logger = logging.getLogger(__name__)

TIPO_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class AnalisisIAView(ListAPIView):
    """
    GET  ia/analisis/?geomembrana=  -> historial de análisis (el más reciente primero).
    POST ia/analisis/               -> genera uno nuevo {geomembrana, tipo, dias, horizonte}.

    Generar consume cuota de la API de IA: exige permiso de ESCRITURA del
    módulo 'ai', igual que el botón "Generar" del panel web.
    """

    serializer_class = AnalisisIASerializer
    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'ai'

    def get_queryset(self):
        queryset = (
            AnalisisIA.objects
            .select_related('geomembrana')
            .annotate(num_predicciones=Count('predicciones'))
            .order_by('-fecha_generacion')
        )
        geomembrana = self.request.query_params.get('geomembrana', '')
        if geomembrana.isdigit():
            queryset = queryset.filter(geomembrana_id=geomembrana)
        return queryset

    def list(self, request, *args, **kwargs):
        pagina = self.paginate_queryset(self.get_queryset())
        return respuesta(True, {
            'total': self.paginator.page.paginator.count,
            'pagina': self.paginator.page.number,
            'paginas': self.paginator.page.paginator.num_pages,
            'ia_configurada': ia_configurada(),
            'resultados': self.get_serializer(pagina, many=True).data,
        }, 'Análisis de IA.')

    def post(self, request, *args, **kwargs):
        entrada = GenerarAnalisisSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        geomembrana = datos['geomembrana']

        try:
            analisis = generar_analisis(
                geomembrana, tipo=datos['tipo'], dias=datos['dias'],
                horizonte=datos['horizonte'])
        except ErrorIA as error:
            # Sin datos o IA caída: no es un error del sistema, se informa.
            logger.warning('Análisis IA (móvil) fallido para %s: %s',
                           geomembrana.codigo_identificacion, error)
            return respuesta(False, None, str(error), status.HTTP_503_SERVICE_UNAVAILABLE)

        analisis.num_predicciones = analisis.predicciones.count()
        logger.info('Análisis IA %s generado desde la app por %s', analisis.pk, request.user.email)
        return respuesta(True, AnalisisIASerializer(analisis).data,
                         f'Análisis generado para {geomembrana.nombre_piscina}.',
                         status.HTTP_201_CREATED)


class AsistenteIAView(APIView):
    """
    POST ia/asistente/ {"pregunta": "..."} -> respuesta estructurada del asistente.

    Mismo asistente que el círculo flotante de la web: responde con los datos
    reales del sistema y guarda la consulta para descargarla en Excel.
    """

    permission_classes = [IsAuthenticated, PermisoLecturaModulo]
    modulo = 'ai'

    def post(self, request, *args, **kwargs):
        entrada = PreguntaAsistenteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            consulta = preguntar(request.user, entrada.validated_data['pregunta'])
        except LimiteConsultas as error:
            return respuesta(False, None, str(error), status.HTTP_429_TOO_MANY_REQUESTS)
        except ErrorIA as error:
            logger.warning('Asistente IA (móvil) sin respuesta para %s: %s',
                           request.user.email, error)
            return respuesta(False, None, str(error), status.HTTP_503_SERVICE_UNAVAILABLE)

        datos = dict(consulta.respuesta)
        datos.update({
            'id': consulta.pk,
            'pregunta': consulta.pregunta,
            'modelo': consulta.modelo_usado,
            # La app descarga el Excel por la API móvil (JWT), no por la web.
            'tiene_excel': consulta.pk is not None,
        })
        return respuesta(True, datos, 'Respuesta generada.')


class AsistenteExcelView(APIView):
    """
    GET ia/asistente/<pk>/excel/ -> informe Excel de una respuesta del asistente.

    Solo su autor o el Instructor Líder; para el resto la consulta "no existe".
    """

    permission_classes = [IsAuthenticated, PermisoModulo]
    modulo = 'ai'

    def get(self, request, pk, *args, **kwargs):
        consulta = ConsultaIA.objects.select_related('usuario').filter(pk=pk).first()
        es_instructor = obtener_nombre_rol(request.user) == ROL_INSTRUCTOR
        if consulta is None or (consulta.usuario_id != request.user.pk and not es_instructor):
            return respuesta(False, None, 'Consulta no encontrada.', status.HTTP_404_NOT_FOUND)

        try:
            contenido = generar_excel(consulta)
        except Exception:  # noqa: BLE001 - se responde JSON y el detalle queda en el log
            logger.exception('Excel del asistente (móvil) falló para la consulta %s', pk)
            return respuesta(False, None, 'No se pudo generar el Excel.',
                             status.HTTP_500_INTERNAL_SERVER_ERROR)

        marca = timezone.localtime(consulta.fecha_creacion).strftime('%Y%m%d_%H%M')
        archivo = HttpResponse(contenido, content_type=TIPO_XLSX)
        archivo['Content-Disposition'] = (
            f'attachment; filename="asistente_ia_{marca}_{consulta.pk}.xlsx"')
        return archivo
