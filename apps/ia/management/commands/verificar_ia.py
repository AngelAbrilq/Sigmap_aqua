"""
Comprueba que la integracion con Gemini esta bien configurada.

Uso:
    python manage.py verificar_ia
    python manage.py verificar_ia --piscina GEO-001

Hace una llamada real y mínima a la API: es la única forma de saber si la
clave sirve. Consume una fracción ínfima de la cuota gratuita.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ia.services import ErrorIA, _llamar_gemini, construir_contexto
from apps.piscinas.models import Geomembrana


class Command(BaseCommand):
    help = 'Verifica la clave y el modelo de Gemini con una llamada real.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--piscina', type=str, default=None,
            help='Código de la geomembrana con la que probar el contexto.')

    def handle(self, *args, **opciones):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nVerificación de la integración con Gemini\n'))

        # --- 1. Configuracion ---
        clave = getattr(settings, 'GEMINI_API_KEY', '')
        modelo = getattr(settings, 'GEMINI_MODEL', '')

        if not clave:
            self.stdout.write(self.style.ERROR(
                '  [FALLA] GEMINI_API_KEY no está definida.\n'
                '          Agrégala al archivo .env:  GEMINI_API_KEY=tu_clave\n'
                '          Se obtiene gratis en https://aistudio.google.com/apikey'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'  [OK]    GEMINI_API_KEY leída ({len(clave)} caracteres, '
            f'termina en …{clave[-4:]})'))
        self.stdout.write(self.style.SUCCESS(f'  [OK]    Modelo: {modelo}'))

        # --- 2. Llamada real ---
        self.stdout.write('\n  Contactando a la API…')
        try:
            respuesta = _llamar_gemini(
                'Responde con un diagnóstico de una sola frase confirmando que '
                'recibiste esta prueba de conexión, sin anomalías ni '
                'recomendaciones, y con confianza 100.'
            )
        except ErrorIA as error:
            self.stdout.write(self.style.ERROR(f'  [FALLA] {error}'))
            return

        self.stdout.write(self.style.SUCCESS('  [OK]    La API respondió.'))

        faltantes = [c for c in ('diagnostico', 'anomalias', 'recomendaciones',
                                 'riesgo_proyectado', 'confianza')
                     if c not in respuesta]
        if faltantes:
            self.stdout.write(self.style.WARNING(
                f'  [AVISO] La respuesta no trae: {", ".join(faltantes)}. '
                f'Revisa que el modelo "{modelo}" acepte responseSchema.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                '  [OK]    El JSON estructurado llegó completo.'))
            self.stdout.write(f'\n          Respuesta: {respuesta["diagnostico"]}')

        # --- 3. Contexto de una piscina real ---
        self.stdout.write('')
        piscinas = Geomembrana.objects.all()
        if opciones['piscina']:
            piscinas = piscinas.filter(codigo_identificacion=opciones['piscina'].upper())

        piscina = piscinas.first()
        if piscina is None:
            self.stdout.write(self.style.WARNING(
                '  [AVISO] No hay geomembranas registradas: no se puede probar '
                'el contexto de análisis.'))
        else:
            contexto = construir_contexto(piscina, dias=7)
            lecturas = contexto['total_lecturas']
            if lecturas:
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK]    {piscina.codigo_identificacion}: {lecturas} lectura(s) '
                    f'en 7 días, {len(contexto["parametros"])} parámetro(s). '
                    f'Lista para analizar.'))
            else:
                self.stdout.write(self.style.WARNING(
                    f'  [AVISO] {piscina.codigo_identificacion} no tiene lecturas en '
                    f'7 días. El análisis se rechazará hasta que los sensores '
                    f'envíen datos.'))

        self.stdout.write(self.style.SUCCESS(
            '\n  Integración lista. Ya puedes generar análisis desde /ai/\n'))
