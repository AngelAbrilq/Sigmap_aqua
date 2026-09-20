import 'package:flutter/material.dart';

import '../theme/status.dart';

/// Etiqueta de estado con color + ícono + texto (nunca solo color).
class StatusChip extends StatelessWidget {
  const StatusChip({super.key, required this.label, required this.level});

  final String label;
  final StatusLevel level;

  @override
  Widget build(BuildContext context) {
    final palette = level.palette(context);
    return Semantics(
      label: 'Estado: $label',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: palette.container,
          borderRadius: BorderRadius.circular(999),
        ),
        // Un solo Text (con el ícono como WidgetSpan) funciona con ancho
        // acotado (Wrap, recorta con "…") y no acotado (dentro de un Row).
        child: Text.rich(
          TextSpan(
            children: [
              WidgetSpan(
                alignment: PlaceholderAlignment.middle,
                child: Padding(
                  padding: const EdgeInsets.only(right: 4),
                  child: Icon(level.icon, size: 16, color: palette.onContainer),
                ),
              ),
              TextSpan(text: label),
            ],
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: palette.onContainer,
                fontWeight: FontWeight.w600,
              ),
        ),
      ),
    );
  }
}
