import 'package:flutter/material.dart';

/// Colores de un estado: [accent] para íconos, bordes y gráficas;
/// [container] + [onContainer] para chips con contraste AA.
@immutable
class StatusPalette {
  const StatusPalette({
    required this.accent,
    required this.container,
    required this.onContainer,
  });

  final Color accent;
  final Color container;
  final Color onContainer;
}

/// Semáforo del sistema (mismos colores que la web: óptimo, riesgo, crítico),
/// expuesto como [ThemeExtension] para que respete modo claro/oscuro.
@immutable
class StatusColors extends ThemeExtension<StatusColors> {
  const StatusColors({
    required this.normal,
    required this.warning,
    required this.critical,
    required this.neutral,
  });

  static const light = StatusColors(
    normal: StatusPalette(
      accent: Color(0xFF12B76A),
      container: Color(0xFFE6F7ED),
      onContainer: Color(0xFF05603A),
    ),
    warning: StatusPalette(
      accent: Color(0xFFDC6803),
      container: Color(0xFFFEF0C7),
      onContainer: Color(0xFF93370D),
    ),
    critical: StatusPalette(
      accent: Color(0xFFD92D20),
      container: Color(0xFFFEE4E2),
      onContainer: Color(0xFF912018),
    ),
    neutral: StatusPalette(
      accent: Color(0xFF64748B),
      container: Color(0xFFF1F5F9),
      onContainer: Color(0xFF334155),
    ),
  );

  static const dark = StatusColors(
    normal: StatusPalette(
      accent: Color(0xFF32D583),
      container: Color(0xFF053321),
      onContainer: Color(0xFFA6F4C5),
    ),
    warning: StatusPalette(
      accent: Color(0xFFFDB022),
      container: Color(0xFF4E1D09),
      onContainer: Color(0xFFFEDF89),
    ),
    critical: StatusPalette(
      accent: Color(0xFFF97066),
      container: Color(0xFF55160C),
      onContainer: Color(0xFFFECDCA),
    ),
    neutral: StatusPalette(
      accent: Color(0xFF94A3B8),
      container: Color(0xFF1E293B),
      onContainer: Color(0xFFE2E8F0),
    ),
  );

  final StatusPalette normal;
  final StatusPalette warning;
  final StatusPalette critical;
  final StatusPalette neutral;

  static StatusColors of(BuildContext context) =>
      Theme.of(context).extension<StatusColors>() ?? light;

  @override
  StatusColors copyWith({
    StatusPalette? normal,
    StatusPalette? warning,
    StatusPalette? critical,
    StatusPalette? neutral,
  }) =>
      StatusColors(
        normal: normal ?? this.normal,
        warning: warning ?? this.warning,
        critical: critical ?? this.critical,
        neutral: neutral ?? this.neutral,
      );

  @override
  StatusColors lerp(covariant StatusColors? other, double t) =>
      (other == null || t < 0.5) ? this : other;
}
