from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def index(request):
    """Página de bienvenida pública."""
    return render(request, 'core/index.html')


@login_required
def dashboard(request):
    """Dashboard principal — requiere autenticación."""
    return render(request, 'roles/InstructorLider.html')


# Alias para compatibilidad con URLs existentes
instructor_lider = dashboard


@login_required
def sensores(request):
    return render(request, 'funcionalidades/sensores.html')


@login_required
def monitoreo(request):
    return render(request, 'funcionalidades/monitoreo.html')


@login_required
def graficas_reportes(request):
    return render(request, 'funcionalidades/graficasyreportes.html')


@login_required
def comparacion_periodos(request):
    return render(request, 'funcionalidades/ComoaracionesdePreiodos.html')


@login_required
def alertas(request):
    return render(request, 'funcionalidades/Alertas.html')


@login_required
def ai(request):
    return render(request, 'funcionalidades/AI.html')


@login_required
def usuarios(request):
    return render(request, 'funcionalidades/usuarios.html')


@login_required
def geomembranas(request):
    return render(request, 'funcionalidades/geomenbranas.html')


@login_required
def configuraciones(request):
    return render(request, 'funcionalidades/configuraciones.html')


