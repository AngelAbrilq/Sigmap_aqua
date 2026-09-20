"""
Indice compuesto para el historial filtrado por piscina y parametro.

Es la consulta mas frecuente de la app movil. Sin el, MySQL filtra con el
indice de geomembrana y ordena el resto en memoria (Using filesort), que deja
de ser viable cuando `lecturas_sensores` acumula meses de mediciones.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoreo', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='lectura',
            index=models.Index(
                fields=['geomembrana', 'tipo_parametro', '-timestamp_lectura'],
                name='idx_lect_geo_param_ts'),
        ),
    ]
