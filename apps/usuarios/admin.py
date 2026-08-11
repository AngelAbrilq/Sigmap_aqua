from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Rol, Usuario


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('nombre_rol', 'descripcion', 'estado')
    list_filter = ('estado',)
    search_fields = ('nombre_rol',)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'nombre_completo', 'rol', 'estado', 'is_staff')
    list_filter = ('rol', 'estado', 'is_staff')
    search_fields = ('email', 'nombre_completo', 'documento_identidad')
    ordering = ('nombre_completo',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información personal', {
            'fields': ('nombre_completo', 'documento_identidad',
                       'numero_celular', 'numero_whatsapp', 'foto_perfil')
        }),
        ('Rol y estado', {'fields': ('rol', 'estado')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Fechas', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre_completo', 'rol', 'password1', 'password2'),
        }),
    )