"""
Logica de negocio de alertas.

Reemplaza al trigger `tr_crear_alerta_lectura_fuera_rango` del esquema SQL:
la regla vive en la aplicacion, donde se puede versionar y probar, no en la
base de datos.

Esta capa la invoca la ingesta de la API (apps.monitoreo.views) despues de
persistir cada lote de lecturas.
"""
import logging

from django.db import transaction

from .models import Alerta, HistorialEstadoAgua, Notificacion

logger = logging.getLogger(__name__)

# Clasificacion de la lectura -> severidad de la alerta que genera.
SEVERIDAD_POR_ESTADO = {
    'riesgo': 'media',
    'critico': 'critica',
}

# Severidad -> roles que deben recibir la notificacion.
# Los nombres coinciden EXACTAMENTE con usuarios.permissions (sin tildes).
DESTINATARIOS_POR_SEVERIDAD = {
    'critica': ['Instructor Lider', 'Operario'],
    'media': ['Operario'],
}


def evaluar_lote(lecturas):
    """
    Evalua un lote de lecturas ya persistidas y genera las alertas del caso.

    Se llama una sola vez por lote en vez de una por lectura: un ESP32 envia
    varias mediciones juntas y consultar las alertas activas en cada iteracion
    seria N+1 contra la tabla mas caliente del sistema.

    :param lecturas: iterable de monitoreo.Lectura ya guardadas
    :return: list de Alerta creadas
    """
    fuera_de_rango = [lec for lec in lecturas if lec.estado_lectura != 'normal']
    if not fuera_de_rango:
        return []

    # Una sola consulta para saber que combinaciones ya tienen alerta abierta.
    abiertas = set(
        Alerta.objects
        .filter(estado='activa', geomembrana__in={lec.geomembrana_id for lec in fuera_de_rango})
        .values_list('geomembrana_id', 'tipo_parametro_id')
    )

    nuevas = []
    for lectura in fuera_de_rango:
        clave = (lectura.geomembrana_id, lectura.tipo_parametro_id)
        if clave in abiertas:
            # Ya hay una alerta abierta por este parametro: no se duplica en
            # cada lectura consecutiva del mismo problema.
            continue

        nuevas.append(Alerta(
            geomembrana=lectura.geomembrana,
            sensor=lectura.sensor,
            tipo_parametro=lectura.tipo_parametro,
            lectura=lectura,
            tipo_alerta=lectura.estado_lectura,
            severidad=SEVERIDAD_POR_ESTADO[lectura.estado_lectura],
            valor_que_disparo=lectura.valor_medida,
            mensaje_alerta=construir_mensaje(lectura),
        ))
        abiertas.add(clave)

    if not nuevas:
        return []

    Alerta.objects.bulk_create(nuevas)
    # bulk_create en MySQL no siempre rellena los PK: se releen para poder
    # asociarles notificaciones.
    creadas = list(
        Alerta.objects
        .filter(estado='activa', lectura__in=[a.lectura_id for a in nuevas])
        .select_related('geomembrana', 'tipo_parametro')
    )

    notificar(creadas)

    for alerta in creadas:
        logger.warning(
            'Alerta %s generada: %s', alerta.severidad, alerta.mensaje_alerta
        )

    # El estado consolidado de cada piscina cambia con las alertas nuevas.
    for geomembrana in {alerta.geomembrana for alerta in creadas}:
        evaluar_estado_piscina(geomembrana)

    return creadas


def construir_mensaje(lectura):
    """
    Redacta el mensaje que lee el operario, con el valor y el rango esperado.

    :param lectura: monitoreo.Lectura fuera de rango
    :return: str con el mensaje
    """
    tipo = lectura.tipo_parametro
    etiqueta = 'crítico' if lectura.estado_lectura == 'critico' else 'en riesgo'
    return (
        f'{tipo.nombre_parametro} {etiqueta} en {lectura.geomembrana.nombre_piscina}: '
        f'{lectura.valor_medida} {tipo.unidad_medida} '
        f'(rango normal: {tipo.rango_normal_min} – {tipo.rango_normal_max})'
    )


def notificar(alertas):
    """
    Crea las notificaciones de un conjunto de alertas en una sola escritura.

    :param alertas: iterable de Alerta recien creadas
    :return: list de Notificacion creadas
    """
    from apps.usuarios.models import Usuario

    roles_necesarios = set()
    for alerta in alertas:
        roles_necesarios.update(DESTINATARIOS_POR_SEVERIDAD.get(alerta.severidad, []))

    if not roles_necesarios:
        return []

    usuarios_por_rol = {}
    for usuario in Usuario.objects.filter(
        rol__nombre_rol__in=roles_necesarios, estado='activo'
    ).select_related('rol'):
        usuarios_por_rol.setdefault(usuario.rol.nombre_rol, []).append(usuario)

    pendientes = []
    for alerta in alertas:
        for rol in DESTINATARIOS_POR_SEVERIDAD.get(alerta.severidad, []):
            for usuario in usuarios_por_rol.get(rol, []):
                pendientes.append(Notificacion(
                    usuario=usuario,
                    alerta=alerta,
                    titulo=f'Alerta {alerta.get_severidad_display()}',
                    mensaje=alerta.mensaje_alerta,
                ))

    if not pendientes:
        logger.warning(
            'No hay usuarios activos para notificar los roles %s', roles_necesarios
        )
        return []

    return Notificacion.objects.bulk_create(pendientes)


