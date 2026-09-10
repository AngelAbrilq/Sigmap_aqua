from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.usuarios.permissions import (
    ROL_APRENDIZ,
    ROL_INSTRUCTOR,
    ROL_OPERARIO,
    obtener_nombre_rol,
    puede_ver_modulo,
    resolver_dashboard,
)

# rol -> template de su dashboard principal
TEMPLATE_POR_ROL = {
    ROL_INSTRUCTOR: 'roles/InstructorLider.html',
    ROL_APRENDIZ:   'roles/Aprendiz.html',
    ROL_OPERARIO:   'roles/Operario.html',
}


def rol_requerido(url_name, roles=None):
    """
    Decorador que valida el rol antes de renderizar un modulo de core.

    :param url_name: nombre corto de la url, usado contra MODULOS_POR_ROL
    :param roles: iterable opcional de roles permitidos de forma explicita
    :return: decorador de vista
    """
    def decorador(vista):
        @login_required
        def envoltura(request, *args, **kwargs):
            rol = obtener_nombre_rol(request.user)
            permitido = rol in roles if roles else puede_ver_modulo(request.user, url_name)
            if not permitido:
                messages.warning(request, 'No tienes permisos para acceder a ese modulo.')
                return redirect(resolver_dashboard(request.user))
            return vista(request, *args, **kwargs)
        envoltura.__name__ = vista.__name__
        envoltura.__doc__ = vista.__doc__
        return envoltura
    return decorador


def index(request):
    """Pagina de bienvenida publica. Si ya hay sesion, va al dashboard del rol."""
    if request.user.is_authenticated:
        return redirect(resolver_dashboard(request.user))
    return render(request, 'core/index.html')


@login_required
def dashboard(request):
    """Router de dashboards: renderiza el template que corresponde al rol."""
    template = TEMPLATE_POR_ROL.get(obtener_nombre_rol(request.user))
    if template is None:
        messages.error(request, 'Tu rol no tiene un panel asignado.')
        return redirect('usuarios:logout')
    return render(request, template)


@rol_requerido('instructor_lider', roles={ROL_INSTRUCTOR})
def instructor_lider(request):
    """Panel de supervision general. Exclusivo del Instructor Lider."""
    return render(request, 'roles/InstructorLider.html')


@rol_requerido('aprendiz', roles={ROL_APRENDIZ})
def aprendiz(request):
    """Panel del Aprendiz: matriz de actividades y graficas comparativas."""
    return render(request, 'roles/Aprendiz.html')


@rol_requerido('operario', roles={ROL_OPERARIO})
def operario(request):
    """Panel del Operario: monitoreo en tiempo real y operaciones."""
    return render(request, 'roles/Operario.html')


@rol_requerido('sensores')
def sensores(request):
    return render(request, 'funcionalidades/sensores.html')


@rol_requerido('monitoreo')
def monitoreo(request):
    return render(request, 'funcionalidades/monitoreo.html')


@rol_requerido('historial')
def historial(request):
    return render(request, 'funcionalidades/Historial.html')


@rol_requerido('graficas_reportes')
def graficas_reportes(request):
    return render(request, 'funcionalidades/graficasyreportes.html')


@rol_requerido('comparacion_periodos')
def comparacion_periodos(request):
    return render(request, 'funcionalidades/ComoaracionesdePreiodos.html')


@rol_requerido('alertas')
def alertas(request):
    return render(request, 'funcionalidades/Alertas.html')


@rol_requerido('ai')
def ai(request):
    return render(request, 'funcionalidades/AI.html')


@rol_requerido('usuarios')
def usuarios(request):
    return render(request, 'funcionalidades/usuarios.html')


@rol_requerido('geomembranas')
def geomembranas(request):
    return render(request, 'funcionalidades/geomenbranas.html')


@rol_requerido('configuraciones')
def configuraciones(request):
    return render(request, 'funcionalidades/configuraciones.html')
