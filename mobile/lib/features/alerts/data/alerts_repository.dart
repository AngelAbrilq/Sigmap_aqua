import '../../../core/network/api_client.dart';
import '../../../core/network/api_response.dart';
import 'alert.dart';

class AlertsRepository {
  AlertsRepository(this._api);

  final ApiClient _api;

  Future<List<Alert>> fetchAlerts({required AlertStatus status}) async {
    final body = await _api.get(
      '/alertas/',
      query: {'estado': status.apiValue, 'page_size': 100},
    );
    return unwrapList(body).map(Alert.fromJson).toList();
  }

  /// Total de alertas activas, para el badge de la navegación.
  Future<int> countActive() async {
    final body = await _api.get(
      '/alertas/',
      query: {'estado': AlertStatus.active.apiValue, 'page_size': 1},
    );
    return unwrapCount(body);
  }

  Future<void> acknowledge(int alertId) =>
      _api.post('/alertas/$alertId/reconocer/');

  Future<void> resolve(int alertId, {required String actionTaken}) => _api.post(
        '/alertas/$alertId/resolver/',
        data: {'accion_tomada': actionTaken.trim()},
      );
}
