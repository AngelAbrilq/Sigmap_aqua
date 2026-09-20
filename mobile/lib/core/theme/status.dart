import 'package:flutter/material.dart';

import 'status_colors.dart';

/// Nivel visual de un estado, independiente del módulo que lo origina.
enum StatusLevel { normal, warning, critical, neutral }

extension StatusLevelStyle on StatusLevel {
  StatusPalette palette(BuildContext context) {
    final colors = StatusColors.of(context);
    return switch (this) {
      StatusLevel.normal => colors.normal,
      StatusLevel.warning => colors.warning,
      StatusLevel.critical => colors.critical,
      StatusLevel.neutral => colors.neutral,
    };
  }

  /// El estado nunca se comunica solo con color (accesibilidad).
  IconData get icon => switch (this) {
        StatusLevel.normal => Icons.check_circle_outline,
        StatusLevel.warning => Icons.warning_amber_rounded,
        StatusLevel.critical => Icons.error_outline,
        StatusLevel.neutral => Icons.info_outline,
      };
}
