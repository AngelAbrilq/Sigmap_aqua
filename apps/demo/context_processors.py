"""Expone a los templates si la demostración por QR está activa."""
from django.conf import settings


def demo_qr(request):
    """
    :param request: HttpRequest
    :return: dict con `demo_qr_activo` (bool) y `acceso_demo` (slug del rol
             si la sesión actual entró por QR, para el tour del asistente)
    """
    sesion = getattr(request, 'session', None)
    return {
        'demo_qr_activo': getattr(settings, 'DEMO_QR_ACTIVO', False),
        'acceso_demo': sesion.get('acceso_demo', '') if sesion is not None else '',
    }
