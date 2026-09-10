from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.usuarios.models import Rol, Usuario
from apps.usuarios.permissions import ROL_APRENDIZ, ROL_INSTRUCTOR, ROL_OPERARIO

# (rol, email, nombre_completo, password)
USUARIOS_PRUEBA = [
    (ROL_INSTRUCTOR, 'instructor@sigmap.com', 'Ana Instructora', 'Instructor2026*'),
    (ROL_APRENDIZ,   'aprendiz@sigmap.com',   'Luis Aprendiz',   'Aprendiz2026*'),
    (ROL_OPERARIO,   'operario@sigmap.com',   'Carlos Operario', 'Operario2026*'),
]


class Command(BaseCommand):
    help = 'Crea los roles, los grupos espejo y un usuario de prueba por rol.'

    @transaction.atomic
    def handle(self, *args, **options):
        for nombre_rol, email, nombre, password in USUARIOS_PRUEBA:
            rol, _ = Rol.objects.get_or_create(
                nombre_rol=nombre_rol,
                defaults={'descripcion': nombre_rol, 'permisos': {}, 'estado': 'activo'},
            )
            grupo, _ = Group.objects.get_or_create(name=nombre_rol)

            usuario, creado = Usuario.objects.get_or_create(
                email=email,
                defaults={
                    'nombre_completo': nombre,
                    'rol': rol,
                    'estado': 'activo',
                    'is_staff': False,      # sin acceso al admin nativo
                    'is_superuser': False,
                },
            )
            usuario.rol = rol
            usuario.estado = 'activo'
            usuario.is_staff = False
            usuario.is_superuser = False
            usuario.set_password(password)
            usuario.save()
            usuario.groups.set([grupo])

            etiqueta = 'Creado' if creado else 'Actualizado'
            self.stdout.write(self.style.SUCCESS(
                f'{etiqueta}: {email} / {password}  ->  {nombre_rol}'
            ))

        self.stdout.write(self.style.WARNING(
            '\nUsuarios de prueba listos. Entra por /auth/login/'
        ))
