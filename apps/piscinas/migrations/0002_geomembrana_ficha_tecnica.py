"""
Ficha tecnica de la geomembrana e indice de estado.

Los cuatro campos nuevos (espesor, proveedor, garantia, vida util) ya se
exigian en la maqueta de la interfaz y en la especificacion de casos de uso,
pero no existian en el modelo: el HTML los mostraba con datos ficticios.

El indice acompana el filtro por estado del listado, que es el acceso mas
frecuente del modulo.
"""
import decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('piscinas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='geomembrana',
            name='espesor_mm',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                validators=[django.core.validators.MinValueValidator(decimal.Decimal('0.01'))],
                verbose_name='Espesor (mm)',
            ),
        ),
        migrations.AddField(
            model_name='geomembrana',
            name='proveedor',
            field=models.CharField(blank=True, max_length=150, verbose_name='Proveedor'),
        ),
        migrations.AddField(
            model_name='geomembrana',
            name='garantia_anios',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name='Garantía (años)'
            ),
        ),
        migrations.AddField(
            model_name='geomembrana',
            name='vida_util_anios',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name='Vida útil estimada (años)'
            ),
        ),
        migrations.AlterField(
            model_name='geomembrana',
            name='area_m2',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                validators=[django.core.validators.MinValueValidator(decimal.Decimal('0.01'))],
                verbose_name='Área (m²)',
            ),
        ),
        migrations.AlterField(
            model_name='geomembrana',
            name='profundidad_promedio',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                validators=[django.core.validators.MinValueValidator(decimal.Decimal('0.01'))],
                verbose_name='Profundidad (m)',
            ),
        ),
        migrations.AlterField(
            model_name='geomembrana',
            name='volumen_agua_m3',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                help_text='Si se deja vacío se calcula como área × profundidad.',
                verbose_name='Volumen (m³)',
            ),
        ),
        migrations.AddIndex(
            model_name='geomembrana',
            index=models.Index(
                fields=['estado', 'apta_para_produccion'], name='idx_geo_estado_apta'
            ),
        ),
    ]
