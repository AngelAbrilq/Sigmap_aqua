"""
Context processors globales.

Inyectan en TODOS los templates los datos del encabezado, para no repetir la
misma consulta en cada vista.
"""


def usuario_context(request):
    """
    Datos del usuario autenticado y sus notificaciones sin leer.

    La campanita del header aparece en cada pagina: la consulta se hace aqui
    una sola vez, acotada con [:6] y contando solo lo no leido, apoyada en el
    indice idx_notif_usuario_leida.

    :param request: HttpRequest
    :return: dict con el contexto del encabezado
    """
    if not request.user.is_authenticated:
        return {
            'nombre_usuario': '',
            'rol_usuario': '',
            'notificaciones_no_leidas': 0,
            'notificaciones_recientes': [],
        }

    from apps.alertas.models import Notificacion

    no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False)

    return {
        'nombre_usuario': request.user.nombre_completo or request.user.email,
        'rol_usuario': request.user.rol.nombre_rol if request.user.rol_id else 'Sin rol',
        'notificaciones_no_leidas': no_leidas.count(),
        'notificaciones_recientes': list(
            no_leidas.select_related('alerta')[:6]
        ),
    }
