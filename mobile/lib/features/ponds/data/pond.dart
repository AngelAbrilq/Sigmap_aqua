import '../../../core/theme/status.dart';
import '../../../core/utils/json_parsers.dart';

/// Geomembrana (estanque piscícola).
class Pond {
  const Pond({
    required this.id,
    required this.name,
    required this.code,
    required this.status,
    required this.fitForProduction,
    this.location,
    this.stage,
    this.areaM2,
    this.volumeM3,
    this.activeAlerts = 0,
    this.operationalStatus,
    this.operationalLabel,
  });

  factory Pond.fromJson(Map<String, dynamic> json) {
    final stage = json['etapa'] ?? json['etapa_actual'];
    return Pond(
      id: parseInt(json['id']) ?? 0,
      name: parseString(json['nombre_piscina']) ?? 'Sin nombre',
      code: parseString(json['codigo_identificacion']) ?? '',
      status: parseString(json['estado']) ?? 'activo',
      fitForProduction: json['apta_para_produccion'] != false,
      location: parseString(json['ubicacion']),
      // Acepta el nombre plano o el objeto anidado {nombre_etapa: ...}.
      stage: stage is Map ? parseString(stage['nombre_etapa']) : parseString(stage),
      areaM2: parseDecimal(json['area_m2']),
      volumeM3: parseDecimal(json['volumen_agua_m3']),
      activeAlerts: parseInt(json['alertas_activas']) ?? 0,
      operationalStatus: parseString(json['estado_operativo']),
      operationalLabel: parseString(json['estado_operativo_label']),
    );
  }

  final int id;
  final String name;
  final String code;

  /// `activo`, `inactivo` o `mantenimiento` (choices del modelo Django).
  final String status;
  final bool fitForProduction;
  final String? location;
  final String? stage;
  final double? areaM2;
  final double? volumeM3;
  final int activeAlerts;

  /// Semáforo consolidado del backend: `ok`, `warn` o `crit`.
  final String? operationalStatus;
  final String? operationalLabel;

  /// Etiqueta del semáforo; si el backend no la envía, usa el estado.
  String get healthLabel => operationalLabel ?? statusLabel;

  StatusLevel get healthLevel => switch (operationalStatus) {
        'ok' => StatusLevel.normal,
        'warn' => StatusLevel.warning,
        'crit' => StatusLevel.critical,
        _ => statusLevel,
      };

  String get statusLabel => switch (status) {
        'activo' => 'Activa',
        'mantenimiento' => 'En mantenimiento',
        'inactivo' => 'Inactiva',
        _ => status,
      };

  StatusLevel get statusLevel => switch (status) {
        'activo' => StatusLevel.normal,
        'mantenimiento' => StatusLevel.warning,
        _ => StatusLevel.neutral,
      };
}
