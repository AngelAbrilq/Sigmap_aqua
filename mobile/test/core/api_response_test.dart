import 'package:flutter_test/flutter_test.dart';
import 'package:sigmap_aqua_mobile/core/network/api_exception.dart';
import 'package:sigmap_aqua_mobile/core/network/api_response.dart';

void main() {
  group('unwrapData', () {
    test('extrae data de una respuesta envuelta', () {
      // Arrange
      final body = {'success': true, 'data': {'id': 1}, 'message': 'ok'};

      // Act
      final data = unwrapData(body);

      // Assert
      expect(data, {'id': 1});
    });

    test('devuelve el cuerpo tal cual si no viene envuelto (SimpleJWT)', () {
      final body = {'access': 'a', 'refresh': 'r'};

      expect(unwrapData(body), body);
    });

    test('lanza ApiException con el mensaje del servidor si success es false', () {
      final body = {'success': false, 'data': null, 'message': 'Sin permiso'};

      expect(
        () => unwrapData(body),
        throwsA(isA<ApiException>().having((e) => e.message, 'message', 'Sin permiso')),
      );
    });
  });

  group('unwrapList', () {
    test('lee resultados paginados de DRF', () {
      final body = {
        'success': true,
        'data': {
          'count': 2,
          'results': [
            {'id': 1},
            {'id': 2},
          ],
        },
      };

      expect(unwrapList(body).map((item) => item['id']), [1, 2]);
      expect(unwrapCount(body), 2);
    });

    test('lee la paginación de la API móvil (total/resultados)', () {
      final body = {
        'success': true,
        'data': {
          'total': 41,
          'pagina': 1,
          'paginas': 3,
          'resultados': [
            {'id': 1},
          ],
        },
      };

      expect(unwrapList(body).single['id'], 1);
      expect(unwrapCount(body), 41);
    });

    test('acepta una lista simple', () {
      final body = {
        'success': true,
        'data': [
          {'id': 7},
        ],
      };

      expect(unwrapList(body).single['id'], 7);
      expect(unwrapCount(body), 1);
    });

    test('lanza error si el formato no es una lista (caso borde)', () {
      expect(
        () => unwrapList({'success': true, 'data': 'texto'}),
        throwsA(isA<ApiException>()),
      );
    });
  });
}
