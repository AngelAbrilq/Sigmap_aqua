import 'package:intl/intl.dart';

/// Formatos de presentación en español (Colombia).
abstract final class Formatters {
  static final _number = NumberFormat('#,##0.##', 'es');
  static final _dateTime = DateFormat("d MMM, h:mm a", 'es');
  static final _date = DateFormat('d MMM y', 'es');
  static final _time = DateFormat('h:mm a', 'es');
  static final _dayMonth = DateFormat('d/MM', 'es');

  static String number(double? value) =>
      value == null ? '—' : _number.format(value);

  static String dateTime(DateTime? value) =>
      value == null ? '—' : _dateTime.format(value);

  static String date(DateTime? value) =>
      value == null ? '—' : _date.format(value);

  static String time(DateTime value) => _time.format(value);

  static String dayMonth(DateTime value) => _dayMonth.format(value);

  /// "hace 3 min", "hace 2 h", o la fecha si pasó más de un día.
  static String relative(DateTime? value, {DateTime? now}) {
    if (value == null) return 'Sin datos';
    final difference = (now ?? DateTime.now()).difference(value);
    if (difference.inSeconds < 60) return 'hace un momento';
    if (difference.inMinutes < 60) return 'hace ${difference.inMinutes} min';
    if (difference.inHours < 24) return 'hace ${difference.inHours} h';
    return dateTime(value);
  }

  /// "6,5 – 8,5 mg/L", o null si el rango no está configurado.
  static String? range(double? min, double? max, String unit) {
    if (min == null && max == null) return null;
    final suffix = unit.isEmpty ? '' : ' $unit';
    return '${number(min)} – ${number(max)}$suffix';
  }
}
