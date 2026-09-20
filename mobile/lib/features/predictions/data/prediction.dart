import '../../../core/utils/json_parsers.dart';

/// Proyección falsable de un parámetro generada por la IA
/// (tabla `predicciones_ia`).
class Prediction {
  const Prediction({
    required this.id,
    required this.parameterName,
    required this.unit,
    required this.outOfRangeProbability,
    required this.status,
    this.expectedValue,
    this.minValue,
    this.maxValue,
    this.targetDate,
    this.justification,
  });

  factory Prediction.fromJson(Map<String, dynamic> json) => Prediction(
        id: parseInt(json['id']) ?? 0,
        parameterName: parseString(json['parametro']) ?? 'Parámetro',
        unit: parseString(json['unidad']) ?? '',
        outOfRangeProbability:
            (parseInt(json['probabilidad_fuera_rango']) ?? 0).clamp(0, 100).toInt(),
        status: parseString(json['estado']) ?? 'pendiente',
        expectedValue: parseDecimal(json['valor_esperado']),
        minValue: parseDecimal(json['valor_min']),
        maxValue: parseDecimal(json['valor_max']),
        targetDate: parseDateTime(json['fecha_objetivo']),
        justification: parseString(json['justificacion']),
      );

  final int id;
  final String parameterName;
  final String unit;

  /// 0–100.
  final int outOfRangeProbability;

  /// `pendiente`, `acertada`, `fallida` o `sin_datos`.
  final String status;
  final double? expectedValue;
  final double? minValue;
  final double? maxValue;
  final DateTime? targetDate;
  final String? justification;
}
