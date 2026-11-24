"""
Camara del nodo ESP32 (RF027): POST /api/v1/capturas/ y su foto en el tablero.

Las imagenes se guardan en una carpeta temporal para no ensuciar media/.
"""
import io
import shutil
import tempfile

from django.test import override_settings
from PIL import Image

from apps.monitoreo.models import CapturaCamara

from .base import BaseSigmap

MEDIA_TEMPORAL = tempfile.mkdtemp(prefix='sigmap_test_media_')
URL = '/api/v1/capturas/'


def jpeg_de_prueba(ancho=160, alto=120):
    """JPEG real del tamaño que manda la OV7670 (QQVGA)."""
    buffer = io.BytesIO()
    Image.new('RGB', (ancho, alto), (30, 120, 90)).save(buffer, format='JPEG', quality=70)
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class IngestaCapturaTest(BaseSigmap):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)

    def enviar(self, contenido, tipo='image/jpeg', token=None, **extra):
        return self.client.generic('POST', URL, contenido, content_type=tipo,
                                   **self.cabecera_dispositivo(token), **extra)

    def test_jpeg_valido_se_guarda_con_su_piscina(self):
        """Camino feliz: la foto queda asociada al nodo y a su geomembrana."""
        respuesta = self.enviar(jpeg_de_prueba(), HTTP_X_MOTIVO='alerta')

        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(respuesta.json()['success'])
        captura = CapturaCamara.objects.get()
        self.assertEqual(captura.geomembrana, self.piscina)
        self.assertEqual(captura.motivo, 'alerta')
        self.assertEqual((captura.ancho, captura.alto), (160, 120))
        self.assertTrue(captura.imagen.name.endswith('.jpg'))

    def test_sin_token_devuelve_401(self):
        """Caso de error: nadie sin token puede subir imagenes."""
        respuesta = self.client.generic('POST', URL, jpeg_de_prueba(), content_type='image/jpeg')
        self.assertEqual(respuesta.status_code, 401)
        self.assertFalse(CapturaCamara.objects.exists())

    def test_bytes_que_no_son_jpeg_se_rechazan(self):
        """Caso de error: un archivo cualquiera con Content-Type de imagen."""
        respuesta = self.enviar(b'\xff\xd8esto no es una imagen')
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['data']['campo'], 'imagen')
        self.assertFalse(CapturaCamara.objects.exists())

    def test_content_type_distinto_devuelve_415(self):
        """Caso limite: el nodo debe mandar image/jpeg."""
        respuesta = self.enviar(jpeg_de_prueba(), tipo='application/octet-stream')
        self.assertEqual(respuesta.status_code, 415)

    def test_motivo_desconocido_queda_como_periodica(self):
        """Caso limite: un header raro no rompe la ingesta."""
        self.enviar(jpeg_de_prueba(), HTTP_X_MOTIVO='<script>')
        self.assertEqual(CapturaCamara.objects.get().motivo, 'periodica')

    def test_el_tablero_recibe_la_ultima_foto(self):
        """El JSON del monitoreo trae la URL de la foto mas reciente."""
        self.enviar(jpeg_de_prueba())
        self.client.force_login(self.instructor)
        respuesta = self.client.get(f'/monitoreo/api/{self.piscina.pk}/estado/')
        camara = respuesta.json()['data']['camara']
        self.assertIsNotNone(camara)
        self.assertEqual(camara['url'], CapturaCamara.objects.get().imagen.url)

    def test_tablero_sin_fotos_muestra_espera_y_no_video(self):
        """Sin capturas no se carga el video del prototipo: se ve el aviso de espera."""
        self.client.force_login(self.instructor)
        html = self.client.get(f'/monitoreo/?piscina={self.piscina.pk}').content.decode()
        self.assertIn('id="camaraVacia"', html)
        self.assertNotIn('<video', html)

    def test_tablero_con_foto_muestra_la_imagen(self):
        """Con capturas, la seccion de camara muestra la ultima foto real."""
        self.enviar(jpeg_de_prueba())
        self.client.force_login(self.instructor)
        html = self.client.get(f'/monitoreo/?piscina={self.piscina.pk}').content.decode()
        self.assertIn(CapturaCamara.objects.get().imagen.url, html)
        self.assertNotIn('id="camaraVacia"', html)
