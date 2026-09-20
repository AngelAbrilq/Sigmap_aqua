"""
Permisos de la API móvil.

Reutiliza la matriz RBAC de apps.usuarios.permissions en vez de duplicarla:
si mañana cambia lo que puede hacer un Operario, cambia en un solo sitio y
aplica a la web y a la app por igual.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.usuarios.permissions import puede_editar_modulo, puede_ver_modulo


class PermisoModulo(BasePermission):
    """
    Permiso por módulo, declarado en la vista con `modulo = '<url_name>'`.

    GET/HEAD/OPTIONS exigen permiso de lectura; el resto, de escritura.
    Una vista sin `modulo` solo exige estar autenticado.
    """

    message = 'Tu rol no tiene permiso para esta acción.'

    def has_permission(self, request, view):
        usuario = request.user

        if not usuario.is_authenticated:
            return False

        # Una cuenta dada de baja conserva su token hasta que expire: se
        # bloquea aquí, no solo en el login.
        if getattr(usuario, 'estado', None) != 'activo':
            self.message = 'La cuenta está inactiva.'
            return False

        modulo = getattr(view, 'modulo', None)
        if modulo is None:
            return True

        if request.method in SAFE_METHODS:
            return puede_ver_modulo(usuario, modulo)
        return puede_editar_modulo(usuario, modulo)
