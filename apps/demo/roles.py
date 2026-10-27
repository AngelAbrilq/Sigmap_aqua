"""
Los tres perfiles que se presentan con QR y cómo se ven en pantalla.

Un solo lugar define colores, textos y el usuario de cada rol: lo usan las
vistas, el generador de QR y el comando de consola (DRY).
"""

from apps.usuarios.permissions import ROL_APRENDIZ, ROL_INSTRUCTOR, ROL_OPERARIO

# Correos que crea `crear_usuarios_prueba`; se prefieren si existen.
EMAIL_PREFERIDO = {
    ROL_INSTRUCTOR: 'instructor@sigmap.com',
    ROL_OPERARIO: 'operario@sigmap.com',
    ROL_APRENDIZ: 'aprendiz@sigmap.com',
}

ROLES_DEMO = {
    ROL_INSTRUCTOR: {
        'slug': 'instructor',
        'titulo': 'Instructor Líder',
        'lema': 'Control total del sistema',
        'color': '#2f80ed',
        'color2': '#22d3ee',
        'icono': '🧭',
        'capacidades': [
            'Valida los análisis de la IA',
            'Gestiona usuarios, piscinas y sensores',
            'Revisa la auditoría de eventos',
        ],
    },
    ROL_OPERARIO: {
        'slug': 'operario',
        'titulo': 'Operario',
        'lema': 'Operación en campo',
        'color': '#0d9488',
        'color2': '#5eead4',
        'icono': '🛠️',
        'capacidades': [
            'Monitorea el agua en tiempo real',
            'Atiende alertas de los sensores',
            'Genera análisis con IA',
        ],
    },
    ROL_APRENDIZ: {
        'slug': 'aprendiz',
        'titulo': 'Aprendiz',
        'lema': 'Consulta y aprendizaje',
        'color': '#7c3aed',
        'color2': '#c084fc',
        'icono': '🎓',
        'capacidades': [
            'Consulta gráficas e historial',
            'Compara periodos de producción',
            'Lee el análisis predictivo',
        ],
    },
}

ORDEN_ROLES = (ROL_INSTRUCTOR, ROL_OPERARIO, ROL_APRENDIZ)


def usuario_demo(nombre_rol):
    """
    Usuario activo que representa a un rol en la demostración.

    Prefiere el correo de prueba conocido; si no existe, toma el primer
    usuario activo de ese rol.

    :param nombre_rol: nombre exacto del rol (ej. 'Operario')
    :return: usuarios.Usuario o None
    """
    from apps.usuarios.models import Usuario

    activos = Usuario.objects.select_related('rol').filter(
        rol__nombre_rol=nombre_rol, estado='activo', is_active=True)
    preferido = activos.filter(email=EMAIL_PREFERIDO.get(nombre_rol)).first()
    return preferido or activos.order_by('pk').first()
