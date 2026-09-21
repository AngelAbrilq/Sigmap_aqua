from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('piscinas', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventoSistema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_evento', models.CharField(choices=[('config_umbral', 'Cambio de umbrales'), ('usuario_alta', 'Alta de usuario'), ('usuario_edicion', 'Edición de usuario'), ('usuario_estado', 'Cambio de estado de usuario'), ('sesion_inicio', 'Inicio de sesión'), ('alerta_reconocida', 'Alerta reconocida'), ('alerta_resuelta', 'Alerta resuelta'), ('sistema', 'Evento del sistema')], max_length=30, verbose_name='Tipo')),
                ('nivel', models.CharField(choices=[('info', 'Informativo'), ('advertencia', 'Advertencia'), ('critico', 'Crítico')], default='info', max_length=12, verbose_name='Nivel')),
                ('descripcion', models.CharField(max_length=255, verbose_name='Descripción')),
                ('datos', models.JSONField(blank=True, default=dict, verbose_name='Datos')),
                ('ip_origen', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP de origen')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha')),
                ('geomembrana', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos', to='piscinas.geomembrana', verbose_name='Piscina')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
            ],
            options={
                'verbose_name': 'Evento del sistema',
                'verbose_name_plural': 'Eventos del sistema',
                'db_table': 'eventos_sistema',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='eventosistema',
            index=models.Index(fields=['tipo_evento', '-created_at'], name='idx_evt_tipo_fecha'),
        ),
        migrations.AddIndex(
            model_name='eventosistema',
            index=models.Index(fields=['geomembrana', '-created_at'], name='idx_evt_geo_fecha'),
        ),
    ]
