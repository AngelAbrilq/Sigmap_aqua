import '../../../core/network/api_client.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/network/api_response.dart';
import '../../../core/storage/token_storage.dart';
import 'app_user.dart';

/// Flujo JWT completo: login → token → refresh (en [ApiClient]) → logout.
class AuthRepository {
  AuthRepository(this._api, this._tokenStorage);

  final ApiClient _api;
  final TokenStorage _tokenStorage;

  /// Inicia sesión, guarda los tokens y devuelve el perfil con permisos.
  Future<AppUser> login({
    required String email,
    required String password,
  }) async {
    final body = await _api.post(
      '/auth/token/',
      data: {'email': email.trim(), 'password': password},
      options: ApiClient.publicRequest,
    );
    final data = unwrapMap(body);
    final accessToken = data['access'];
    final refreshToken = data['refresh'];
    if (accessToken is! String || refreshToken is! String) {
      throw const ApiException('El servidor no devolvió los tokens de sesión.');
    }
    await _tokenStorage.saveTokens(
      accessToken: accessToken,
      refreshToken: refreshToken,
    );
    return fetchCurrentUser();
  }

  /// Recupera la sesión guardada al abrir la app.
  /// Devuelve `null` si no hay sesión o si el servidor ya no la acepta.
  Future<AppUser?> restoreSession() async {
    final refreshToken = await _tokenStorage.readRefreshToken();
    if (refreshToken == null) return null;
    try {
      return await fetchCurrentUser();
    } on ApiException catch (error) {
      if (error.isUnauthorized || error.isForbidden) {
        await _tokenStorage.clear();
        return null;
      }
      rethrow; // Sin red: la pantalla de inicio ofrece reintentar.
    }
  }

  Future<AppUser> fetchCurrentUser() async =>
      AppUser.fromJson(unwrapMap(await _api.get('/auth/me/')));

  /// Invalida el refresh token en el servidor (blacklist) y borra los
  /// tokens locales. Si no hay red, igual se cierra la sesión en el teléfono.
  Future<void> logout() async {
    final refreshToken = await _tokenStorage.readRefreshToken();
    try {
      if (refreshToken != null) {
        await _api.post('/auth/logout/', data: {'refresh': refreshToken});
      }
    } on ApiException {
      // Token ya inválido o sin conexión: no bloquea el cierre local.
    } finally {
      await _tokenStorage.clear();
    }
  }
}
