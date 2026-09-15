"""
Formularios de gestion de usuarios.

La contrasena nunca se asigna directamente al campo: siempre pasa por
set_password(), que aplica el hasher configurado (PBKDF2 por defecto en
Django). Un ModelForm plano guardaria el texto plano en la columna.
"""
import re

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Rol, Usuario

PATRON_CELULAR = re.compile(r'^\+?\d{7,15}$')


class UsuarioForm(forms.ModelForm):
    """
    Alta y edicion de usuarios del sistema.

    En alta la contrasena es obligatoria; en edicion se deja vacia para
    conservar la actual.
    """

    password1 = forms.CharField(
        label='Contraseña', required=False, strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'gm-form-input', 'autocomplete': 'new-password',
            'placeholder': 'Mínimo 8 caracteres'}),
    )
    password2 = forms.CharField(
        label='Repetir contraseña', required=False, strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'gm-form-input', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = Usuario
        fields = [
            'nombre_completo', 'email', 'rol', 'documento_identidad',
            'numero_celular', 'numero_whatsapp', 'foto_perfil', 'estado',
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Nombre y apellidos'}),
            'email': forms.EmailInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'persona@correo.com',
                'autocomplete': 'email'}),
            'rol': forms.Select(attrs={'class': 'gm-form-input'}),
            'documento_identidad': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': 'Cédula o TI'}),
            'numero_celular': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': '3001234567'}),
            'numero_whatsapp': forms.TextInput(attrs={
                'class': 'gm-form-input', 'placeholder': '3001234567'}),
            'foto_perfil': forms.ClearableFileInput(attrs={
                'class': 'gm-form-input', 'accept': 'image/*'}),
            'estado': forms.Select(attrs={'class': 'gm-form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].queryset = Rol.objects.filter(estado='activo')
        self.fields['rol'].empty_label = None

        if self.instance.pk:
            self.fields['password1'].help_text = 'Déjala vacía para no cambiarla.'
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True

    def clean_email(self):
        """Normaliza el correo a minusculas y valida unicidad."""
        email = (self.cleaned_data.get('email') or '').strip().lower()
        duplicado = Usuario.objects.filter(email=email)
        if self.instance.pk:
            duplicado = duplicado.exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise forms.ValidationError('Ya existe un usuario con ese correo.')
        return email

    def clean_documento_identidad(self):
        """Documento vacio se guarda como None: la columna es unique."""
        documento = (self.cleaned_data.get('documento_identidad') or '').strip()
        if not documento:
            return None
        duplicado = Usuario.objects.filter(documento_identidad=documento)
        if self.instance.pk:
            duplicado = duplicado.exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise forms.ValidationError('Ya existe un usuario con ese documento.')
        return documento

    def _limpiar_telefono(self, campo):
        """Valida un numero de telefono y lo devuelve sin separadores."""
        valor = (self.cleaned_data.get(campo) or '').strip().replace(' ', '').replace('-', '')
        if not valor:
            return None
        if not PATRON_CELULAR.match(valor):
            raise forms.ValidationError('Número inválido. Usa solo dígitos, 7 a 15.')
        return valor

    def clean_numero_celular(self):
        return self._limpiar_telefono('numero_celular')

    def clean_numero_whatsapp(self):
        return self._limpiar_telefono('numero_whatsapp')

    def clean(self):
        """Valida que ambas contrasenas coincidan y cumplan las politicas."""
        datos = super().clean()
        p1 = datos.get('password1')
        p2 = datos.get('password2')

        if p1 or p2:
            if p1 != p2:
                self.add_error('password2', 'Las contraseñas no coinciden.')
            else:
                try:
                    # Aplica AUTH_PASSWORD_VALIDATORS: longitud, comun, numerica.
                    validate_password(p1, self.instance)
                except ValidationError as exc:
                    self.add_error('password1', exc)
        elif not self.instance.pk:
            self.add_error('password1', 'La contraseña es obligatoria al crear un usuario.')

        return datos

    def save(self, commit=True):
        """Persiste el usuario aplicando el hash de la contrasena si cambio."""
        usuario = super().save(commit=False)
        password = self.cleaned_data.get('password1')
        if password:
            usuario.set_password(password)
        if commit:
            usuario.save()
        return usuario
