"""
Matriz de enrutamiento y permisos por rol (RBAC) de SIGMAP-AQUA.

Fuente de verdad: usuarios.Rol.nombre_rol (tabla `roles`).
Los Group de django.contrib.auth se mantienen solo como espejo.
"""
from django.urls import reverse

# Nombres canonicos de los roles (deben coincidir con la tabla `roles`)
ROL_INSTRUCTOR = 'Instructor Lider'
ROL_APRENDIZ = 'Aprendiz'
ROL_OPERARIO = 'Operario'
ROL_AGENTE_IA = 'Agente IA'

# rol -> url_name al que se redirige tras el login
DASHBOARD_POR_ROL = {
    ROL_INSTRUCTOR: 'core:instructor_lider',   # supervision general
    ROL_APRENDIZ:   'core:aprendiz',           # matriz de actividades + comparativas
    ROL_OPERARIO:   'core:operario',           # monitoreo en tiempo real
}

DASHBOARD_POR_DEFECTO = 'core:dashboard'

# rol -> conjunto de url_names de core a los que puede entrar.
# None = acceso a todo el modulo core (solo Instructor Lider).
MODULOS_POR_ROL = {
    ROL_INSTRUCTOR: None,
    ROL_OPERARIO: {
        'operario', 'monitoreo', 'sensores', 'alertas', 'historial',
        'geomembranas', 'configuraciones', 'dashboard',
    },
    ROL_APRENDIZ: {
        'aprendiz', 'graficas_reportes', 'comparacion_periodos', 'historial',
        'monitoreo', 'alertas', 'configuraciones', 'dashboard',
    },
}

# Roles que NUNCA deben ver el admin nativo de Django
ROLES_SIN_ADMIN = set(DASHBOARD_POR_ROL) | {ROL_AGENTE_IA}


def obtener_nombre_rol(usuario):
    """
    Devuelve el nombre del rol del usuario.

    :param usuario: instancia de usuarios.Usuario o AnonymousUser
    :return: str con el nombre del rol, o '' si no aplica
    """
    if not usuario.is_authenticated or not usuario.rol_id:
        return ''
    return usuario.rol.nombre_rol


def resolver_dashboard(usuario):
    """
    Resuelve la ruta del dashboard que corresponde al rol del usuario.

    :param usuario: instancia de usuarios.Usuario
    :return: str con la ruta destino (ej. '/operario/')
    """
    url_name = DASHBOARD_POR_ROL.get(obtener_nombre_rol(usuario), DASHBOARD_POR_DEFECTO)
    return reverse(url_name)


def puede_ver_modulo(usuario, url_name):
    """
    Indica si el usuario puede entrar a un modulo del app core.

    :param usuario: instancia de usuarios.Usuario
    :param url_name: nombre corto de la url (ej. 'monitoreo')
    :return: bool
    """
    rol = obtener_nombre_rol(usuario)
    if not rol:
        return False
    if rol not in MODULOS_POR_ROL:
        return False
    permitidos = MODULOS_POR_ROL[rol]
    return permitidos is None or url_name in permitidos


def puede_entrar_al_admin(usuario):
    """
    Solo superusuarios sin rol operativo acceden al admin nativo de Django.

    :param usuario: instancia de usuarios.Usuario
    :return: bool
    """
    if not usuario.is_authenticated:
        return False
    return usuario.is_superuser and obtener_nombre_rol(usuario) not in ROLES_SIN_ADMIN
