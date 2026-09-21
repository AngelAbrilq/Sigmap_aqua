"""
RF019: reenvio de lecturas encoladas offline sin duplicar (dedup por sensor+timestamp).
"""
import json

from apps.monitoreo.models import Lectura

from .base import BaseSigmap


class IngestaOfflineDedupTest(BaseSigmap):

    def _post_lote(self, lecturas):
        return self.client.post(
            '/api/v1/lecturas/',
            {'lecturas': lecturas}, content_type='application/json',
            **self.cabecera_dispositivo(),
        )

    def test_reenvio_no_duplica_por_timestamp(self):
        lote = [{'codigo_hardware': 'SEN-PH', 'valor': '7.0',
                 'timestamp': '2026-09-20T10:00:00-05:00'}]

        r1 = self._post_lote(lote)
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r1.json()['data']['registradas'], 1)

        # El nodo reenvia la MISMA lectura encolada: no debe duplicarse.
        r2 = self._post_lote(lote)
        self.assertEqual(r2.status_code, 201)
        d2 = r2.json()['data']
        self.assertEqual(d2['registradas'], 0)
        self.assertEqual(d2['duplicadas'], 1)

        self.assertEqual(Lectura.objects.filter(sensor=self.sensor_ph).count(), 1)

    def test_lecturas_en_vivo_sin_timestamp_siempre_entran(self):
        # Sin timestamp = lectura en vivo: dos envios cuentan como dos lecturas.
        self._post_lote([{'codigo_hardware': 'SEN-PH', 'valor': '7.0'}])
        self._post_lote([{'codigo_hardware': 'SEN-PH', 'valor': '7.1'}])
        self.assertEqual(Lectura.objects.filter(sensor=self.sensor_ph).count(), 2)
