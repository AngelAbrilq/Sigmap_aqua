/// Conversores tolerantes para los tipos que envía DRF.
///
/// DRF serializa `DecimalField` como texto ("7.2500") para no perder
/// precisión; aquí se convierte a `double` solo para mostrar o graficar.
double? parseDecimal(Object? raw) => switch (raw) {
      final num number => number.toDouble(),
      final String text => double.tryParse(text),
      _ => null,
    };

int? parseInt(Object? raw) => switch (raw) {
      final int number => number,
      final num number => number.toInt(),
      final String text => int.tryParse(text),
      _ => null,
    };

/// Fecha ISO-8601 del servidor convertida a la zona horaria del teléfono.
DateTime? parseDateTime(Object? raw) =>
    raw is String ? DateTime.tryParse(raw)?.toLocal() : null;

String? parseString(Object? raw) => switch (raw) {
      null => null,
      final String text when text.trim().isEmpty => null,
      final String text => text,
      _ => '$raw',
    };
