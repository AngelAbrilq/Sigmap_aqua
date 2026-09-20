import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_exception.dart';
import '../../../core/network/providers.dart';
import '../../../core/theme/status.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/section_header.dart';
import '../data/prediction.dart';
import '../data/predictions_repository.dart';

final predictionsRepositoryProvider = Provider<PredictionsRepository>(
  (ref) => PredictionsRepository(ref.watch(apiClientProvider)),
);

final predictionsProvider =
    FutureProvider.autoDispose.family<List<Prediction>, int>(
  (ref, pondId) =>
      ref.watch(predictionsRepositoryProvider).fetchPredictions(pondId),
);

/// Bloque de predicciones de IA dentro del detalle de la geomembrana.
class PredictionsSection extends ConsumerWidget {
  const PredictionsSection({super.key, required this.pondId});

  final int pondId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final predictions = ref.watch(predictionsProvider(pondId));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionHeader(
          title: 'Predicciones IA',
          subtitle: 'Proyecciones pendientes de verificar',
        ),
        predictions.when(
          loading: () => const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (error, stackTrace) => _InfoCard(
            icon: Icons.cloud_off_outlined,
            text: errorMessageOf(error),
          ),
          data: (items) => items.isEmpty
              ? const _InfoCard(
                  icon: Icons.auto_awesome_outlined,
                  text: 'No hay predicciones vigentes para esta geomembrana.',
                )
              : Column(
                  children: [
                    for (final prediction in items)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: PredictionCard(prediction: prediction),
                      ),
                  ],
                ),
        ),
      ],
    );
  }
}

class PredictionCard extends StatelessWidget {
  const PredictionCard({super.key, required this.prediction});

  final Prediction prediction;

  StatusLevel get _riskLevel => switch (prediction.outOfRangeProbability) {
        >= 60 => StatusLevel.critical,
        >= 30 => StatusLevel.warning,
        _ => StatusLevel.normal,
      };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final palette = _riskLevel.palette(context);
    final range =
        Formatters.range(prediction.minValue, prediction.maxValue, prediction.unit);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    prediction.parameterName,
                    style: theme.textTheme.titleSmall,
                  ),
                ),
                Text(
                  Formatters.date(prediction.targetDate),
                  style: theme.textTheme.labelMedium,
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'Esperado: ${Formatters.number(prediction.expectedValue)} ${prediction.unit}'
              '${range == null ? '' : '  (entre $range)'}',
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 10),
            Semantics(
              label: 'Probabilidad de salir de rango: '
                  '${prediction.outOfRangeProbability} por ciento',
              excludeSemantics: true,
              child: Row(
                children: [
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(999),
                      child: LinearProgressIndicator(
                        value: prediction.outOfRangeProbability / 100,
                        minHeight: 8,
                        color: palette.accent,
                        backgroundColor: palette.container,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(_riskLevel.icon, size: 18, color: palette.accent),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      '${prediction.outOfRangeProbability}% fuera de rango',
                    ),
                  ),
                ],
              ),
            ),
            if (prediction.justification != null) ...[
              const SizedBox(height: 10),
              Text(
                prediction.justification!,
                maxLines: 4,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(leading: Icon(icon), title: Text(text)),
    );
  }
}
