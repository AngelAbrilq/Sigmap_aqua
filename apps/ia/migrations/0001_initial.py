"""Tabla analisis_ia: persistencia de los analisis generados por Gemini."""
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
            name='AnalisisIA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('tipo_analisis', models.CharField(
                    choices=[('diagnostico', 'Diagnóstico del estado actual'),
                             ('prediccion', 'Predicción de riesgo'),
                             ('recomendacion', 'Recomendación operativa')],
                    default='diagnostico', max_length=15, verbose_name='Tipo')),
                ('datos_entrada', models.JSONField(default=dict, verbose_name='Datos de entrada')),
                ('resultados_salida', models.JSONField(default=dict, verbose_name='Resultados')),
                ('descripcion_analisis', models.TextField(blank=True, verbose_name='Análisis')),
                ('recomendaciones', models.TextField(blank=True, verbose_name='Recomendaciones')),
                ('anomalias_detectadas', models.JSONField(blank=True, default=list,
                                                          verbose_name='Anomalías')),
                ('confianza', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True,
                    help_text='0 a 100. La declara el modelo, no es una medida estadística.',
                    verbose_name='Confianza')),
                ('modelo_usado', models.CharField(blank=True, max_length=60,
                                                  verbose_name='Modelo')),
                ('estado', models.CharField(
                    choices=[('generado', 'Generado'), ('validado', 'Validado'),
                             ('descartado', 'Descartado'), ('implementado', 'Implementado')],
                    default='generado', max_length=15)),
                ('fecha_generacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_validacion', models.DateTimeField(blank=True, null=True)),
                ('geomembrana', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='analisis_ia', to='piscinas.geomembrana',
                    verbose_name='Piscina')),
                ('validado_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='analisis_validados', to='usuarios.usuario')),
            ],
            options={
                'verbose_name': 'Análisis de IA',
                'verbose_name_plural': 'Análisis de IA',
                'db_table': 'analisis_ia',
                'ordering': ['-fecha_generacion'],
            },
        ),
        migrations.AddIndex(
            model_name='analisisia',
            index=models.Index(fields=['geomembrana', '-fecha_generacion'],
                               name='idx_ia_geo_fecha'),
        ),
        migrations.AddIndex(
            model_name='analisisia',
            index=models.Index(fields=['estado'], name='idx_ia_estado'),
        ),
    ]
