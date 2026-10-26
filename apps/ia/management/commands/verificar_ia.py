"""
Comprueba que la integracion con la IA esta bien configurada.

Uso:
    python manage.py verificar_ia
    python manage.py verificar_ia --piscina GEO-001

Hace una llamada real y mínima a cada proveedor configurado (DeepSeek y, si
tiene clave, Gemini): es la única forma de saber si la clave sirve.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ia.services import (
    ErrorIA, _llamar_deepseek, _llamar_gemini, _modelo_de, construir_contexto,
    proveedores_configurados,
)
from apps.piscinas.models import Geomembrana

CAMPOS_ESPERADOS = ('diagnostico', 'anomalias', 'recomendaciones',
                    'riesgo_proyectado', 'confianza')
PROMPT_PRUEBA = (
    'Responde con un diagnóstico de una sola frase confirmando que recibiste '
    'esta prueba de conexión, sin anomalías ni recomendaciones, y con confianza 100.'
)
LLAMADAS = {'deepseek': _llamar_deepseek, 'gemini': _llamar_gemini}
VARIABLES = {'deepseek': 'DEEPSEEK_API_KEY', 'gemini': 'GEMINI_API_KEY'}


class Command(BaseCommand):
    help = 'Verifica las claves y modelos de IA con una llamada real.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--piscina', type=str, default=None,
            help='Código de la geomembrana con la que probar el contexto.')

    def handle(self, *args, **opciones):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\nVerificación de la integración con IA\n'))

        principal = getattr(settings, 'IA_PROVEEDOR', 'deepseek')
        self.stdout.write(f'  Proveedor principal: {principal}')

        proveedores = proveedores_configurados()
        if not proveedores:
            self.stdout.write(self.style.ERROR(
                '  [FALLA] No hay ninguna clave de IA.\n'
                '          Agrega al archivo .env:  DEEPSEEK_API_KEY=tu_clave\n'
                '          Se obtiene en https://platform.deepseek.com/api_keys'))
            return

        alguno_ok = False
        for proveedor in proveedores:
            alguno_ok |= self._probar(proveedor)

        if not alguno_ok:
            return

        self._probar_contexto(opciones['piscina'])
        self.stdout.write(self.style.SUCCESS(
            '\n  Integración lista. Ya puedes generar análisis desde /ai/\n'))

    def _probar(self, proveedor):
        """
        Llama a un proveedor y reporta si la respuesta trae el JSON esperado.

        :param proveedor: 'deepseek' | 'gemini'
        :return: True si respondió
        """
        clave = getattr(settings, VARIABLES[proveedor], '')
        self.stdout.write(f'\n  [{proveedor}] {VARIABLES[proveedor]} leída '
                          f'({len(clave)} caracteres, termina en …{clave[-4:]})')
        self.stdout.write(f'  [{proveedor}] Modelo: {_modelo_de(proveedor)}')
        self.stdout.write(f'  [{proveedor}] Contactando a la API…')
        try:
            respuesta = LLAMADAS[proveedor](PROMPT_PRUEBA)
        except ErrorIA as error:
            self.stdout.write(self.style.ERROR(f'  [FALLA] {error}'))
            return False

        faltantes = [c for c in CAMPOS_ESPERADOS if c not in respuesta]
        if faltantes:
            self.stdout.write(self.style.WARNING(
                f'  [AVISO] Respondió, pero la respuesta no trae: {", ".join(faltantes)}.'))
        else:
            self.stdout.write(self.style.SUCCESS('  [OK]    El JSON estructurado llegó completo.'))
            self.stdout.write(f'          Respuesta: {respuesta["diagnostico"]}')
        return True

    def _probar_contexto(self, codigo):
        """Verifica que haya una piscina con lecturas para analizar."""
        self.stdout.write('')
        piscinas = Geomembrana.objects.all()
        if codigo:
            piscinas = piscinas.filter(codigo_identificacion=codigo.upper())

        piscina = piscinas.first()
        if piscina is None:
            self.stdout.write(self.style.WARNING(
                '  [AVISO] No hay geomembranas registradas: no se puede probar '
                'el contexto de análisis.'))
            return

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
