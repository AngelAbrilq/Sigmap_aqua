"""
API de ingesta de BioAqua System.

Endpoints consumidos por los nodos ESP32:
    POST /api/v1/dispositivos/handshake/   Verifica enlace y credenciales.
    POST /api/v1/lecturas/                 Ingesta de mediciones reales.

Los nodos no acceden nunca a MySQL: solo hablan con esta capa, que valida,
clasifica y persiste. Las credenciales de base de datos jamas salen del servidor.
"""
import logging

from django.db import connection, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alertas.services import evaluar_lote, resolver_alertas_normalizadas

from .api_auth import dispositivo_requerido, marcar_conexion
from .models import Lectura
from .serializers import LecturaSalidaSerializer, LoteLecturasSerializer

logger = logging.getLogger(__name__)


def guardar_con_pk(lecturas):
    """
    Persiste el lote garantizando que cada Lectura quede con su PK.

    El motor de alertas enlaza cada Alerta con su Lectura (FK). En MySQL,
    bulk_create NO devuelve los ids insertados (no soporta RETURNING), asi que
    las lecturas quedaban sin PK y bulk_create de Alerta fallaba con
    "unsaved related object 'lectura'" en cuanto llegaba un valor fuera de
    rango. En motores con RETURNING (PostgreSQL, MariaDB >= 10.5, SQLite) se
    conserva la insercion en bloque; en MySQL se guarda una por una dentro de
    la misma transaccion (el lote trae como maximo 100 lecturas).

    :param lecturas: list de monitoreo.Lectura sin guardar
    :return: la misma lista, ya con PK
    """
    if connection.features.can_return_rows_from_bulk_insert:
        Lectura.objects.bulk_create(lecturas)
    else:
        for lectura in lecturas:
            lectura.save(force_insert=True)
    return lecturas


def respuesta(success, data=None, message='', codigo=status.HTTP_200_OK):
    """Formato JSON unico para toda la API: {success, data, message}."""
    return Response({'success': success, 'data': data, 'message': message}, status=codigo)


class BaseVistaDispositivo(APIView):
    """
    Base para endpoints de hardware.

    authentication_classes vacio a proposito: se evita SessionAuthentication para
    que el ESP32 no tope con CSRF. La autenticacion la hace @dispositivo_requerido.
    """
    authentication_classes = []
    permission_classes = []


class HandshakeView(BaseVistaDispositivo):
    """
    Verificacion de enlace. No registra mediciones.

    Sirve para validar, antes de cablear un solo sensor, que el nodo alcanza el
    servidor, que su token es valido y que la piscina asignada es la correcta.
    Devuelve la hora del servidor: el ESP32 no tiene reloj con bateria y al
    reiniciar cree estar en 1970.
    """

    @dispositivo_requerido
    def post(self, request):
        dispositivo = request.dispositivo
        payload = request.data if isinstance(request.data, dict) else {}

        marcar_conexion(
            dispositivo,
            ip=request.ip_dispositivo,
            mac=payload.get('mac'),
            firmware=payload.get('firmware'),
        )

        sensores = dispositivo.geomembrana.sensores.filter(estado='activo')

        logger.info(
            'Handshake OK dispositivo=%s ip=%s rssi=%s',
            dispositivo.codigo, request.ip_dispositivo, payload.get('rssi'),
        )

        return respuesta(
            True,
            data={
                'dispositivo': dispositivo.codigo,
                'piscina': str(dispositivo.geomembrana),
                'ip_detectada': request.ip_dispositivo,
                'hora_servidor': timezone.now().isoformat(),
                'sensores_esperados': [
                    {
                        'codigo_hardware': s.codigo_hardware,
                        'parametro': s.tipo_parametro.nombre_parametro,
                        'unidad': s.tipo_parametro.unidad_medida,
                        'intervalo_segundos': s.intervalo_lectura_segundos,
                    }
                    for s in sensores
                ],
            },
            message=f'Enlace establecido con {dispositivo.codigo}.',
        )


