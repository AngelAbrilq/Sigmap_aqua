import 'package:flutter/material.dart';

/// Grilla que calcula sus columnas según el ancho disponible: 1 en celular,
/// 2–4 en horizontal o tablet. A diferencia de `GridView`, cada tarjeta toma
/// su alto natural, así que no se desborda con la escala de texto grande.
class ResponsiveGrid extends StatelessWidget {
  const ResponsiveGrid({
    super.key,
    required this.itemCount,
    required this.itemBuilder,
    this.minItemWidth = 300,
    this.maxColumns = 4,
    this.spacing = 12,
  });

  final int itemCount;
  final IndexedWidgetBuilder itemBuilder;
  final double minItemWidth;
  final int maxColumns;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = (constraints.maxWidth / minItemWidth)
            .floor()
            .clamp(1, maxColumns)
            .toInt();

        final rows = <Widget>[];
        for (var start = 0; start < itemCount; start += columns) {
          rows.add(
            Padding(
              padding: EdgeInsets.only(bottom: spacing),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (var column = 0; column < columns; column++) ...[
                    if (column > 0) SizedBox(width: spacing),
                    Expanded(
                      child: start + column < itemCount
                          ? itemBuilder(context, start + column)
                          : const SizedBox.shrink(),
                    ),
                  ],
                ],
              ),
            ),
          );
        }
        return Column(children: rows);
      },
    );
  }
}
