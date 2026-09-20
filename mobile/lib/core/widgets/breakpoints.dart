/// Breakpoints de Material 3 (ancho en dp).
abstract final class Breakpoints {
  /// < 600: celular en vertical.
  static const double medium = 600;

  /// >= 840: tablet grande o celular plegable abierto.
  static const double expanded = 840;

  static bool isCompact(double width) => width < medium;
  static bool isExpanded(double width) => width >= expanded;
}
