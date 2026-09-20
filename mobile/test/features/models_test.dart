import 'package:flutter_test/flutter_test.dart';
import 'package:sigmap_aqua_mobile/features/alerts/data/alert.dart';
import 'package:sigmap_aqua_mobile/features/auth/data/app_user.dart';
import 'package:sigmap_aqua_mobile/features/monitoring/data/reading.dart';

void main() {
  group('AppUser', () {
    test('"todos" da acceso total (Instructor Líder)', () {
      final user = AppUser.fromJson({
        'id': 1,
        'email': 'lider@sena.edu.co',
        'nombre_completo': 'Ana María Rojas',
        'rol': 'Instructor Lider',
        'modulos': {'lectura': 'todos', 'escritura': 'todos'},
      });

      expect(user.canView('alertas'), isTrue);
      expect(user.canEdit('alertas'), isTrue);
      expect(user.initials, 'AM');
    });

    test('el Aprendiz ve alertas pero no puede resolverlas', () {
      final user = AppUser.fromJson({
        'id': 2,
        'nombre_completo': 'Pedro',
        'rol': 'Aprendiz',
        'modulos': {
          'lectura': ['alertas', 'monitoreo'],
          'escritura': <String>[],
        },
      });

      expect(user.canView('alertas'), isTrue);
      expect(user.canEdit('alertas'), isFalse);
    });

    test('si faltan los módulos se niega el acceso (falla segura)', () {
      final user = AppUser.fromJson({'id': 3, 'rol': 'Operario'});

      expect(user.canView('geomembranas'), isFalse);
      expect(user.canEdit('geomembranas'), isFalse);
    });
  });

  group('Reading', () {
    test('convierte el Decimal de DRF (texto) a double', () {
      final reading = Reading.fromJson({
        'id': 10,
        'parametro_id': 2,
        'parametro': 'pH',
        'unidad': '',
        'valor_medida': '7.2500',
        'estado_lectura': 'riesgo',
        'timestamp_lectura': '2026-09-17T10:00:00-0500',
        'rango_min': '6.5000',
        'rango_max': '8.5000',
      });

      expect(reading.value, 7.25);
      expect(reading.status, ReadingStatus.warning);
      expect(reading.normalMax, 8.5);
    });

    test('un sensor sin lecturas llega como "Sin datos" (caso borde)', () {
      final reading = Reading.fromJson({
        'parametro_id': 3,
        'parametro': 'Turbidez',
        'valor_medida': null,
        'estado_lectura': 'sin_datos',
        'timestamp_lectura': null,
      });

      expect(reading.value, isNull);
      expect(reading.hasValue, isFalse);
      expect(reading.status, ReadingStatus.noData);
    });

    test('un estado desconocido no rompe el parseo', () {
      final reading = Reading.fromJson({'valor_medida': 'abc', 'estado_lectura': 'x'});

      expect(reading.value, isNull);
      expect(reading.status, ReadingStatus.unknown);
    });
  });

  group('Alert', () {
    test('una alerta reconocida se puede resolver pero no reconocer', () {
      final alert = Alert.fromJson({
        'id': 5,
        'geomembrana': 1,
        'piscina': 'Estanque 1',
        'tipo_alerta': 'critico',
        'severidad': 'critica',
        'estado': 'reconocida',
        'mensaje_alerta': 'Oxígeno disuelto bajo',
        'fecha_generacion': '2026-09-17T10:00:00-0500',
      });

      expect(alert.canBeAcknowledged, isFalse);
      expect(alert.canBeResolved, isTrue);
      expect(alert.severity, AlertSeverity.critical);
      expect(alert.pondId, 1);
      expect(alert.pondName, 'Estanque 1');
    });
  });
}
