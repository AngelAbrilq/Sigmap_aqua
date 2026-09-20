import 'package:dio/dio.dart';

import '../config/env.dart';
import '../storage/token_storage.dart';
import 'api_exception.dart';
import 'api_response.dart';

/// Cliente HTTP único de la app (equivalente a la instancia base de Axios).
///
/// - Adjunta `Authorization: Bearer <access>` a cada petición privada.
/// - Si el servidor responde 401, renueva el access token con el refresh
///   token y reintenta la petición una sola vez.
/// - Si la renovación falla, borra los tokens y avisa con [onSessionExpired].
///
/// Los widgets nunca usan esta clase directamente: pasan por un repositorio.
class ApiClient {
  ApiClient({
    required TokenStorage tokenStorage,
    required this.onSessionExpired,
    Dio? dio,
    Dio? plainDio,
  })  : _tokenStorage = tokenStorage,
        dio = dio ?? Dio(_baseOptions()),
        _plainDio = plainDio ?? Dio(_baseOptions()) {
    this.dio.interceptors.add(
          QueuedInterceptorsWrapper(
            onRequest: _attachToken,
            onError: _refreshOnUnauthorized,
          ),
        );
  }

  static const _skipAuthKey = 'skipAuth';
  static const _retriedKey = 'retried';

  /// Opciones para endpoints públicos (login): sin Bearer y sin refresh.
  static Options get publicRequest => Options(extra: {_skipAuthKey: true});

  final TokenStorage _tokenStorage;
  final void Function() onSessionExpired;

  /// Instancia con interceptores, para las peticiones de la app.
  final Dio dio;

  /// Instancia sin interceptores, para refrescar y reintentar sin bloquear
  /// la cola del [QueuedInterceptorsWrapper].
  final Dio _plainDio;

  static BaseOptions _baseOptions() => BaseOptions(
        baseUrl: Env.apiUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 20),
        contentType: Headers.jsonContentType,
        headers: const {'Accept': 'application/json'},
      );

  /// GET que devuelve el cuerpo JSON o lanza [ApiException].
  Future<Object?> get(String path, {Map<String, dynamic>? query}) =>
      _send(() => dio.get<Object?>(path, queryParameters: query));

  /// POST que devuelve el cuerpo JSON o lanza [ApiException].
  Future<Object?> post(String path, {Object? data, Options? options}) =>
      _send(() => dio.post<Object?>(path, data: data, options: options));

  Future<Object?> _send(Future<Response<Object?>> Function() request) async {
    try {
      final response = await request();
      return response.data;
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<void> _attachToken(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (options.extra[_skipAuthKey] != true) {
      final accessToken = await _tokenStorage.readAccessToken();
      if (accessToken != null) {
        options.headers['Authorization'] = 'Bearer $accessToken';
      }
    }
    handler.next(options);
  }

  Future<void> _refreshOnUnauthorized(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final request = error.requestOptions;
    final canRefresh = error.response?.statusCode == 401 &&
        request.extra[_skipAuthKey] != true &&
        request.extra[_retriedKey] != true;

    if (!canRefresh) {
      handler.next(error);
      return;
    }

    // Si otra petición de la cola ya renovó el token, se reutiliza en vez
    // de gastar otra rotación del refresh token.
    final usedToken =
        '${request.headers['Authorization'] ?? ''}'.replaceFirst('Bearer ', '');
    final storedToken = await _tokenStorage.readAccessToken();
    final newAccessToken = (storedToken != null && storedToken != usedToken)
        ? storedToken
        : await _refreshAccessToken();

    if (newAccessToken == null) {
      await _tokenStorage.clear();
      onSessionExpired();
      handler.next(error);
      return;
    }

    request.headers['Authorization'] = 'Bearer $newAccessToken';
    request.extra[_retriedKey] = true;
    try {
      handler.resolve(await _plainDio.fetch<Object?>(request));
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }

  /// Pide un access token nuevo. Devuelve `null` si el refresh expiró
  /// o fue invalidado (logout, rotación, cuenta desactivada).
  Future<String?> _refreshAccessToken() async {
    final refreshToken = await _tokenStorage.readRefreshToken();
    if (refreshToken == null) return null;

    try {
      final response = await _plainDio.post<Object?>(
        '/auth/refresh/',
        data: {'refresh': refreshToken},
      );
      final data = unwrapMap(response.data);
      final accessToken = data['access'];
      if (accessToken is! String) return null;

      final rotatedRefresh = data['refresh'];
      await _tokenStorage.saveTokens(
        accessToken: accessToken,
        refreshToken: rotatedRefresh is String ? rotatedRefresh : refreshToken,
      );
      return accessToken;
    } on DioException {
      return null;
    } on ApiException {
      return null;
    }
  }
}