class IngestaLecturasView(BaseVistaDispositivo):
    """
    Recibe un lote de mediciones reales y las persiste.

    Cada lectura se clasifica contra los rangos configurados en TipoParametro
    (normal / riesgo / critico) del lado del servidor, nunca del lado del nodo.
    Tras persistir el lote se invoca el motor de alertas, que abre las alertas
    de los parametros fuera de rango y cierra las que volvieron a la normalidad.
    """

    @dispositivo_requerido
    @transaction.atomic
    def post(self, request):
        dispositivo = request.dispositivo
        serializer = LoteLecturasSerializer(
            data=request.data, context={'dispositivo': dispositivo}
        )

        if not serializer.is_valid():
            return respuesta(
                False, data=serializer.errors,
                message='Lote rechazado.', codigo=status.HTTP_400_BAD_REQUEST,
            )

        validadas = serializer.validated_data['lecturas']
        errores_parciales = getattr(serializer, 'errores_parciales', [])
        ahora = timezone.now()
        # RF019 (modo offline): al reenviar lecturas encoladas en el ESP32 tras
        # una caida de red, se evitan duplicados por (sensor, timestamp). Solo
        # aplica a lecturas con timestamp explicito; una lectura en vivo (sin
        # timestamp) siempre se inserta.
        con_ts = [i for i in validadas if i.get('timestamp')]
        ya_existentes = set()
        if con_ts:
            ya_existentes = set(
                Lectura.objects.filter(
                    sensor_id__in={i['_sensor'].id for i in con_ts},
                    timestamp_lectura__in={i['timestamp'] for i in con_ts},
                ).values_list('sensor_id', 'timestamp_lectura')
            )

        persistidas = []
        duplicadas = 0

        for item in validadas:
            sensor = item['_sensor']
            valor = item['valor']
            tipo = sensor.tipo_parametro

            ts = item.get('timestamp')
            if ts is not None and (sensor.id, ts) in ya_existentes:
                duplicadas += 1
                continue

            clasificacion = tipo.clasificar(valor)

            persistidas.append(Lectura(
                sensor=sensor,
                geomembrana=sensor.geomembrana,
                tipo_parametro=tipo,
                valor_medida=valor,
                estado_lectura=clasificacion,
                dentro_rango=(clasificacion == 'normal'),
                timestamp_lectura=item.get('timestamp') or ahora,
                dispositivo=dispositivo,
                secuencia=item.get('secuencia'),
            ))

        guardar_con_pk(persistidas)

        # El motor de alertas se ejecuta DENTRO de la misma transaccion que las
        # lecturas: si algo falla al evaluar, no queda un lote persistido sin su
        # alerta correspondiente. Antes este paso no existia y el modulo de
        # alertas nunca llegaba a poblarse.
        alertas_nuevas = evaluar_lote(persistidas)
        alertas_cerradas = resolver_alertas_normalizadas(persistidas)

        marcar_conexion(
            dispositivo,
            ip=request.ip_dispositivo,
            mac=serializer.validated_data.get('mac'),
            firmware=serializer.validated_data.get('firmware'),
        )

        criticas = [l for l in persistidas if l.estado_lectura == 'critico']
        if criticas:
            logger.warning(
                'Lecturas CRITICAS en %s: %s',
                dispositivo.geomembrana,
                ', '.join(f'{l.sensor.codigo_hardware}={l.valor_medida}' for l in criticas),
            )

        return respuesta(
            True,
            data={
                'registradas': len(persistidas),
                'duplicadas': duplicadas,
                'criticas': len(criticas),
                'alertas_generadas': len(alertas_nuevas),
                'alertas_cerradas': alertas_cerradas,
                'rechazadas': errores_parciales,
                'hora_servidor': ahora.isoformat(),
                'lecturas': LecturaSalidaSerializer(persistidas, many=True).data,
            },
            message=f'{len(persistidas)} lectura(s) registrada(s).',
            codigo=status.HTTP_201_CREATED,
        )
