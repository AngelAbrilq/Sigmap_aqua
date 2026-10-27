"""
Genera los tres QR de demostración como PNG (imprimir) y SVG (diapositivas).

Uso:
    python manage.py generar_qrs_demo --url https://g8lnb4b3-8000.use.devtunnels.ms
    python manage.py generar_qrs_demo                    # usa DEMO_QR_URL_BASE del .env
    python manage.py generar_qrs_demo --salida C:/QRs --escala 28

Cada ejecución firma tokens nuevos con DEMO_QR_HORAS de vigencia.
"""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.demo.qr import qr_png, qr_svg
from apps.demo.roles import ORDEN_ROLES, ROLES_DEMO, usuario_demo
from apps.demo.tokens import vigencia_segundos
from apps.demo.views import enlace_acceso


class Command(BaseCommand):
    help = 'Genera los QR de acceso por rol (PNG y SVG) para la sustentación.'

    def add_arguments(self, parser):
        parser.add_argument('--url', default='', help='URL pública del sistema (ej. la del túnel).')
        parser.add_argument('--salida', default='', help='Carpeta de salida (def. media/demo_qr).')
        parser.add_argument('--escala', type=int, default=24, help='Píxeles por módulo del PNG (def. 24).')

    def handle(self, *args, **opciones):
        base = (opciones['url'] or settings.DEMO_QR_URL_BASE).strip().rstrip('/')
        if not base.startswith(('http://', 'https://')):
            raise CommandError('Indica la URL pública con --url https://... o DEMO_QR_URL_BASE en el .env')
        if opciones['escala'] < 8:
            raise CommandError('--escala debe ser al menos 8 para que el QR se imprima nítido.')

        salida = Path(opciones['salida'] or Path(settings.MEDIA_ROOT) / 'demo_qr')
        salida.mkdir(parents=True, exist_ok=True)

        if not settings.DEMO_QR_ACTIVO:
            self.stdout.write(self.style.WARNING(
                'Aviso: DEMO_QR_ACTIVO=False. Los QR se generan, pero no abrirán nada '
                'hasta que pongas DEMO_QR_ACTIVO=True en el .env y reinicies el servidor.\n'))

        generados = 0
        for nombre_rol in ORDEN_ROLES:
            rol = ROLES_DEMO[nombre_rol]
            usuario = usuario_demo(nombre_rol)
            if usuario is None:
                self.stdout.write(self.style.ERROR(f'  {rol["titulo"]}: no hay usuario activo con este rol, se omite.'))
                continue

            enlace = enlace_acceso(base, usuario)
            ruta_png = salida / f'qr_{rol["slug"]}.png'
            ruta_svg = salida / f'qr_{rol["slug"]}.svg'
            qr_png(enlace, rol['color'], rol['color2'], ruta_png, escala=opciones['escala'])
            ruta_svg.write_text(
                qr_svg(enlace, rol['color'], rol['color2'], uid=f'qr-{rol["slug"]}',
                       titulo=f'Acceso como {rol["titulo"]}'),
                encoding='utf-8')
            generados += 1
            self.stdout.write(self.style.SUCCESS(f'  {rol["icono"]} {rol["titulo"]} -> {usuario.email}'))
            self.stdout.write(f'     {ruta_png}')

        vence = timezone.localtime() + timedelta(seconds=vigencia_segundos())
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n{generados} QR generados en {salida}\nVencen: {vence:%d/%m/%Y %H:%M}\n'))
