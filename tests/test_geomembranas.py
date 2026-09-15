"""
CRUD de geomembranas: la entidad raiz del sistema.

Sin geomembrana no existen sensores, dispositivos, lecturas ni alertas: todas
la referencian con on_delete=PROTECT.
"""
from decimal import Decimal

from apps.piscinas.models import Geomembrana

from .base import BaseSigmap


class CrearGeomembranaTest(BaseSigmap):
    """Alta de geomembranas y sus reglas de negocio."""

    def setUp(self):
        self.client.force_login(self.operario)
        self.datos = {
            'nombre_piscina': 'Estanque Norte', 'codigo_identificacion': 'geo-001',
            'descripcion': '', 'ubicacion': 'Lote norte',
            'area_m2': '2500.00', 'profundidad_promedio': '1.80',
            'volumen_agua_m3': '', 'capacidad_maxima_peces': '12000',
            'etapa_actual': self.etapa.pk, 'material': 'HDPE',
            'espesor_mm': '1.50', 'proveedor': 'GeoLáminas S.A.S.',
            'garantia_anios': '8', 'vida_util_anios': '10',
            'fecha_instalacion': '2024-03-15', 'fecha_ultimo_mantenimiento': '',
            'apta_para_produccion': 'on', 'estado': 'activo',
        }

    def test_camino_feliz_crea_la_geomembrana(self):
        """Con datos validos, la geomembrana se persiste."""
        # Arrange: self.datos ya tiene un alta valida
        # Act
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        # Assert
        self.assertTrue(Geomembrana.objects.filter(codigo_identificacion='GEO-001').exists())

    def test_normaliza_el_codigo_a_mayusculas(self):
        """El codigo se guarda en mayusculas aunque se escriba en minusculas."""
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        creada = Geomembrana.objects.get(codigo_identificacion='GEO-001')
        self.assertEqual(creada.codigo_identificacion, 'GEO-001')

    def test_calcula_el_volumen_si_se_deja_vacio(self):
        """Volumen = area x profundidad cuando el usuario no lo escribe."""
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        creada = Geomembrana.objects.get(codigo_identificacion='GEO-001')
        self.assertEqual(creada.volumen_agua_m3, Decimal('4500.00'))

    def test_rechaza_codigo_duplicado(self):
        """Caso de error: el codigo es unico."""
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        self.assertEqual(
            Geomembrana.objects.filter(codigo_identificacion='GEO-001').count(), 1)

    def test_rechaza_garantia_mayor_que_vida_util(self):
        """Caso limite: la garantia del fabricante no puede exceder la vida util."""
        self.datos.update(codigo_identificacion='GEO-BAD', garantia_anios='12')
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        self.assertFalse(Geomembrana.objects.filter(codigo_identificacion='GEO-BAD').exists())

    def test_rechaza_apta_con_estado_mantenimiento(self):
        """Caso limite: una piscina en mantenimiento no puede estar apta."""
        self.datos.update(codigo_identificacion='GEO-BAD2', estado='mantenimiento')
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        self.assertFalse(Geomembrana.objects.filter(codigo_identificacion='GEO-BAD2').exists())

    def test_rechaza_volumen_incoherente_con_la_geometria(self):
        """Caso limite: el volumen declarado se aparta mas de 20 % del teorico."""
        self.datos.update(codigo_identificacion='GEO-BAD3', volumen_agua_m3='9000')
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        self.assertFalse(Geomembrana.objects.filter(codigo_identificacion='GEO-BAD3').exists())

    def test_rechaza_capacidad_por_encima_de_la_densidad_de_la_etapa(self):
        """Caso limite: 2500 m2 x 8 peces/m2 = 20 000 peces como maximo."""
        self.datos.update(codigo_identificacion='GEO-BAD4', capacidad_maxima_peces='30000')
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        self.assertFalse(Geomembrana.objects.filter(codigo_identificacion='GEO-BAD4').exists())

    def test_rechaza_fecha_de_instalacion_futura(self):
        """Caso de error: no se puede instalar algo en el futuro."""
        self.datos.update(codigo_identificacion='GEO-BAD5', fecha_instalacion='2099-01-01')
        self.client.post('/geomembranas/crear/', self.datos, follow=True)
        self.assertFalse(Geomembrana.objects.filter(codigo_identificacion='GEO-BAD5').exists())


