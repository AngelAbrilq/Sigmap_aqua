"""
Integridad de los templates.

Estas pruebas atrapan una familia de errores que Django NO reporta: sintaxis
de plantilla mal escrita que no lanza excepcion, simplemente se imprime como
texto en la pagina. El sistema "funciona", los tests de logica pasan, y el
usuario ve codigo crudo en pantalla.
"""
import pathlib
import re

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from .base import BaseSigmap

# Rutas que renderizan una pagina completa con el layout base.
PAGINAS = [
    'core:dashboard', 'piscinas:listar', 'monitoreo:sensores',
    'monitoreo:monitoreo', 'monitoreo:historial', 'monitoreo:configuraciones',
    'reportes:graficas', 'reportes:comparacion', 'alertas:listar',
    'ia:panel', 'usuarios:listar',
]


def _directorios_de_templates():
    """Devuelve los directorios de plantillas configurados en settings."""
    for motor in settings.TEMPLATES:
        for ruta in motor.get('DIRS', []):
            yield pathlib.Path(ruta)


class SintaxisDeComentariosTest(SimpleTestCase):
    """
    `{# ... #}` comenta UNA sola linea.

    Si abarca varias, Django no lo trata como comentario: lo imprime literal
    en el HTML. Para bloques hay que usar {% comment %} ... {% endcomment %}.
    """

    def test_ningun_comentario_de_almohadilla_abarca_varias_lineas(self):
        """Regresion: el sidebar mostraba su propio comentario en pantalla."""
        infractores = []
        for carpeta in _directorios_de_templates():
            for archivo in carpeta.rglob('*.html'):
                contenido = archivo.read_text(encoding='utf-8', errors='replace')
                for hallazgo in re.finditer(r'\{#(.*?)#\}', contenido, re.DOTALL):
                    if '\n' in hallazgo.group(1):
                        linea = contenido[:hallazgo.start()].count('\n') + 1
                        infractores.append(f'{archivo.name}:{linea}')

        self.assertEqual(
            infractores, [],
            'Comentarios {# #} de varias líneas (Django los imprime como texto). '
            'Usa {% comment %}...{% endcomment %}: ' + ', '.join(infractores))

    def test_las_llaves_de_comentario_estan_balanceadas(self):
        """Un `{#` sin su `#}` se come el resto de la plantilla."""
        desbalanceados = []
        for carpeta in _directorios_de_templates():
            for archivo in carpeta.rglob('*.html'):
                contenido = archivo.read_text(encoding='utf-8', errors='replace')
                if contenido.count('{#') != contenido.count('#}'):
                    desbalanceados.append(archivo.name)

        self.assertEqual(desbalanceados, [], f'Sin balancear: {desbalanceados}')

    def test_los_bloques_comment_cierran(self):
        """Cada {% comment %} necesita su {% endcomment %}."""
        desbalanceados = []
        for carpeta in _directorios_de_templates():
            for archivo in carpeta.rglob('*.html'):
                contenido = archivo.read_text(encoding='utf-8', errors='replace')
                aperturas = len(re.findall(r'\{%\s*comment\s*%\}', contenido))
                cierres = len(re.findall(r'\{%\s*endcomment\s*%\}', contenido))
                if aperturas != cierres:
                    desbalanceados.append(f'{archivo.name} ({aperturas}/{cierres})')

        self.assertEqual(desbalanceados, [], f'Sin cerrar: {desbalanceados}')


class SinFugasEnElHtmlTest(BaseSigmap):
    """
    Ninguna pagina debe entregar sintaxis de plantilla sin procesar.

    Se renderiza cada modulo de verdad y se inspecciona el HTML resultante:
    es la unica forma de detectar lo que el motor no considera un error.
    """

    def setUp(self):
        self.client.force_login(self.instructor)

    def test_ninguna_pagina_filtra_comentarios_de_plantilla(self):
        """Regresion directa del bug del sidebar."""
        for nombre in PAGINAS:
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(nombre), follow=True)
                html = respuesta.content.decode('utf-8', errors='replace')
                self.assertNotIn('{#', html)
                self.assertNotIn('#}', html)

    def test_ninguna_pagina_filtra_etiquetas_sin_procesar(self):
        """
        Un `{% url ... %}` mal escrito o un `{{ variable }}` fuera de bloque
        se imprimen literalmente.

        Se excluyen los bloques <script type="application/json">, donde las
        llaves dobles son JSON legitimo.
        """
        patron_json = re.compile(
            r'<script[^>]*type="application/json"[^>]*>.*?</script>', re.DOTALL)

        for nombre in PAGINAS:
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(nombre), follow=True)
                html = patron_json.sub('', respuesta.content.decode('utf-8', 'replace'))
                self.assertNotIn('{%', html)
                self.assertNotIn('%}', html)

    def test_el_sidebar_se_renderiza_dentro_del_contenedor(self):
        """
        El <aside> debe ser el primer elemento de .app-container.

        Cualquier texto suelto antes de el se convierte en un item flex
        anonimo y empuja el menu fuera de su sitio: eso es lo que hacia que
        el sidebar apareciera a la derecha.
        """
        respuesta = self.client.get(reverse('core:dashboard'), follow=True)
        html = respuesta.content.decode('utf-8', errors='replace')

        inicio_contenedor = html.index('class="app-container"')
        inicio_aside = html.index('<aside', inicio_contenedor)
        entre_medias = html[html.index('>', inicio_contenedor) + 1:inicio_aside]

        self.assertEqual(
            entre_medias.strip(), '',
            f'Hay contenido suelto entre .app-container y <aside>: '
            f'{entre_medias.strip()[:200]!r}')


class EnlacesDelSidebarTest(BaseSigmap):
    """Cada enlace que el sidebar pinta debe llevar a una pagina viva."""

    def _enlaces(self, usuario):
        """
        Extrae los href del <aside> tal como los ve ese usuario.

        :param usuario: instancia de Usuario con la que iniciar sesion
        :return: list de rutas
        """
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('core:dashboard'), follow=True)
        html = respuesta.content.decode('utf-8', errors='replace')
        aside = html[html.index('<aside'):html.index('</aside>')]
        return re.findall(r'href="([^"]+)"', aside)

    def test_los_enlaces_del_instructor_responden_200(self):
        """Camino feliz: ningun enlace muerto para el rol con acceso total."""
        for ruta in self._enlaces(self.instructor):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta, follow=True).status_code, 200)

    def test_el_sidebar_no_ofrece_modulos_vedados_al_operario(self):
        """El Operario no debe ver el enlace a gestion de usuarios."""
        self.assertNotIn(reverse('usuarios:listar'), self._enlaces(self.operario))

    def test_el_sidebar_no_ofrece_modulos_vedados_al_aprendiz(self):
        """El Aprendiz tampoco administra cuentas."""
        self.assertNotIn(reverse('usuarios:listar'), self._enlaces(self.aprendiz))

    def test_ningun_enlace_del_sidebar_queda_vacio(self):
        """
        Caso limite: un {% url %} que falla en silencio deja href="".

        Un enlace vacio recarga la misma pagina y parece que el menu no
        funciona, sin que aparezca ningun error.
        """
        for ruta in self._enlaces(self.instructor):
            with self.subTest(ruta=ruta):
                self.assertNotEqual(ruta.strip(), '')
                self.assertNotEqual(ruta.strip(), '#')
