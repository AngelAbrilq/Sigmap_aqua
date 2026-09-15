"""Tablas reportes y comparaciones_datos."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('piscinas', '0002_geomembrana_ficha_tecnica'),
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reporte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=255, verbose_name='Título')),
                ('tipo_reporte', models.CharField(
                    choices=[('diario', 'Diario'), ('semanal', 'Semanal'),
                             ('mensual', 'Mensual'), ('personalizado', 'Personalizado')],
                    default='semanal', max_length=15, verbose_name='Tipo')),
                ('descripcion', models.TextField(blank=True, verbose_name='Descripción')),
                ('fecha_inicio', models.DateField(verbose_name='Desde')),
                ('fecha_fin', models.DateField(verbose_name='Hasta')),
                ('datos_reporte', models.JSONField(default=dict, verbose_name='Datos agregados')),
                ('resumen_ejecutivo', models.TextField(blank=True, verbose_name='Resumen')),
                ('conclusiones', models.TextField(blank=True, verbose_name='Conclusiones')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('geomembrana', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name='reportes',
                    to='piscinas.geomembrana', verbose_name='Piscina')),
                ('generado_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reportes_generados', to='usuarios.usuario')),
            ],
            options={
                'verbose_name': 'Reporte', 'verbose_name_plural': 'Reportes',
                'db_table': 'reportes', 'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='ComparacionDatos',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('periodo_1_inicio', models.DateField(verbose_name='Periodo 1 desde')),
                ('periodo_1_fin', models.DateField(verbose_name='Periodo 1 hasta')),
                ('periodo_2_inicio', models.DateField(verbose_name='Periodo 2 desde')),
                ('periodo_2_fin', models.DateField(verbose_name='Periodo 2 hasta')),
                ('resultados_comparacion', models.JSONField(default=dict,
                                                            verbose_name='Resultados')),
                ('diferencias_principales', models.TextField(blank=True,
                                                             verbose_name='Diferencias')),
                ('conclusiones', models.TextField(blank=True, verbose_name='Conclusiones')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('geomembrana', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name='comparaciones',
                    to='piscinas.geomembrana', verbose_name='Piscina')),
                ('usuario', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='comparaciones', to='usuarios.usuario')),
            ],
            options={
                'verbose_name': 'Comparación de periodos',
                'verbose_name_plural': 'Comparaciones de periodos',
                'db_table': 'comparaciones_datos', 'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.AddIndex(
            model_name='reporte',
            index=models.Index(fields=['geomembrana', '-fecha_creacion'],
                               name='idx_rep_geo_fecha'),
        ),
    ]
