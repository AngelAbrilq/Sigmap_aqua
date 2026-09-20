import '../../../core/theme/status.dart';
import '../../../core/utils/json_parsers.dart';

/// Estado de una lectura según los rangos de `tipos_parametros`.
enum ReadingStatus {
  normal('normal', 'Óptimo', StatusLevel.normal),
  warning('riesgo', 'Riesgo', StatusLevel.warning),
  critical('critico', 'Crítico', StatusLevel.critical),
  noData('sin_datos', 'Sin datos', StatusLevel.neutral),
  unknown('', 'Sin clasificar', StatusLevel.neutral);

  const ReadingStatus(this.apiValue, this.label, this.level);

  final String apiValue;
  final String label;
  final StatusLevel level;

  static ReadingStatus fromApi(Object? raw) => values.firstWhere(
        (status) => status.apiValue == raw,
        orElse: () => ReadingStatus.unknown,
      );
}

/// Medición de un sensor (tabla `lecturas_sensores`).
class Reading {
  const Reading({
    required this.id,
    required this.parameterId,
    required this.parameterName,
    required this.unit,
    required this.status,
    this.value,
    this.timestamp,
    this.sensorCode,
    this.normalMin,
    this.normalMax,
  });

  factory Reading.fromJson(Map<String, dynamic> json) => Reading(
        id: parseInt(json['id']) ?? 0,
        parameterId: parseInt(json['parametro_id']) ?? 0,
        parameterName: parseString(json['parametro']) ?? 'Parámetro',
        unit: parseString(json['unidad']) ?? '',
        value: parseDecimal(json['valor_medida']),
        status: ReadingStatus.fromApi(json['estado_lectura']),
        timestamp: parseDateTime(json['timestamp_lectura']),
        sensorCode: parseString(json['sensor']),
        normalMin: parseDecimal(json['rango_min'] ?? json['rango_normal_min']),
        normalMax: parseDecimal(json['rango_max'] ?? json['rango_normal_max']),
      );

  final int id;
  final int parameterId;
  final String parameterName;
  final String unit;
  /// `null` si el sensor existe pero todavía no reporta ("Sin datos").
  final double? value;
  final ReadingStatus status;
  final DateTime? timestamp;

  bool get hasValue => value != null && timestamp != null;
  final String? sensorCode;
  final double? normalMin;
  final double? normalMax;
}
