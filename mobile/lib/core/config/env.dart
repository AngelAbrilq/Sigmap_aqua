/// Configuración inyectada al compilar con `--dart-define` o
/// `--dart-define-from-file=dart_defines.local.json`.
abstract final class Env {
  /// URL base de la API móvil de Django.
  ///
  /// El valor por defecto apunta al PC anfitrión visto desde el emulador de
  /// Android (10.0.2.2). En un celular físico usa la IP LAN del PC.
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1/movil',
  );

  /// Cada cuánto se refrescan las lecturas en pantalla. Los sensores reportan
  /// cada ~300 s, así que bajar de 30 s no aporta datos nuevos.
  static const Duration pollingInterval = Duration(
    seconds: int.fromEnvironment('POLLING_SECONDS', defaultValue: 60),
  );

  static const String appVersion = '0.1.0';
}
