import '../../../core/network/api_client.dart';
import '../../../core/network/api_response.dart';
import 'prediction.dart';

class PredictionsRepository {
  PredictionsRepository(this._api);

  final ApiClient _api;

  /// Predicciones vigentes (pendientes de evaluar) de una geomembrana.
  Future<List<Prediction>> fetchPredictions(int pondId) async {
    final body = await _api.get(
      '/predicciones/',
      query: {'geomembrana': pondId, 'estado': 'pendiente'},
    );
    return unwrapList(body).map(Prediction.fromJson).toList();
  }
}
