"""
Servicio de auditoría: único punto de entrada para dejar constancia de un evento.

Regla central: auditar es un efecto secundario. Si registrar el evento falla
(BD caída, dato inválido), se deja traza en el log y se devuelve None, pero la
excepción NUNCA se propaga a la vista o al servicio que lo llamó. Auditar un
cambio jamás debe revertir el cambio.
"""
import logging

logger = logging.getLogger('apps.auditoria')


def registrar_evento(tipo_evento, descripcion, *, usuario=None, geomembrana=None,
                     nivel='info', datos=None, ip=None):
    """
    Persiste un evento del sistema de forma segura.

    :param tipo_evento: valor de EventoSistema.Tipo (o su string)
    :param descripcion: texto corto legible por el Instructor Líder
    :param usuario: usuarios.Usuario responsable (None = acción del sistema)
    :param geomembrana: piscinas.Geomembrana asociada, si aplica
    :param nivel: 'info' | 'advertencia' | 'critico'
    :param datos: dict con la evidencia (valores antes/después, ids, etc.)
    :param ip: IP de origen, para eventos de sesión
    :return: EventoSistema creado, o None si no se pudo registrar
    """
    from .models import EventoSistema

    try:
        return EventoSistema.objects.create(
            tipo_evento=str(tipo_evento),
            descripcion=(descripcion or '')[:255],
            usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
            geomembrana=geomembrana,
            nivel=str(nivel),
            datos=datos or {},
            ip_origen=ip,
        )
    except Exception:
        logger.exception('No se pudo registrar el evento de auditoría: %s', descripcion)
        return None


def ip_de(request):
    """
    Extrae la IP de origen de una petición, respetando un posible proxy.

    :param request: HttpRequest
    :return: str con la IP, o None
    """
    adelante = request.META.get('HTTP_X_FORWARDED_FOR')
    if adelante:
        return adelante.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
