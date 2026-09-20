import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_exception.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/breakpoints.dart';
import '../../../core/widgets/state_views.dart';
import '../../../core/widgets/status_chip.dart';
import '../../monitoring/data/monitoring_repository.dart';
import '../../monitoring/data/reading.dart';
import '../../monitoring/presentation/monitoring_providers.dart';
import '../../ponds/presentation/ponds_providers.dart';
import 'history_chart.dart';

/// Historial de un parámetro con filtros de rango y gráfica.
class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key, required this.pondId, this.initialParameterId});

  final int pondId;
  final int? initialParameterId;

  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage> {
  int? _parameterId;
  HistoryRange _range = HistoryRange.week;

  @override
  void initState() {
    super.initState();
    _parameterId = widget.initialParameterId;
  }

  @override
  Widget build(BuildContext context) {
    final pondName = ref.watch(pondProvider(widget.pondId)).value?.name;
    // Los parámetros disponibles salen de las últimas lecturas.
    final parameters = ref.watch(latestReadingsProvider(widget.pondId));

    return Scaffold(
      appBar: AppBar(
        title: Text(pondName == null ? 'Historial' : 'Historial · $pondName'),
      ),
      body: AsyncValueView<List<Reading>>(
        value: parameters,
        onRetry: () => ref.invalidate(latestReadingsProvider(widget.pondId)),
        data: (latest) {
          if (latest.isEmpty) {
            return const EmptyView(
              title: 'Sin parámetros con lecturas',
              icon: Icons.sensors_off_outlined,
            );
          }
          final selected = latest.firstWhere(
            (reading) => reading.parameterId == _parameterId,
            orElse: () => latest.first,
          );
          return _HistoryBody(
            pondId: widget.pondId,
            parameters: latest,
            selected: selected,
            range: _range,
            onParameterChanged: (id) => setState(() => _parameterId = id),
            onRangeChanged: (range) => setState(() => _range = range),
          );
        },
      ),
    );
  }
}

class _HistoryBody extends ConsumerWidget {
  const _HistoryBody({
    required this.pondId,
    required this.parameters,
    required this.selected,
    required this.range,
    required this.onParameterChanged,
    required this.onRangeChanged,
  });

  final int pondId;
  final List<Reading> parameters;
  final Reading selected;
  final HistoryRange range;
  final ValueChanged<int> onParameterChanged;
  final ValueChanged<HistoryRange> onRangeChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = (
      pondId: pondId,
      parameterId: selected.parameterId,
      range: range,
    );
    final history = ref.watch(historyProvider(query));
    final width = MediaQuery.sizeOf(context).width;
    final chartHeight = Breakpoints.isCompact(width) ? 240.0 : 320.0;

    return RefreshIndicator(
      onRefresh: () => ref.refresh(historyProvider(query).future),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final parameter in parameters)
                ChoiceChip(
                  label: Text(parameter.parameterName),
                  selected: parameter.parameterId == selected.parameterId,
                  onSelected: (_) => onParameterChanged(parameter.parameterId),
                ),
            ],
          ),
          const SizedBox(height: 12),
          SegmentedButton<HistoryRange>(
            segments: [
              for (final option in HistoryRange.values)
                ButtonSegment(value: option, label: Text(option.label)),
            ],
            selected: {range},
            showSelectedIcon: false,
            onSelectionChanged: (selection) => onRangeChanged(selection.first),
          ),
          const SizedBox(height: 16),
          history.when(
            loading: () => SizedBox(
              height: chartHeight,
              child: const LoadingView(),
            ),
            error: (error, stackTrace) => SizedBox(
              height: chartHeight,
              child: ErrorView(
                message: errorMessageOf(error),
                onRetry: () => ref.invalidate(historyProvider(query)),
              ),
            ),
            data: (readings) => readings.isEmpty
                ? SizedBox(
                    height: chartHeight,
                    child: const EmptyView(
                      title: 'Sin lecturas en este periodo',
                      icon: Icons.timeline_outlined,
                    ),
                  )
                : _HistoryContent(
                    readings: readings,
                    selected: selected,
                    range: range,
                    chartHeight: chartHeight,
                  ),
          ),
        ],
      ),
    );
  }
}

class _HistoryContent extends StatelessWidget {
  const _HistoryContent({
    required this.readings,
    required this.selected,
    required this.range,
    required this.chartHeight,
  });

  static const _visibleRows = 50;

  final List<Reading> readings;
  final Reading selected;
  final HistoryRange range;
  final double chartHeight;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final latestFirst = readings.reversed.take(_visibleRows).toList();
    final truncated = readings.length >= MonitoringRepository.historyLimit;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 16, 16, 8),
            child: SizedBox(
              height: chartHeight,
              child: HistoryChart(
                readings: readings,
                range: range,
                normalMin: selected.normalMin,
                normalMax: selected.normalMax,
              ),
            ),
          ),
        ),
        if (truncated)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              'Se muestran las ${MonitoringRepository.historyLimit} lecturas '
              'más recientes del periodo.',
              style: theme.textTheme.bodySmall,
            ),
          ),
        const SizedBox(height: 16),
        Text('Últimas lecturas', style: theme.textTheme.titleMedium),
        const SizedBox(height: 8),
        Card(
          child: Column(
            children: [
              for (final reading in latestFirst)
                ListTile(
                  dense: true,
                  title: Text(
                    '${Formatters.number(reading.value)} ${reading.unit}',
                  ),
                  subtitle: Text(Formatters.dateTime(reading.timestamp)),
                  trailing: StatusChip(
                    label: reading.status.label,
                    level: reading.status.level,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
