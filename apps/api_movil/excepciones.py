"""
Manejador global de errores de DRF.

Sin esto, un 401 responde {"detail": "..."} y un error de validación responde
{"email": ["..."]}: dos formas distintas que el cliente tendría que distinguir.
Aquí todo sale como {success, data, message}.
"""
from rest_framework.views import exception_handler


def manejador_errores(exc, context):
    """
    Traduce la respuesta de error de DRF al contrato de la API.

    :param exc: excepción lanzada
    :param context: contexto de la vista
    :return: Response con formato estándar, o None si DRF no la manejó (500)
    """
    respuesta_drf = exception_handler(exc, context)
    if respuesta_drf is None:
        # Error no controlado: se deja pasar para que Django lo registre
        # como 500 en vez de disfrazarlo de respuesta válida.
        return None

    detalle = respuesta_drf.data

    if isinstance(detalle, dict) and 'detail' in detalle:
        # 401, 403, 404, 405, 429: un solo mensaje.
        datos, mensaje = None, str(detalle['detail'])
    elif isinstance(detalle, list):
        datos, mensaje = None, ' '.join(str(item) for item in detalle)
    else:
        # Errores de validación campo por campo: la app los pinta bajo su input.
        datos, mensaje = detalle, 'Revisa los datos enviados.'

    respuesta_drf.data = {'success': False, 'data': datos, 'message': mensaje}
    return respuesta_drf
