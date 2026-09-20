import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Guarda los tokens JWT en el almacenamiento cifrado del sistema
/// (Android Keystore / iOS Keychain).
///
/// Nunca usar `shared_preferences` para tokens: es texto plano.
class TokenStorage {
  const TokenStorage([this._storage = const FlutterSecureStorage()]);

  static const _accessKey = 'bioaqua_access_token';
  static const _refreshKey = 'bioaqua_refresh_token';

  final FlutterSecureStorage _storage;

  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(key: _accessKey, value: accessToken);
    await _storage.write(key: _refreshKey, value: refreshToken);
  }

  Future<String?> readAccessToken() => _storage.read(key: _accessKey);

  Future<String?> readRefreshToken() => _storage.read(key: _refreshKey);

  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }
}
