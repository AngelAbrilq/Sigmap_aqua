import 'package:flutter/widgets.dart';

/// Breakpoints de Material 3 (ancho en dp).
abstract final class Breakpoints {
  /// < 600: celular en vertical.
  static const double medium = 600;

  /// >= 840: tablet grande o celular plegable abierto.
  static const double expanded = 840;

  /// Alto util escaso: celular en horizontal o ventana partida.
  static const double shortHeight = 500;

  static bool isCompact(double width) => width < medium;
  static bool isExpanded(double width) => width >= expanded;
  static bool isShort(double height) => height < shortHeight;

  /// Margen de página: recorta el espacio vertical cuando la pantalla es
  /// baja (horizontal), para que quepa una tarjeta más sin hacer scroll.
  static EdgeInsets pagePadding(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    return EdgeInsets.symmetric(
      horizontal: 16,
      vertical: isShort(size.height) ? 8 : 16,
    );
  }
}
