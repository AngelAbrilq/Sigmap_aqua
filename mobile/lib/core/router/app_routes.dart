/// Rutas de la app en un solo lugar (sin strings repetidos en los widgets).
abstract final class AppRoutes {
  static const splash = '/splash';
  static const login = '/login';
  static const ponds = '/geomembranas';
  static const alerts = '/alertas';
  static const profile = '/perfil';

  static String pondDetail(int pondId) => '$ponds/$pondId';

  static String pondHistory(int pondId, {int? parameterId}) =>
      Uri(
        path: '$ponds/$pondId/historial',
        queryParameters:
            parameterId == null ? null : {'parametro': '$parameterId'},
      ).toString();
}
