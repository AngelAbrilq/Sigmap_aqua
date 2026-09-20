import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/config/app_modules.dart';
import '../../../core/config/env.dart';
import '../../../core/router/app_routes.dart';
import '../../../core/widgets/breakpoints.dart';
import '../../../core/widgets/responsive_grid.dart';
import '../../../core/widgets/section_header.dart';
import '../../../core/widgets/state_views.dart';
import '../../auth/presentation/auth_controller.dart';
import '../../monitoring/data/reading.dart';
import '../../monitoring/presentation/monitoring_providers.dart';
import '../../monitoring/presentation/reading_card.dart';
import '../../predictions/presentation/predictions_section.dart';
import 'ponds_providers.dart';

/// Detalle de una geomembrana: lecturas en vivo + predicciones de IA.
///
/// En pantallas >= 840 dp las predicciones pasan a una columna lateral.
class PondDetailPage extends ConsumerWidget {
  const PondDetailPage({super.key, required this.pondId});

  final int pondId;

  Future<void> _refresh(WidgetRef ref) async {
    ref.invalidate(predictionsProvider(pondId));
    ref.invalidate(latestReadingsProvider(pondId));
    await ref.read(latestReadingsProvider(pondId).future);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pond = ref.watch(pondProvider(pondId));
    final user = ref.watch(authControllerProvider).value;
    final canSeeAi = user?.canView(AppModule.ai) ?? false;
    final canSeeHistory = user?.canView(AppModule.history) ?? false;

    return Scaffold(
      appBar: AppBar(
        title: Text(pond.value?.name ?? 'Geomembrana'),
        actions: [
          if (canSeeHistory)
            IconButton(
              tooltip: 'Historial',
              icon: const Icon(Icons.show_chart),
              onPressed: () => context.go(AppRoutes.pondHistory(pondId)),
            ),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final readings = _ReadingsSection(
            pondId: pondId,
            canSeeHistory: canSeeHistory,
          );
          final predictions =
              canSeeAi ? PredictionsSection(pondId: pondId) : null;

          if (Breakpoints.isExpanded(constraints.maxWidth) && predictions != null) {
            return RefreshIndicator(
              onRefresh: () => _refresh(ref),
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 3, child: readings),
                      const SizedBox(width: 24),
                      Expanded(flex: 2, child: predictions),
                    ],
                  ),
                ],
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: () => _refresh(ref),
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                readings,
                if (predictions != null) ...[
                  const SizedBox(height: 24),
                  predictions,
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _ReadingsSection extends ConsumerWidget {
  const _ReadingsSection({required this.pondId, required this.canSeeHistory});

  final int pondId;
  final bool canSeeHistory;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final readings = ref.watch(latestReadingsProvider(pondId));
    final showsGrid = readings.hasValue &&
        !readings.hasError &&
        (readings.value?.isNotEmpty ?? false);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(
          title: 'Lecturas actuales',
          subtitle: 'Se actualiza cada ${Env.pollingInterval.inSeconds} s',
          trailing: readings.isLoading && readings.hasValue
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : null,
        ),
        SizedBox(
          // La vista de estado necesita alto propio dentro del ListView.
          height: showsGrid ? null : 260,
          child: AsyncValueView<List<Reading>>(
            value: readings,
            onRetry: () => ref.invalidate(latestReadingsProvider(pondId)),
            data: (items) => items.isEmpty
                ? const EmptyView(
                    title: 'Sin lecturas todavía',
                    message: 'Verifica que el nodo ESP32 de esta geomembrana '
                        'esté encendido y enviando datos.',
                    icon: Icons.sensors_off_outlined,
                  )
                : ResponsiveGrid(
                    itemCount: items.length,
                    minItemWidth: 260,
                    maxColumns: 3,
                    itemBuilder: (context, index) {
                      final reading = items[index];
                      return ReadingCard(
                        reading: reading,
                        onTap: canSeeHistory
                            ? () => context.go(
                                  AppRoutes.pondHistory(
                                    pondId,
                                    parameterId: reading.parameterId,
                                  ),
                                )
                            : null,
                      );
                    },
                  ),
          ),
        ),
      ],
    );
  }
}
