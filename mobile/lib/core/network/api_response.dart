import 'api_exception.dart';

/// Utilidades para leer el formato estándar del backend:
/// `{ "success": bool, "data": ..., "message": str }`.
///
/// Si el cuerpo no viene envuelto (p. ej. las vistas nativas de SimpleJWT
/// como `auth/refresh/`), se devuelve tal cual.
Object? unwrapData(Object? body) {
  if (body is Map && body.containsKey('success')) {
    if (body['success'] != true) {
      throw ApiException('${body['message'] ?? 'La operación no fue exitosa.'}');
    }
    return body['data'];
  }
  return body;
}

/// Devuelve `data` como mapa o lanza [ApiException] si el formato no coincide.
Map<String, dynamic> unwrapMap(Object? body) {
  final data = unwrapData(body);
  if (data is! Map) {
    throw const ApiException('Formato de respuesta inesperado del servidor.');
  }
  return Map<String, dynamic>.from(data);
}

/// Devuelve la lista de resultados, venga paginada por la API móvil
/// (`{total, pagina, paginas, resultados}`), por DRF estándar
/// (`{count, results}`) o como lista simple.
List<Map<String, dynamic>> unwrapList(Object? body) {
  final data = unwrapData(body);
  final items = data is Map ? (data['resultados'] ?? data['results']) : data;
  if (items is! List) {
    throw const ApiException('Formato de respuesta inesperado del servidor.');
  }
  return items
      .whereType<Map>()
      .map((item) => Map<String, dynamic>.from(item))
      .toList();
}

/// Total de registros de una respuesta paginada; si no viene paginada,
/// cuenta los elementos de la lista.
int unwrapCount(Object? body) {
  final data = unwrapData(body);
  if (data is Map) {
    final total = data['total'] ?? data['count'];
    if (total is int) return total;
  }
  return unwrapList(body).length;
}
