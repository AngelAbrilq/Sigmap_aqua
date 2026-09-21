"""
CRUD de Geomembranas.

Geomembrana es la entidad raiz: sensores, dispositivos, lecturas y alertas la
referencian con on_delete=PROTECT. Por eso el borrado fisico solo se permite
cuando no hay historico; en cualquier otro caso se desactiva, que es lo que
pide la trazabilidad del cultivo.

Lectura: Instructor Lider, Operario y Aprendiz.
Escritura: Instructor Lider y Operario.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from apps.monitoreo.aptitud import evaluar_aptitud
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.usuarios.permissions import puede_editar_modulo, puede_ver_modulo, resolver_dashboard

from .forms import GeomembranaForm
from .models import Geomembrana

logger = logging.getLogger(__name__)

MODULO = 'geomembranas'
POR_PAGINA = 8


# ----------------------------------------------------------------------
# Decoradores de acceso
# ----------------------------------------------------------------------
def _requiere_lectura(vista):
    """Permite el paso solo a los roles que tienen el modulo en su matriz."""
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_ver_modulo(request.user, MODULO):
            messages.warning(request, 'No tienes permisos para ver las geomembranas.')
            return redirect(resolver_dashboard(request.user))
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


def _requiere_escritura(vista):
    """
    Permite el paso solo a los roles que pueden modificar el modulo.

    El Aprendiz ve el modulo pero no lo altera: su rol es de consulta.
    """
    @login_required
    def envoltura(request, *args, **kwargs):
        if not puede_editar_modulo(request.user, MODULO):
            messages.error(request, 'Tu rol no permite modificar geomembranas.')
            return redirect('piscinas:listar')
        return vista(request, *args, **kwargs)
    envoltura.__name__ = vista.__name__
    envoltura.__doc__ = vista.__doc__
    return envoltura


# ----------------------------------------------------------------------
# Contexto compartido
# ----------------------------------------------------------------------
def _resumen_kpis(queryset_completo):
    """
    Calcula las 5 tarjetas superiores del modulo.

    Recibe el queryset SIN paginar para que los totales reflejen el universo
    completo y no solo la pagina visible.

    :param queryset_completo: QuerySet de Geomembrana ya filtrado
    :return: dict con los valores de los KPI
    """
    geomembranas = list(queryset_completo)
    total = len(geomembranas)

    vidas = [g.vida_util_restante_pct for g in geomembranas]
    vidas = [v for v in vidas if v is not None]
    vida_promedio = round(sum(vidas) / len(vidas)) if vidas else None

    criticas = sum(1 for g in geomembranas if g.estado_operativo == 'crit')
    atencion = sum(1 for g in geomembranas if g.estado_operativo == 'warn')

    if criticas:
        estado_general, estado_clase = 'Crítico', 'crit'
        estado_sub = f'{criticas} requiere(n) intervención'
    elif atencion:
        estado_general, estado_clase = 'Atención', 'warn'
        estado_sub = f'{atencion} en observación'
    else:
        estado_general, estado_clase = 'Óptimo', 'ok'
        estado_sub = 'Sin riesgos detectados'

    mantenimientos = [g.fecha_ultimo_mantenimiento for g in geomembranas
                      if g.fecha_ultimo_mantenimiento]
    proximas = [(g.proxima_inspeccion, g) for g in geomembranas if g.proxima_inspeccion]
    proxima_fecha, proxima_geo = min(proximas, key=lambda par: par[0]) if proximas else (None, None)

    return {
        'total': total,
        'operativas': sum(1 for g in geomembranas if g.esta_operativa),
        'estado_general': estado_general,
        'estado_clase': estado_clase,
        'estado_sub': estado_sub,
        'vida_promedio': vida_promedio,
        'ultimo_mantenimiento': max(mantenimientos) if mantenimientos else None,
        'proxima_inspeccion': proxima_fecha,
        'proxima_geomembrana': proxima_geo,
        'dias_proxima': proxima_geo.dias_para_inspeccion if proxima_geo else None,
    }


# ----------------------------------------------------------------------
# READ
# ----------------------------------------------------------------------
@_requiere_lectura
def listar(request):
    """
    Listado con busqueda, filtro por estado, paginacion y panel de detalle.

    La geomembrana seleccionada se resuelve en el servidor (?seleccion=<pk>),
    no en JavaScript: asi el detalle sobrevive a recargas y es enlazable.
    """
    termino = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', '').strip()

    queryset = Geomembrana.objects.con_relaciones().buscar(termino)
    if filtro_estado in dict(Geomembrana.ESTADOS):
        queryset = queryset.filter(estado=filtro_estado)

    kpis = _resumen_kpis(queryset)

    paginador = Paginator(queryset, POR_PAGINA)
    pagina = paginador.get_page(request.GET.get('page'))

    # Seleccion explicita, o la primera de la pagina actual.
    seleccion_id = request.GET.get('seleccion')
    seleccionada = None
    if seleccion_id:
        seleccionada = queryset.filter(pk=seleccion_id).first()
    if seleccionada is None and pagina.object_list:
        seleccionada = pagina.object_list[0]

    contexto = {
        'actual': MODULO,
        'pagina': pagina,
        'geomembranas': pagina.object_list,
        'seleccionada': seleccionada,
        'aptitud': evaluar_aptitud(seleccionada) if seleccionada else None,
        'kpis': kpis,
        'termino': termino,
        'filtro_estado': filtro_estado,
        'estados_disponibles': Geomembrana.ESTADOS,
        'puede_editar': puede_editar_modulo(request.user, MODULO),
        'form': GeomembranaForm(),
        'form_editar': GeomembranaForm(instance=seleccionada) if seleccionada else None,
    }
    return render(request, 'funcionalidades/geomenbranas.html', contexto)


# ----------------------------------------------------------------------
# CREATE
# ----------------------------------------------------------------------
@_requiere_escritura
@require_http_methods(['POST'])
def crear(request):
    """
    Alta de geomembrana. Solo acepta POST con CSRF valido.

    Si el formulario falla, se re-renderiza el listado con los errores y el
    modal abierto, para no perder lo que el usuario ya escribio.
    """
    form = GeomembranaForm(request.POST)

    if form.is_valid():
        geomembrana = form.save()
        logger.info(
            'Geomembrana creada id=%s codigo=%s por usuario=%s',
            geomembrana.pk, geomembrana.codigo_identificacion, request.user.email,
        )
        messages.success(
            request,
            f'Geomembrana {geomembrana.codigo_identificacion} registrada correctamente.',
        )
        return redirect(f"{reverse('piscinas:listar')}?seleccion={geomembrana.pk}")

    messages.error(request, 'Revisa los campos marcados: la geomembrana no se registró.')
    return _re_render_con_errores(request, form, modal='crear')


# ----------------------------------------------------------------------
# UPDATE
# ----------------------------------------------------------------------
@_requiere_escritura
@require_http_methods(['POST'])
def editar(request, pk):
    """
    Actualiza una geomembrana existente.

    :param pk: identificador de la geomembrana
    """
    geomembrana = get_object_or_404(Geomembrana, pk=pk)
    form = GeomembranaForm(request.POST, instance=geomembrana)

    if form.is_valid():
        form.save()
        logger.info(
            'Geomembrana editada id=%s codigo=%s por usuario=%s',
            geomembrana.pk, geomembrana.codigo_identificacion, request.user.email,
        )
        messages.success(request, f'{geomembrana.codigo_identificacion} actualizada.')
        return redirect(f"{reverse('piscinas:listar')}?seleccion={geomembrana.pk}")

    messages.error(request, 'Revisa los campos marcados: los cambios no se guardaron.')
    return _re_render_con_errores(request, form, modal='editar', seleccionada=geomembrana)


# ----------------------------------------------------------------------
# DELETE
# ----------------------------------------------------------------------
@_requiere_escritura
@require_http_methods(['POST'])
def eliminar(request, pk):
    """
    Borrado con salvaguarda de trazabilidad.

    Si la geomembrana tiene sensores, dispositivos, lecturas o alertas, un
    delete fisico borraria el historico del cultivo: en ese caso se desactiva.
    El borrado real solo procede sobre fichas sin ningun dato asociado.

    :param pk: identificador de la geomembrana
    """
    geomembrana = get_object_or_404(Geomembrana, pk=pk)
    codigo = geomembrana.codigo_identificacion

    if geomembrana.tiene_dependencias:
        dep = geomembrana.dependencias
        geomembrana.estado = 'inactivo'
        geomembrana.apta_para_produccion = False
        geomembrana.save(update_fields=['estado', 'apta_para_produccion', 'fecha_edicion'])

        logger.warning(
            'Geomembrana %s desactivada (no borrada) por usuario=%s. Dependencias: %s',
            codigo, request.user.email, dep,
        )
        messages.warning(
            request,
            f'{codigo} tiene {dep["lecturas"]} lectura(s), {dep["sensores"]} sensor(es) y '
            f'{dep["alertas"]} alerta(s) asociadas. Se desactivó en lugar de borrarse '
            f'para conservar la trazabilidad del cultivo.',
        )
        return redirect('piscinas:listar')

    try:
        geomembrana.delete()
    except ProtectedError:
        # Red de seguridad: alguien pudo insertar un registro entre la
        # comprobacion y el delete.
        geomembrana.estado = 'inactivo'
        geomembrana.apta_para_produccion = False
        geomembrana.save(update_fields=['estado', 'apta_para_produccion', 'fecha_edicion'])
        messages.warning(request, f'{codigo} quedó con registros asociados: se desactivó.')
        return redirect('piscinas:listar')

    logger.info('Geomembrana eliminada codigo=%s por usuario=%s', codigo, request.user.email)
    messages.success(request, f'Geomembrana {codigo} eliminada.')
    return redirect('piscinas:listar')


# ----------------------------------------------------------------------
# Auxiliar
# ----------------------------------------------------------------------
def _re_render_con_errores(request, form, modal, seleccionada=None):
    """
    Vuelve a pintar el listado conservando el formulario con sus errores.

    :param form: GeomembranaForm no valido
    :param modal: 'crear' o 'editar', para que el template lo reabra
    :param seleccionada: instancia en edicion, si aplica
    :return: HttpResponse
    """
    queryset = Geomembrana.objects.con_relaciones()
    paginador = Paginator(queryset, POR_PAGINA)
    pagina = paginador.get_page(1)

    if seleccionada is None and pagina.object_list:
        seleccionada = pagina.object_list[0]

    contexto = {
        'actual': MODULO,
        'pagina': pagina,
        'geomembranas': pagina.object_list,
        'seleccionada': seleccionada,
        'aptitud': evaluar_aptitud(seleccionada) if seleccionada else None,
        'kpis': _resumen_kpis(queryset),
        'termino': '',
        'filtro_estado': '',
        'estados_disponibles': Geomembrana.ESTADOS,
        'puede_editar': True,
        'form': form if modal == 'crear' else GeomembranaForm(),
        'form_editar': form if modal == 'editar' else (
            GeomembranaForm(instance=seleccionada) if seleccionada else None
        ),
        'abrir_modal': modal,
    }
    return render(request, 'funcionalidades/geomenbranas.html', contexto)
