from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Rol(models.Model):
    ESTADOS = [('activo', 'Activo'), ('inactivo', 'Inactivo')]

    nombre_rol = models.CharField('Nombre del rol', max_length=50, unique=True)
    descripcion = models.TextField('Descripción', blank=True)
    permisos = models.JSONField('Permisos', default=dict, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        ordering = ['id']

    def __str__(self):
        return self.nombre_rol

    def tiene_permiso(self, clave):
        """Consulta un permiso puntual del JSON. Ej: rol.tiene_permiso('ver_alertas')"""
        return bool(self.permisos.get(clave, False))


class UsuarioManager(BaseUserManager):
    """Manager que usa email en lugar de username."""

    def create_user(self, email, nombre_completo, password=None, **extra):
        if not email:
            raise ValueError('El usuario debe tener un correo electrónico')
        email = self.normalize_email(email)
        usuario = self.model(email=email, nombre_completo=nombre_completo, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, nombre_completo, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('estado', 'activo')

        if not extra.get('rol') and not extra.get('rol_id'):
            from apps.usuarios.models import Rol
            rol, _ = Rol.objects.get_or_create(
                nombre_rol='Instructor Lider',
                defaults={
                    'descripcion': 'Administrador del sistema',
                    'permisos': {},
                },
            )
            extra['rol'] = rol

        return self.create_user(email, nombre_completo, password, **extra)


class Usuario(AbstractUser):
    ESTADOS = [('activo', 'Activo'), ('inactivo', 'Inactivo')]

    # Campos de AbstractUser que no usamos
    username = None
    first_name = None
    last_name = None

    email = models.EmailField('Correo electrónico', max_length=100, unique=True)
    nombre_completo = models.CharField('Nombre completo', max_length=150)
    rol = models.ForeignKey(
        Rol, on_delete=models.PROTECT, related_name='usuarios',
        verbose_name='Rol'
    )
    documento_identidad = models.CharField(
        'Documento de identidad', max_length=20, blank=True, null=True, unique=True
    )
    numero_celular = models.CharField('Celular', max_length=15, blank=True, null=True)
    numero_whatsapp = models.CharField('WhatsApp', max_length=15, blank=True, null=True)
    foto_perfil = models.ImageField(
        'Foto de perfil', upload_to='usuarios/', blank=True, null=True
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default='activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_edicion = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre_completo']

    objects = UsuarioManager()

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['nombre_completo']

    def __str__(self):
        return f'{self.nombre_completo} ({self.email})'