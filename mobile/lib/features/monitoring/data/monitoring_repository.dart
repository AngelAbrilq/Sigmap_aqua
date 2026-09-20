import 'package:intl/intl.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_response.dart';
import 'reading.dart';

class MonitoringRepository {
  MonitoringRepository(this._api);

  static final _apiDate = DateFormat('yyyy-MM-dd');

  /// Máximo de puntos que se piden para una gráfica.
  static const historyLimit = 500;

  final ApiClient _api;

  /// Última lectura de cada parámetro que mide la geomembrana, incluidos
  /// los sensores sin datos (`estado_lectura: sin_datos`).
  Future<List<Reading>> fetchLatestReadings(int pondId) async {
    final body = await _api.get('/geomembranas/$pondId/ultimas-lecturas/');
    final parameters = unwrapMap(body)['parametros'];
    if (parameters is! List) return const [];
    return parameters
        .whereType<Map>()
        .map((item) => Reading.fromJson(Map<String, dynamic>.from(item)))
        .toList();
  }

  /// Historial de un parámetro, ordenado del más antiguo al más reciente.
  Future<List<Reading>> fetchHistory({
    required int pondId,
    required int parameterId,
    required DateTime from,
    required DateTime to,
  }) async {
    final body = await _api.get('/lecturas/', query: {
      'geomembrana': pondId,
      'parametro': parameterId,
      'desde': _apiDate.format(from),
      'hasta': _apiDate.format(to),
      'page_size': historyLimit,
    });
    final readings = unwrapList(body)
        .map(Reading.fromJson)
        .where((reading) => reading.hasValue)
        .toList()
      ..sort((a, b) => a.timestamp!.compareTo(b.timestamp!));
    return readings;
  }
}
