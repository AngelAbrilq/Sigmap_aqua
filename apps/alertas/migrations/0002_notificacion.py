"""
Modelo Notificacion (tabla `notificaciones_push`).

Estaba en el ERD y `services.notificar_alerta` ya lo usaba, pero la clase
nunca se escribio: cualquier llamada a esa funcion terminaba en NameError.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alertas', '0001_initial'),
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notificacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=255, verbose_name='Título')),
                ('mensaje', models.TextField(verbose_name='Mensaje')),
                ('canal', models.CharField(
                    choices=[('sistema', 'En el sistema'), ('push', 'Push'),
                             ('whatsapp', 'WhatsApp'), ('email', 'Correo')],
                    default='sistema', max_length=10)),
                ('enviada', models.BooleanField(default=True, verbose_name='Enviada')),
                ('leida', models.BooleanField(default=False, verbose_name='Leída')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_lectura', models.DateTimeField(blank=True, null=True,
                                                       verbose_name='Leída en')),
                ('alerta', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notificaciones', to='alertas.alerta')),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notificaciones', to='usuarios.usuario',
                    verbose_name='Destinatario')),
            ],
            options={
                'verbose_name': 'Notificación',
                'verbose_name_plural': 'Notificaciones',
                'db_table': 'notificaciones_push',
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.AddIndex(
            model_name='notificacion',
            index=models.Index(fields=['usuario', 'leida', '-fecha_creacion'],
                               name='idx_notif_usuario_leida'),
        ),
    ]
