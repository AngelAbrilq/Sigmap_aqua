"""
Contrasta las predicciones vencidas contra las lecturas reales.

Uso:
    python manage.py evaluar_predicciones
    python manage.py evaluar_predicciones --piscina GEO-001
    python manage.py evaluar_predicciones --simular

Pensado para correr a diario desde el Programador de tareas de Windows.
Es idempotente: una predicción ya evaluada no vuelve a entrar.
"""
from django.core.management.base import BaseCommand

from apps.ia.models import Prediccion
from apps.ia.services import evaluar_predicciones_vencidas, precision_historica
from apps.piscinas.models import Geomembrana


class Command(BaseCommand):
    help = 'Evalúa las predicciones de IA cuya fecha objetivo ya pasó.'

    def add_arguments(self, parser):
        parser.add_argument('--piscina', type=str, default=None,
                            help='Código de la geomembrana a evaluar.')
        parser.add_argument('--simular', action='store_true',
                            help='Muestra qué se evaluaría, sin guardar nada.')

    def handle(self, *args, **opciones):
        geomembrana = None
        if opciones['piscina']:
            geomembrana = Geomembrana.objects.filter(
                codigo_identificacion=opciones['piscina'].upper()).first()
            if geomembrana is None:
                self.stdout.write(self.style.ERROR(
                    f'No existe la geomembrana {opciones["piscina"]}.'))
                return

        pendientes = Prediccion.objects.vencidas().con_relaciones()
        if geomembrana is not None:
            pendientes = pendientes.filter(geomembrana=geomembrana)

        cantidad = pendientes.count()
        if not cantidad:
            self.stdout.write(self.style.SUCCESS(
                'No hay predicciones vencidas por evaluar.'))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n{cantidad} predicción(es) vencida(s)\n'))

        if opciones['simular']:
            for prediccion in pendientes:
                resultado = prediccion.evaluar(guardar=False)
                self.stdout.write(
                    f'  {prediccion.geomembrana.codigo_identificacion} · '
                    f'{prediccion.tipo_parametro.nombre_parametro} · '
                    f'{prediccion.fecha_objetivo}: previsto '
                    f'{prediccion.rango_previsto} → real '
                    f'{prediccion.valor_real if prediccion.valor_real is not None else "sin datos"} '
                    f'[{resultado}]')
            self.stdout.write(self.style.WARNING('\n  Simulación: no se guardó nada.\n'))
            return

        recuento = evaluar_predicciones_vencidas(geomembrana)

        self.stdout.write(self.style.SUCCESS(
            f'  Acertadas:  {recuento["acertada"]}'))
        self.stdout.write(self.style.ERROR(
            f'  Fallidas:   {recuento["fallida"]}'))
        self.stdout.write(self.style.WARNING(
            f'  Sin datos:  {recuento["sin_datos"]}  '
            f'(no hubo lecturas ese día; no cuentan en la precisión)'))

        stats = precision_historica(geomembrana)
        if stats['tasa_acierto'] is not None:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'\n  Precisión acumulada (90 días): {stats["tasa_acierto"]}% '
                f'sobre {stats["evaluadas"]} predicción(es) evaluada(s)\n'))
        else:
            self.stdout.write(
                '\n  Todavía no hay predicciones evaluadas para calcular precisión.\n')
