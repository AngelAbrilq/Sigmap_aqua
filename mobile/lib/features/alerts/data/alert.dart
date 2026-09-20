import '../../../core/theme/status.dart';
import '../../../core/utils/json_parsers.dart';

enum AlertStatus {
  active('activa', 'Activas'),
  acknowledged('reconocida', 'Reconocidas'),
  resolved('resuelta', 'Resueltas'),
  dismissed('descartada', 'Descartadas');

  const AlertStatus(this.apiValue, this.label);

  final String apiValue;
  final String label;

  static AlertStatus fromApi(Object? raw) => values.firstWhere(
        (status) => status.apiValue == raw,
        orElse: () => AlertStatus.active,
      );
}

enum AlertSeverity {
  low('baja', 'Baja', StatusLevel.warning),
  medium('media', 'Media', StatusLevel.warning),
  high('alta', 'Alta', StatusLevel.critical),
  critical('critica', 'Crítica', StatusLevel.critical);

  const AlertSeverity(this.apiValue, this.label, this.level);

  final String apiValue;
  final String label;
  final StatusLevel level;

  static AlertSeverity fromApi(Object? raw) => values.firstWhere(
        (severity) => severity.apiValue == raw,
        orElse: () => AlertSeverity.medium,
      );
}

/// Alerta generada por el motor de reglas (tabla `alertas`).
class Alert {
  const Alert({
    required this.id,
    required this.pondName,
    required this.type,
    required this.severity,
    required this.status,
    required this.message,
    required this.createdAt,
    this.pondId,
    this.parameterName,
    this.triggerValue,
    this.actionTaken,
  });

  factory Alert.fromJson(Map<String, dynamic> json) => Alert(
        id: parseInt(json['id']) ?? 0,
        pondId: parseInt(json['geomembrana']),
        pondName: parseString(json['piscina']) ?? 'Geomembrana',
        parameterName: parseString(json['parametro']),
        type: parseString(json['tipo_alerta']) ?? '',
        severity: AlertSeverity.fromApi(json['severidad']),
        status: AlertStatus.fromApi(json['estado']),
        message: parseString(json['mensaje_alerta']) ?? '',
        triggerValue: parseDecimal(json['valor_que_disparo']),
        createdAt: parseDateTime(json['fecha_generacion']) ?? DateTime.now(),
        actionTaken: parseString(json['accion_tomada']),
      );

  final int id;
  final int? pondId;
  final String pondName;
  final String? parameterName;

  /// `riesgo`, `critico`, `sensor` o `desconexion`.
  final String type;
  final AlertSeverity severity;
  final AlertStatus status;
  final String message;
  final double? triggerValue;
  final DateTime createdAt;
  final String? actionTaken;

  bool get canBeAcknowledged => status == AlertStatus.active;

  bool get canBeResolved =>
      status == AlertStatus.active || status == AlertStatus.acknowledged;

  String get typeLabel => switch (type) {
        'riesgo' => 'Riesgo',
        'critico' => 'Crítico',
        'sensor' => 'Falla de sensor',
        'desconexion' => 'Sin conexión',
        _ => type,
      };
}