@transaction.atomic
def evaluar_estado_piscina(geomembrana):
    """
    Registra el estado consolidado del agua de una piscina.

    Alimenta la tabla `historial_estado_agua`, que es la fuente de las
    graficas de evolucion y de la comparacion entre periodos.

    :param geomembrana: piscinas.Geomembrana a evaluar
    :return: HistorialEstadoAgua creado
    """
    activas = Alerta.objects.filter(geomembrana=geomembrana, estado='activa')

    if activas.filter(severidad='critica').exists():
        estado, apta = 'critico', False
    elif activas.exists():
        estado, apta = 'riesgo', True
    else:
        estado, apta = 'optimo', True

    return HistorialEstadoAgua.objects.create(
        geomembrana=geomembrana,
        estado_general=estado,
        apta_produccion=apta,
    )


def resolver_alertas_normalizadas(lecturas):
    """
    Cierra automaticamente las alertas cuyo parametro volvio a rango normal.

    Sin esto, una alerta abierta bloquea para siempre la generacion de nuevas
    alertas de ese parametro (por la regla anti-duplicados de evaluar_lote) y
    el semaforo de la piscina nunca vuelve a verde.

    :param lecturas: iterable de Lectura del lote recien ingresado
    :return: int con la cantidad de alertas cerradas
    """
    normales = [lec for lec in lecturas if lec.estado_lectura == 'normal']
    if not normales:
        return 0

    from django.utils import timezone

    cerradas = 0
    for lectura in normales:
        afectadas = Alerta.objects.filter(
            geomembrana_id=lectura.geomembrana_id,
            tipo_parametro_id=lectura.tipo_parametro_id,
            estado='activa',
        )
        actualizadas = afectadas.update(
            estado='resuelta',
            fecha_resolucion=timezone.now(),
            accion_tomada='Cerrada automáticamente: el parámetro volvió a rango normal.',
        )
        if actualizadas:
            cerradas += actualizadas
            logger.info(
                'Cerradas %s alerta(s) de %s en %s por normalización',
                actualizadas, lectura.tipo_parametro_id, lectura.geomembrana_id,
            )

    return cerradas


# ======================================================================
# Acciones sobre alertas, compartidas por la web y la API movil
# ======================================================================
class AccionInvalida(Exception):
    """La alerta no esta en un estado que admita esta accion."""


def reconocer_alerta(alerta, usuario):
    """
    Marca la alerta como vista por alguien.

    Reconocer no es resolver: deja constancia de quien se hizo cargo mientras
    el problema sigue abierto.

    :param alerta: alertas.Alerta
    :param usuario: usuarios.Usuario que la atiende
    :return: la Alerta actualizada
    :raises AccionInvalida: si la alerta ya no esta activa
    """
    if alerta.estado != 'activa':
        raise AccionInvalida('Esa alerta ya no está activa.')

    alerta.reconocer(usuario)
    logger.info('Alerta %s reconocida por %s', alerta.pk, usuario.email)
    from apps.auditoria.services import registrar_evento
    registrar_evento(
        'alerta_reconocida',
        f'Alerta #{alerta.pk} reconocida en {alerta.geomembrana.nombre_piscina}',
        usuario=usuario, geomembrana=alerta.geomembrana,
    )
    return alerta


def resolver_alerta(alerta, usuario, accion):
    """
    Cierra la alerta registrando la accion correctiva aplicada.

    La accion es obligatoria: una alerta critica cerrada sin explicacion no
    sirve para la trazabilidad del cultivo.

    Al cerrarla se reevalua el estado consolidado de la piscina, porque su
    semaforo depende de las alertas abiertas.

    :param alerta: alertas.Alerta
    :param usuario: usuarios.Usuario que la resuelve
    :param accion: texto con lo que se hizo en campo
    :return: la Alerta actualizada
    :raises AccionInvalida: si falta la accion o la alerta ya estaba cerrada
    """
    accion = (accion or '').strip()
    if not accion:
        raise AccionInvalida('Describe la acción tomada antes de cerrar la alerta.')
    if alerta.estado in ('resuelta', 'descartada'):
        raise AccionInvalida('Esa alerta ya estaba cerrada.')

    alerta.resolver(usuario, accion)
    logger.info('Alerta %s resuelta por %s', alerta.pk, usuario.email)

    evaluar_estado_piscina(alerta.geomembrana)
    from apps.auditoria.services import registrar_evento
    registrar_evento(
        'alerta_resuelta',
        f'Alerta #{alerta.pk} resuelta en {alerta.geomembrana.nombre_piscina}',
        usuario=usuario, geomembrana=alerta.geomembrana,
        nivel='advertencia', datos={'accion': accion},
    )
    return alerta


