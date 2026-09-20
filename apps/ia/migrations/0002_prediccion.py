"""
Tabla predicciones_ia: proyecciones falsables y su contraste contra lo medido.

Es lo que permite medir si la IA acierta. Sin esta tabla, una recomendación
generada por el modelo no se puede auditar contra la realidad.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ia', '0001_initial'),
        ('monitoreo', '0001_initial'),
        ('piscinas', '0002_geomembrana_ficha_tecnica'),
    ]

    operations = [
        migrations.CreateModel(
            name='Prediccion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('valor_esperado', models.DecimalField(
                    decimal_places=4, max_digits=10, verbose_name='Valor esperado')),
                ('valor_min', models.DecimalField(
                    decimal_places=4, max_digits=10, verbose_name='Mínimo previsto')),
                ('valor_max', models.DecimalField(
                    decimal_places=4, max_digits=10, verbose_name='Máximo previsto')),
                ('probabilidad_fuera_rango', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    verbose_name='Probabilidad de salirse de rango (%)')),
                ('justificacion', models.TextField(blank=True, verbose_name='Justificación')),
                ('horizonte_dias', models.PositiveSmallIntegerField(
                    default=3, verbose_name='Horizonte (días)')),
                ('fecha_objetivo', models.DateField(
                    help_text='Día cuyo promedio real se comparará contra esta predicción.',
                    verbose_name='Fecha objetivo')),
                ('fecha_generacion', models.DateTimeField(auto_now_add=True)),
                ('estado', models.CharField(
                    choices=[('pendiente', 'Pendiente de evaluar'),
                             ('acertada', 'Acertada'), ('fallida', 'Fallida'),
                             ('sin_datos', 'Sin datos para evaluar')],
                    default='pendiente', max_length=12)),
                ('valor_real', models.DecimalField(
                    blank=True, decimal_places=4, max_digits=10, null=True,
                    verbose_name='Valor real medido')),
                ('error_absoluto', models.DecimalField(
                    blank=True, decimal_places=4, max_digits=10, null=True,
                    verbose_name='Error absoluto')),
                ('lecturas_evaluadas', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='Lecturas contrastadas')),
                ('fecha_evaluacion', models.DateTimeField(blank=True, null=True)),
                ('analisis', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='predicciones', to='ia.analisisia',
                    verbose_name='Análisis de origen')),
                ('geomembrana', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='predicciones', to='piscinas.geomembrana',
                    verbose_name='Piscina')),
                ('tipo_parametro', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='predicciones', to='monitoreo.tipoparametro',
                    verbose_name='Parámetro')),
            ],
            options={
                'verbose_name': 'Predicción',
                'verbose_name_plural': 'Predicciones',
                'db_table': 'predicciones_ia',
                'ordering': ['-fecha_generacion', 'tipo_parametro'],
            },
        ),
        migrations.AddIndex(
            model_name='prediccion',
            index=models.Index(fields=['estado', 'fecha_objetivo'],
                               name='idx_pred_estado_fecha'),
        ),
        migrations.AddIndex(
            model_name='prediccion',
            index=models.Index(fields=['geomembrana', '-fecha_generacion'],
                               name='idx_pred_geo_fecha'),
        ),
    ]
