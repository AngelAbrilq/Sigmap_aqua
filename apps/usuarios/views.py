from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .permissions import resolver_dashboard


def _destino_post_login(request, usuario):
    """
    Calcula a donde enviar al usuario recien autenticado.
    Prioriza ?next= (validado contra el host) y cae en la matriz de roles.

    :param request: HttpRequest
    :param usuario: instancia de usuarios.Usuario ya autenticada
    :return: str con la ruta destino
    """
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_secure=request.is_secure(),
    ):
        return next_url
    return resolver_dashboard(usuario)


def login_view(request):
    """
    Vista de login por email. Redirige al dashboard segun el rol.
    Nunca envia al admin nativo de Django.
    """
    if request.user.is_authenticated:
        return redirect(resolver_dashboard(request.user))

    if request.method == 'POST':
        email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not email or not password:
            messages.error(request, 'Por favor completa todos los campos.')
            return render(request, 'usuarios/login.html')

        usuario = authenticate(request, username=email, password=password)

        if usuario is None:
            messages.error(request, 'Correo o contrasena incorrectos.')
        elif usuario.estado != 'activo':
            messages.error(request, 'Tu cuenta esta inactiva. Contacta al administrador.')
        elif not usuario.rol_id:
            messages.error(request, 'Tu cuenta no tiene un rol asignado. Contacta al administrador.')
        else:
            login(request, usuario)
            return redirect(_destino_post_login(request, usuario))

    return render(request, 'usuarios/login.html')


def logout_view(request):
    """Cierra sesion y vuelve al login."""
    logout(request)
    return redirect('usuarios:login')


# ======================================================================
# GESTION DE USUARIOS
# ======================================================================
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import UsuarioForm
from .models import Rol, Usuario
from .permissions import puede_editar_modulo, puede_ver_modulo

logger = logging.getLogger(__name__)

MODULO = 'usuarios'
POR_PAGINA = 12


def _requiere_lectura(vista):
    """Restringe la vista a los roles con acceso al modulo de usuarios."""
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_ver_modulo(request.user, MODULO):
            messages.warning(request, 'No tienes permisos para ver los usuarios.')
            return redirect(resolver_dashboard(request.user))
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


def _requiere_escritura(vista):
    """Solo el Instructor Lider administra cuentas."""
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_editar_modulo(request.user, MODULO):
            messages.error(request, 'Tu rol no permite administrar usuarios.')
            return redirect('usuarios:listar')
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


@_requiere_lectura
def listar(request):
    """Listado de usuarios con busqueda y filtros por rol y estado."""
    termino = request.GET.get('q', '').strip()
    filtro_rol = request.GET.get('rol', '').strip()
    filtro_estado = request.GET.get('estado', '').strip()

    queryset = Usuario.objects.select_related('rol')

    if termino:
        queryset = queryset.filter(
            Q(nombre_completo__icontains=termino)
            | Q(email__icontains=termino)
            | Q(documento_identidad__icontains=termino)
        )
    if filtro_rol.isdigit():
        queryset = queryset.filter(rol_id=filtro_rol)
    if filtro_estado in dict(Usuario.ESTADOS):
        queryset = queryset.filter(estado=filtro_estado)

    resumen = Usuario.objects.aggregate(
        total=Count('id'),
        activos=Count('id', filter=Q(estado='activo')),
        inactivos=Count('id', filter=Q(estado='inactivo')),
    )

    paginador = Paginator(queryset, POR_PAGINA)
    pagina = paginador.get_page(request.GET.get('page'))

    seleccion = request.GET.get('seleccion')
    seleccionado = queryset.filter(pk=seleccion).first() if seleccion else None
    if seleccionado is None and pagina.object_list:
        seleccionado = pagina.object_list[0]

    return render(request, 'funcionalidades/usuarios.html', {
        'actual': MODULO,
        'pagina': pagina,
        'usuarios': pagina.object_list,
        'seleccionado': seleccionado,
        'resumen': resumen,
        'roles': Rol.objects.filter(estado='activo').annotate(cuantos=Count('usuarios')),
        'estados_disponibles': Usuario.ESTADOS,
        'termino': termino,
        'filtro_rol': filtro_rol,
        'filtro_estado': filtro_estado,
        'puede_editar': puede_editar_modulo(request.user, MODULO),
        'form': UsuarioForm(),
        'form_editar': UsuarioForm(instance=seleccionado) if seleccionado else None,
    })


