import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../../core/theme/status_colors.dart';
import '../../../core/utils/formatters.dart';
import '../../monitoring/data/reading.dart';
import '../../monitoring/presentation/monitoring_providers.dart';

/// Línea de tiempo de un parámetro con la banda del rango óptimo sombreada.
class HistoryChart extends StatelessWidget {
  const HistoryChart({
    super.key,
    required this.readings,
    required this.range,
    this.normalMin,
    this.normalMax,
  });

  /// Solo lecturas con valor (`Reading.hasValue`), en orden cronológico.
  final List<Reading> readings;
  final HistoryRange range;
  final double? normalMin;
  final double? normalMax;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusColors = StatusColors.of(context);
    final lineColor = theme.colorScheme.primary;
    final unit = readings.first.unit;

    final spots = [
      for (final reading in readings)
        FlSpot(
          reading.timestamp!.millisecondsSinceEpoch.toDouble(),
          reading.value!,
        ),
    ];
    final values = [for (final spot in spots) spot.y];
    final minValue = values.reduce(math.min);
    final maxValue = values.reduce(math.max);

    // El eje Y incluye la banda óptima para que siempre se vea el contexto.
    final low = math.min(minValue, normalMin ?? minValue);
    final high = math.max(maxValue, normalMax ?? maxValue);
    final padding = (high - low).abs() < 0.001 ? 1.0 : (high - low) * 0.15;

    final firstX = spots.first.x;
    final lastX = spots.last.x;
    final spanX = math.max(lastX - firstX, 1.0);

    return Semantics(
      label: 'Gráfica de ${readings.first.parameterName}: ${readings.length} '
          'lecturas, mínimo ${Formatters.number(minValue)}, '
          'máximo ${Formatters.number(maxValue)} $unit',
      excludeSemantics: true,
      child: LineChart(
        LineChartData(
          minX: firstX,
          maxX: firstX + spanX,
          minY: low - padding,
          maxY: high + padding,
          clipData: const FlClipData.all(),
          gridData: FlGridData(
            drawVerticalLine: false,
            getDrawingHorizontalLine: (value) => FlLine(
              color: theme.colorScheme.outlineVariant,
              strokeWidth: 1,
            ),
          ),
          borderData: FlBorderData(show: false),
          rangeAnnotations: RangeAnnotations(
            horizontalRangeAnnotations: [
              if (normalMin != null && normalMax != null)
                HorizontalRangeAnnotation(
                  y1: normalMin!,
                  y2: normalMax!,
                  color: statusColors.normal.accent.withValues(alpha: 0.12),
                ),
            ],
          ),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(),
            rightTitles: const AxisTitles(),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 44,
                getTitlesWidget: (value, meta) => SideTitleWidget(
                  meta: meta,
                  child: Text(
                    Formatters.number(value),
                    style: theme.textTheme.labelSmall,
                  ),
                ),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 28,
                interval: spanX / 4,
                getTitlesWidget: (value, meta) {
                  final date =
                      DateTime.fromMillisecondsSinceEpoch(value.toInt());
                  return SideTitleWidget(
                    meta: meta,
                    child: Text(
                      range == HistoryRange.day
                          ? Formatters.time(date)
                          : Formatters.dayMonth(date),
                      style: theme.textTheme.labelSmall,
                    ),
                  );
                },
              ),
            ),
          ),
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipColor: (spot) => theme.colorScheme.inverseSurface,
              getTooltipItems: (touchedSpots) => [
                for (final spot in touchedSpots)
                  LineTooltipItem(
                    '${Formatters.number(spot.y)} $unit\n'
                    '${Formatters.dateTime(DateTime.fromMillisecondsSinceEpoch(spot.x.toInt()))}',
                    TextStyle(color: theme.colorScheme.onInverseSurface),
                  ),
              ],
            ),
          ),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              preventCurveOverShooting: true,
              color: lineColor,
              barWidth: 2.5,
              dotData: FlDotData(show: spots.length <= 30),
              belowBarData: BarAreaData(
                show: true,
                color: lineColor.withValues(alpha: 0.08),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
