import 'package:dio/dio.dart';

/// Error de la API ya traducido a un mensaje apto para mostrar al usuario.
class ApiException implements Exception {
  const ApiException(
    this.message, {
    this.statusCode,
    this.fieldErrors = const {},
  });

  /// Construye la excepción a partir de un error de Dio, priorizando el
  /// `message` que envía el backend en `{success, data, message}`.
  factory ApiException.fromDio(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.transformTimeout:
        return const ApiException(
          'El servidor tardó demasiado en responder. Intenta de nuevo.',
        );
      case DioExceptionType.connectionError:
        return const ApiException(
          'No hay conexión con el servidor. Revisa la red o la URL de la API.',
        );
      case DioExceptionType.cancel:
        return const ApiException('La solicitud fue cancelada.');
      case DioExceptionType.badCertificate:
        return const ApiException('El certificado del servidor no es válido.');
      case DioExceptionType.badResponse:
      case DioExceptionType.unknown:
        break;
    }

    final statusCode = error.response?.statusCode;
    final body = error.response?.data;
    var message = _defaultMessage(statusCode);
    final fieldErrors = <String, List<String>>{};

    if (body is Map) {
      final serverMessage = body['message'] ?? body['detail'];
      if (serverMessage is String && serverMessage.trim().isNotEmpty) {
        message = serverMessage;
      }
      // Errores de validación por campo: {"email": ["Obligatorio."]}
      final errors = body.containsKey('success') ? body['data'] : body;
      if (errors is Map) {
        errors.forEach((key, value) {
          if (value is List) {
            fieldErrors['$key'] = value.map((item) => '$item').toList();
          }
        });
      }
    }

    return ApiException(
      message,
      statusCode: statusCode,
      fieldErrors: fieldErrors,
    );
  }

  final String message;
  final int? statusCode;
  final Map<String, List<String>> fieldErrors;

  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden => statusCode == 403;

  static String _defaultMessage(int? statusCode) {
    if (statusCode == null) return 'Ocurrió un error inesperado.';
    if (statusCode >= 500) return 'Error interno del servidor. Intenta más tarde.';
    return switch (statusCode) {
      400 => 'Los datos enviados no son válidos.',
      401 => 'Tu sesión expiró. Inicia sesión de nuevo.',
      403 => 'Tu rol no tiene permiso para esta acción.',
      404 => 'El recurso solicitado no existe.',
      429 => 'Demasiados intentos. Espera un momento.',
      _ => 'Ocurrió un error inesperado.',
    };
  }

  @override
  String toString() => message;
}

/// Mensaje legible para cualquier error que llegue a la UI.
String errorMessageOf(Object error) => error is ApiException
    ? error.message
    : 'Ocurrió un error inesperado. Intenta de nuevo.';