class LeerYEditarGeomembranaTest(BaseSigmap):
    """Lectura del listado y actualizacion."""

    def setUp(self):
        self.client.force_login(self.operario)

    def test_el_listado_muestra_las_piscinas_de_la_base_de_datos(self):
        """READ: el HTML sale de la BD, no de un array en JavaScript."""
        respuesta = self.client.get('/geomembranas/')
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Estanque de Prueba')

    def test_el_listado_no_contiene_el_array_de_datos_ficticios(self):
        """
        Regresion: el template ya no trae `geomembranasData`, el array de
        JavaScript con cuatro piscinas inventadas que se pintaba en lugar de
        consultar la base de datos.

        Se buscan las claves de aquel array, no los textos sueltos: frases
        como 'GeoLáminas S.A.S.' siguen apareciendo legítimamente como
        placeholder del formulario.
        """
        respuesta = self.client.get('/geomembranas/')
        for rastro in ('geomembranasData', 'vidaRestante', 'ultimaInspec',
                       'proximaDias', 'statusClass'):
            with self.subTest(rastro=rastro):
                self.assertNotContains(respuesta, rastro)

    def test_el_listado_refleja_el_contenido_real_de_la_tabla(self):
        """Si la tabla cambia, la pantalla cambia. Antes no ocurria."""
        Geomembrana.objects.filter(pk=self.piscina.pk).update(
            nombre_piscina='Nombre Cambiado En La Base')
        respuesta = self.client.get('/geomembranas/')
        self.assertContains(respuesta, 'Nombre Cambiado En La Base')

    def test_actualiza_el_nombre(self):
        """UPDATE: los cambios se persisten."""
        self.client.post(f'/geomembranas/{self.piscina.pk}/editar/', {
            'nombre_piscina': 'Estanque Renombrado',
            'codigo_identificacion': 'GEO-TEST',
            'descripcion': '', 'ubicacion': '',
            'area_m2': '2500.00', 'profundidad_promedio': '1.80',
            'volumen_agua_m3': '4500.00', 'capacidad_maxima_peces': '12000',
            'etapa_actual': self.etapa.pk, 'material': 'HDPE',
            'espesor_mm': '1.50', 'proveedor': '', 'garantia_anios': '8',
            'vida_util_anios': '10', 'fecha_instalacion': '2024-03-15',
            'fecha_ultimo_mantenimiento': '', 'apta_para_produccion': 'on',
            'estado': 'activo',
        }, follow=True)
        self.piscina.refresh_from_db()
        self.assertEqual(self.piscina.nombre_piscina, 'Estanque Renombrado')


class BorradoProtegidoTest(BaseSigmap):
    """El borrado nunca destruye la trazabilidad del cultivo."""

    def setUp(self):
        self.client.force_login(self.instructor)

    def test_con_dependencias_se_desactiva_en_lugar_de_borrarse(self):
        """La piscina de prueba tiene sensores: no puede borrarse."""
        self.client.post(f'/geomembranas/{self.piscina.pk}/eliminar/', follow=True)
        self.piscina.refresh_from_db()
        self.assertTrue(Geomembrana.objects.filter(pk=self.piscina.pk).exists())
        self.assertEqual(self.piscina.estado, 'inactivo')

    def test_sin_dependencias_si_se_borra(self):
        """Camino feliz del borrado: una ficha virgen si desaparece."""
        vacia = Geomembrana.objects.create(
            nombre_piscina='Vacía', codigo_identificacion='GEO-VACIA')
        self.client.post(f'/geomembranas/{vacia.pk}/eliminar/', follow=True)
        self.assertFalse(Geomembrana.objects.filter(pk=vacia.pk).exists())


class LogicaDeNegocioGeomembranaTest(BaseSigmap):
    """Propiedades calculadas del modelo, sin pasar por HTTP."""

    def test_vida_util_restante_se_calcula_por_desgaste_lineal(self):
        """
        El porcentaje corresponde al tiempo que le queda por consumir.

        Se calcula contra la fecha real de hoy, así que la prueba compara
        contra la fórmula en vez de contra un número fijo que caducaría.
        """
        from django.utils import timezone

        anios_servicio = (timezone.localdate() - self.piscina.fecha_instalacion).days / 365.25
        esperado = round((1 - anios_servicio / 10) * 100)

        self.assertEqual(self.piscina.vida_util_restante_pct, esperado)

    def test_la_vida_util_nunca_sale_del_rango_0_100(self):
        """Caso limite: una lámina que superó su vida útil no da un negativo."""
        from datetime import date

        self.piscina.fecha_instalacion = date(1990, 1, 1)
        self.assertEqual(self.piscina.vida_util_restante_pct, 0)

    def test_sin_vida_util_declarada_no_se_inventa_un_porcentaje(self):
        """Caso limite: sin el dato, la propiedad devuelve None, no un cero."""
        self.piscina.vida_util_anios = None
        self.assertIsNone(self.piscina.vida_util_restante_pct)

    def test_el_semaforo_es_critico_si_la_piscina_esta_inactiva(self):
        """Una piscina dada de baja nunca aparece en verde."""
        self.piscina.estado = 'inactivo'
        self.assertEqual(self.piscina.estado_operativo, 'crit')

    def test_el_semaforo_es_atencion_en_mantenimiento(self):
        """Caso limite entre verde y rojo."""
        self.piscina.estado = 'mantenimiento'
        self.assertEqual(self.piscina.estado_operativo, 'warn')

    def test_cuenta_las_dependencias_que_bloquean_el_borrado(self):
        """dependencias() alimenta la decision de borrar o desactivar."""
        dependencias = self.piscina.dependencias
        self.assertEqual(dependencias['sensores'], 2)
        self.assertEqual(dependencias['dispositivos'], 1)
        self.assertTrue(self.piscina.tiene_dependencias)
