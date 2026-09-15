"""
Vistas del app core: bienvenida y paneles por rol.

Cada modulo funcional (geomembranas, sensores, monitoreo, alertas, reportes,
usuarios, configuraciones) vive en su propio app con su propia logica de
negocio. Core solo enruta al panel que corresponde al rol autenticado.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.alertas.models import Alerta
from apps.monitoreo.models import Lectura, Sensor
from apps.piscinas.models import Geomembrana
from apps.usuarios.permissions import (
    ROL_APRENDIZ,
    ROL_INSTRUCTOR,
    ROL_OPERARIO,
    obtener_nombre_rol,
    resolver_dashboard,
)

TEMPLATE_POR_ROL = {
    ROL_INSTRUCTOR: 'roles/InstructorLider.html',
    ROL_APRENDIZ:   'roles/Aprendiz.html',
    ROL_OPERARIO:   'roles/Operario.html',
}


def rol_requerido(roles):
    """
    Restringe una vista a un conjunto explicito de roles.

    :param roles: iterable con los nombres de rol permitidos
    :return: decorador de vista
    """
    def decorador(vista):
        @login_required
        def envoltura(request, *args, **kwargs):
            if obtener_nombre_rol(request.user) not in roles:
                messages.warning(request, 'No tienes permisos para acceder a ese panel.')
                return redirect(resolver_dashboard(request.user))
            return vista(request, *args, **kwargs)
        envoltura.__name__ = vista.__name__
        envoltura.__doc__ = vista.__doc__
        return envoltura
    return decorador


def _resumen_operativo():
    """
    Indicadores transversales que comparten los tres paneles.

    Una sola consulta agregada por bloque en vez de contar en Python: los
    paneles se abren en cada login y no deben recorrer todas las lecturas.

    :return: dict con los contadores del sistema
    """
    ahora = timezone.now()
    hace_24h = ahora - timezone.timedelta(hours=24)

    piscinas = Geomembrana.objects.aggregate(
        total=Count('id'),
        operativas=Count('id', filter=Q(estado='activo', apta_para_produccion=True)),
    )
    sensores = Sensor.objects.aggregate(
        total=Count('id'),
        activos=Count('id', filter=Q(estado='activo')),
        averiados=Count('id', filter=Q(estado='averiado')),
    )
    alertas = Alerta.objects.aggregate(
        activas=Count('id', filter=Q(estado='activa')),
        criticas=Count('id', filter=Q(estado='activa', severidad='critica')),
    )
    lecturas_24h = Lectura.objects.filter(timestamp_lectura__gte=hace_24h).aggregate(
        total=Count('id'),
        fuera_rango=Count('id', filter=Q(dentro_rango=False)),
    )

    return {
        'piscinas': piscinas,
        'sensores': sensores,
        'alertas': alertas,
        'lecturas_24h': lecturas_24h,
        'ultimas_alertas': (
            Alerta.objects
            .filter(estado='activa')
            .select_related('geomembrana', 'tipo_parametro')[:5]
        ),
        'ultimas_lecturas': (
            Lectura.objects
            .select_related('sensor', 'tipo_parametro', 'geomembrana')[:8]
        ),
    }


def index(request):
    """Pagina de bienvenida publica. Con sesion abierta, va al panel del rol."""
    if request.user.is_authenticated:
        return redirect(resolver_dashboard(request.user))
    return render(request, 'core/index.html')


@login_required
def dashboard(request):
    """Router de paneles: renderiza el template que corresponde al rol."""
    template = TEMPLATE_POR_ROL.get(obtener_nombre_rol(request.user))
    if template is None:
        messages.error(request, 'Tu rol no tiene un panel asignado.')
        return redirect('usuarios:logout')
    return render(request, template, {'actual': 'dashboard', **_resumen_operativo()})


@rol_requerido({ROL_INSTRUCTOR})
def instructor_lider(request):
    """Panel de supervision general. Exclusivo del Instructor Lider."""
    return render(request, 'roles/InstructorLider.html',
                  {'actual': 'dashboard', **_resumen_operativo()})


@rol_requerido({ROL_APRENDIZ})
def aprendiz(request):
    """Panel del Aprendiz: consulta y analisis, sin operaciones de escritura."""
    return render(request, 'roles/Aprendiz.html',
                  {'actual': 'dashboard', **_resumen_operativo()})


@rol_requerido({ROL_OPERARIO})
def operario(request):
    """Panel del Operario: estado en tiempo real y atencion de alertas."""
    return render(request, 'roles/Operario.html',
                  {'actual': 'dashboard', **_resumen_operativo()})
