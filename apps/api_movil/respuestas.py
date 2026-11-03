"""
Formato único de respuesta de la API.

El mismo contrato {success, data, message} que ya usa la API de los ESP32.
Un cliente Flutter que aprende a leer una respuesta las lee todas.
"""
from rest_framework import status
from rest_framework.response import Response


def respuesta(success, data=None, message='', codigo=status.HTTP_200_OK):
    """
    Envuelve cualquier payload en el contrato estándar.

    :param success: True si la operación se completó
    :param data: payload (dict, list o None)
    :param message: texto legible para mostrar en la app
    :param codigo: código HTTP
    :return: rest_framework.response.Response
    """
    return Response(
        {'success': success, 'data': data, 'message': message},
        status=codigo,
    )
