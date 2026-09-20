import 'package:flutter/material.dart';

import '../../../core/theme/status.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/status_chip.dart';
import '../data/reading.dart';

/// Tarjeta de un parámetro: valor actual, estado y rango óptimo.
class ReadingCard extends StatelessWidget {
  const ReadingCard({super.key, required this.reading, this.onTap});

  final Reading reading;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final palette = reading.status.level.palette(context);
    final range = Formatters.range(reading.normalMin, reading.normalMax, reading.unit);
    final valueText = Formatters.number(reading.value);
    final hasValue = reading.hasValue;

    return Semantics(
      button: onTap != null,
      label: '${reading.parameterName}: $valueText ${reading.unit}, '
          '${reading.status.label}, ${Formatters.relative(reading.timestamp)}',
      excludeSemantics: true,
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: DecoratedBox(
            decoration: BoxDecoration(
              border: Border(left: BorderSide(color: palette.accent, width: 5)),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          reading.parameterName,
                          style: theme.textTheme.titleSmall,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      StatusChip(
                        label: reading.status.label,
                        level: reading.status.level,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (hasValue)
                    Text.rich(
                      TextSpan(
                        children: [
                          TextSpan(
                            text: valueText,
                            style: theme.textTheme.headlineMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          if (reading.unit.isNotEmpty)
                            TextSpan(
                              text: ' ${reading.unit}',
                              style: theme.textTheme.titleMedium,
                            ),
                        ],
                      ),
                    )
                  else
                    // Un sensor mudo no se disfraza con un guion gigante:
                    // se dice qué pasa, que es lo que el operario necesita.
                    Text(
                      'Este sensor aún no reporta',
                      style: theme.textTheme.titleSmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  const SizedBox(height: 4),
                  Text(
                    [
                      if (range != null) 'Óptimo: $range',
                      if (hasValue) Formatters.relative(reading.timestamp),
                    ].join(' · '),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
