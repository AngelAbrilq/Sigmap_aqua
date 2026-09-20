import '../../../core/network/api_client.dart';
import '../../../core/network/api_response.dart';
import 'pond.dart';

class PondsRepository {
  PondsRepository(this._api);

  final ApiClient _api;

  /// MVP: una sola página grande. Un proyecto formativo tiene pocas
  /// geomembranas; si crecen, paginar con scroll infinito.
  Future<List<Pond>> fetchPonds() async {
    final body = await _api.get('/geomembranas/', query: {'page_size': 100});
    return unwrapList(body).map(Pond.fromJson).toList();
  }

  Future<Pond> fetchPond(int pondId) async =>
      Pond.fromJson(unwrapMap(await _api.get('/geomembranas/$pondId/')));
}
