def usuario_context(request):
    """
    Inyecta nombre_usuario y rol_usuario en todos los templates.
    Disponible cuando el usuario está autenticado.
    """
    if request.user.is_authenticated:
        nombre_usuario = request.user.nombre_completo or request.user.email
        rol_usuario = request.user.rol.nombre_rol if request.user.rol_id else 'Sin rol'
    else:
        nombre_usuario = ''
        rol_usuario = ''

    return {
        'nombre_usuario': nombre_usuario,
        'rol_usuario': rol_usuario,
    }
