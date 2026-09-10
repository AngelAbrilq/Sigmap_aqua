from django.shortcuts import render


def index(request):
    return render(request, 'roles/InstructorLider.html')


def instructor_lider(request):
    return render(request, 'roles/InstructorLider.html')


def sensores(request):
    return render(request, 'funcionalidades/sensores.html')


def monitoreo(request):
    return render(request, 'funcionalidades/monitoreo.html')


def graficas_reportes(request):
    return render(request, 'funcionalidades/graficasyreportes.html')


def comparacion_periodos(request):
    return render(request, 'funcionalidades/ComoaracionesdePreiodos.html')


def alertas(request):
    return render(request, 'funcionalidades/Alertas.html')


def ai(request):
    return render(request, 'funcionalidades/AI.html')


def usuarios(request):
    return render(request, 'funcionalidades/usuarios.html')


def geomembranas(request):
    return render(request, 'funcionalidades/geomenbranas.html')


def configuraciones(request):
    return render(request, 'funcionalidades/configuraciones.html')