@_requiere_escritura
@require_http_methods(['POST'])
def crear(request):
    """Alta de usuario. request.FILES viaja por la foto de perfil."""
    form = UsuarioForm(request.POST, request.FILES)
    if form.is_valid():
        usuario = form.save()
        logger.info('Usuario creado %s por %s', usuario.email, request.user.email)
        messages.success(request, f'Usuario {usuario.nombre_completo} creado.')
        return redirect(f"{reverse('usuarios:listar')}?seleccion={usuario.pk}")

    messages.error(request, 'Revisa los campos marcados: el usuario no se creó.')
    return _usuarios_con_errores(request, form, 'crear')


@_requiere_escritura
@require_http_methods(['POST'])
def editar(request, pk):
    """Actualiza un usuario existente."""
    usuario = get_object_or_404(Usuario, pk=pk)
    form = UsuarioForm(request.POST, request.FILES, instance=usuario)
    if form.is_valid():
        form.save()
        logger.info('Usuario editado %s por %s', usuario.email, request.user.email)
        messages.success(request, f'{usuario.nombre_completo} actualizado.')
        return redirect(f"{reverse('usuarios:listar')}?seleccion={usuario.pk}")

    messages.error(request, 'Revisa los campos marcados: los cambios no se guardaron.')
    return _usuarios_con_errores(request, form, 'editar', usuario)


@_requiere_escritura
@require_http_methods(['POST'])
def desactivar(request, pk):
    """
    Desactiva una cuenta en lugar de borrarla.

    Los usuarios quedan referenciados en alertas reconocidas, lecturas
    validadas y reportes generados: borrarlos destruiria la trazabilidad de
    quien hizo que. Ademas nadie puede desactivarse a si mismo, para no
    dejar el sistema sin administrador por accidente.
    """
    usuario = get_object_or_404(Usuario, pk=pk)

    if usuario.pk == request.user.pk:
        messages.error(request, 'No puedes desactivar tu propia cuenta.')
        return redirect('usuarios:listar')

    nuevo_estado = 'inactivo' if usuario.estado == 'activo' else 'activo'

    if nuevo_estado == 'inactivo':
        activos_del_rol = Usuario.objects.filter(
            rol=usuario.rol, estado='activo'
        ).exclude(pk=usuario.pk).count()
        if activos_del_rol == 0:
            messages.error(
                request,
                f'{usuario.nombre_completo} es el único usuario activo con rol '
                f'"{usuario.rol.nombre_rol}". Asigna otro antes de desactivarlo.'
            )
            return redirect('usuarios:listar')

    usuario.estado = nuevo_estado
    usuario.save(update_fields=['estado', 'fecha_edicion'])

    logger.info('Usuario %s -> %s por %s', usuario.email, nuevo_estado, request.user.email)
    messages.success(
        request,
        f'{usuario.nombre_completo} quedó {"activo" if nuevo_estado == "activo" else "inactivo"}.'
    )
    return redirect('usuarios:listar')


def _usuarios_con_errores(request, form, modal, seleccionado=None):
    """Re-renderiza el listado conservando el formulario con sus errores."""
    queryset = Usuario.objects.select_related('rol')
    pagina = Paginator(queryset, POR_PAGINA).get_page(1)
    if seleccionado is None and pagina.object_list:
        seleccionado = pagina.object_list[0]

    return render(request, 'funcionalidades/usuarios.html', {
        'actual': MODULO,
        'pagina': pagina,
        'usuarios': pagina.object_list,
        'seleccionado': seleccionado,
        'resumen': queryset.aggregate(
            total=Count('id'),
            activos=Count('id', filter=Q(estado='activo')),
            inactivos=Count('id', filter=Q(estado='inactivo')),
        ),
        'roles': Rol.objects.filter(estado='activo').annotate(cuantos=Count('usuarios')),
        'estados_disponibles': Usuario.ESTADOS,
        'termino': '', 'filtro_rol': '', 'filtro_estado': '',
        'puede_editar': True,
        'form': form if modal == 'crear' else UsuarioForm(),
        'form_editar': form if modal == 'editar' else (
            UsuarioForm(instance=seleccionado) if seleccionado else None
        ),
        'abrir_modal': modal,
    })