# ======================================================================
# RF001: deteccion de sensores caidos (dejan de transmitir)
# ======================================================================
SEVERIDAD_SENSOR_CAIDO = 'critica'


def _mensaje_sensor_caido(sensor, ultima):
    """Redacta el mensaje de un sensor que dejo de transmitir."""
    from django.utils import timezone

    if ultima is None:
        detalle = 'nunca ha transmitido'
    else:
        detalle = f'sin transmitir desde {timezone.localtime(ultima).strftime("%d/%m/%Y %H:%M")}'
    return (
        f'Sensor {sensor.nombre_sensor} ({sensor.codigo_hardware}) en '
        f'{sensor.geomembrana.nombre_piscina}: {detalle}. '
        f'La medicion de {sensor.tipo_parametro.nombre_parametro} esta sin datos.'
    )


def _auditar_sensor(sensor, *, abierto):
    """Deja rastro en auditoria de la apertura/cierre de una alerta de sensor."""
    from apps.auditoria.services import registrar_evento

    if abierto:
        registrar_evento(
            'sistema',
            f'Sensor caido: {sensor.codigo_hardware} en {sensor.geomembrana.nombre_piscina}',
            geomembrana=sensor.geomembrana, nivel='critico',
        )
    else:
        registrar_evento(
            'sistema',
            f'Sensor {sensor.codigo_hardware} volvio a transmitir',
            geomembrana=sensor.geomembrana, nivel='info',
        )


def evaluar_sensores_caidos(margen_multiplos=3, gracia_segundos=120):
    """
    Abre una alerta por cada sensor activo que dejo de transmitir y cierra las
    de los que volvieron (RF001).

    Un sensor se considera caido si su ultima lectura es mas antigua que
    `intervalo_lectura_segundos * margen_multiplos + gracia_segundos`, o si
    nunca ha reportado. El margen evita falsas alarmas por un envio tardio.

    Idempotente: no duplica alertas ni cierra dos veces. Pensado para correr
    cada pocos minutos desde el Programador de tareas.

    :param margen_multiplos: cuantos intervalos de silencio se toleran
    :param gracia_segundos: colchon fijo adicional en segundos
    :return: dict {abiertas, cerradas, activos}
    """
    from django.db.models import Max
    from django.utils import timezone

    from apps.monitoreo.models import Lectura, Sensor

    ahora = timezone.now()
    sensores = list(
        Sensor.objects.filter(estado='activo')
        .select_related('geomembrana', 'tipo_parametro')
    )
    if not sensores:
        return {'abiertas': 0, 'cerradas': 0, 'activos': 0}

    # Ultima lectura por sensor en una sola consulta.
    ultimas = dict(
        Lectura.objects
        .filter(sensor__in=sensores)
        .values('sensor_id')
        .annotate(ultima=Max('timestamp_lectura'))
        .values_list('sensor_id', 'ultima')
    )

    # Alertas de sensor ya abiertas, indexadas por sensor.
    abiertas_por_sensor = {
        alerta.sensor_id: alerta
        for alerta in Alerta.objects.filter(
            tipo_alerta='sensor', estado__in=['activa', 'reconocida'],
            sensor__in=sensores,
        )
    }

    nuevas, cerradas = [], 0
    for sensor in sensores:
        umbral = sensor.intervalo_lectura_segundos * margen_multiplos + gracia_segundos
        limite = ahora - timezone.timedelta(seconds=umbral)
        ultima = ultimas.get(sensor.id)
        caido = ultima is None or ultima < limite
        abierta = abiertas_por_sensor.get(sensor.id)

        if caido and abierta is None:
            nuevas.append(Alerta(
                geomembrana=sensor.geomembrana,
                sensor=sensor,
                tipo_parametro=sensor.tipo_parametro,
                tipo_alerta='sensor',
                severidad=SEVERIDAD_SENSOR_CAIDO,
                mensaje_alerta=_mensaje_sensor_caido(sensor, ultima),
            ))
        elif not caido and abierta is not None:
            abierta.estado = 'resuelta'
            abierta.fecha_resolucion = ahora
            abierta.accion_tomada = 'Cerrada automaticamente: el sensor volvio a transmitir.'
            abierta.save(update_fields=['estado', 'fecha_resolucion', 'accion_tomada'])
            cerradas += 1
            logger.info('Alerta de sensor %s cerrada: volvio a transmitir', sensor.codigo_hardware)
            _auditar_sensor(sensor, abierto=False)

    if nuevas:
        Alerta.objects.bulk_create(nuevas)
        # bulk_create en MySQL no siempre rellena los PK: se releen para notificar.
        creadas = list(
            Alerta.objects.filter(
                tipo_alerta='sensor', estado='activa',
                sensor__in=[a.sensor_id for a in nuevas],
            ).select_related('geomembrana', 'sensor', 'tipo_parametro')
        )
        notificar(creadas)
        for alerta in creadas:
            logger.warning('Sensor caido: %s', alerta.mensaje_alerta)
            _auditar_sensor(alerta.sensor, abierto=True)

    return {'abiertas': len(nuevas), 'cerradas': cerradas, 'activos': len(sensores)}
