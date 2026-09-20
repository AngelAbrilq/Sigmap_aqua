import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router/app_routes.dart';
import '../../../core/theme/status.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/breakpoints.dart';
import '../../../core/widgets/responsive_grid.dart';
import '../../../core/widgets/state_views.dart';
import '../../../core/widgets/status_chip.dart';
import '../data/pond.dart';
import 'ponds_providers.dart';

/// Listado de geomembranas con su estado general.
class PondsPage extends ConsumerWidget {
  const PondsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ponds = ref.watch(pondsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Geomembranas')),
      body: AsyncValueView<List<Pond>>(
        value: ponds,
        onRetry: () => ref.invalidate(pondsProvider),
        data: (items) => RefreshIndicator(
          onRefresh: () => ref.refresh(pondsProvider.future),
          child: items.isEmpty
              ? ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  children: const [
                    SizedBox(height: 120),
                    EmptyView(
                      title: 'No hay geomembranas registradas',
                      message: 'Regístralas desde la versión web.',
                      icon: Icons.water_outlined,
                    ),
                  ],
                )
              : ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: Breakpoints.pagePadding(context),
                  children: [
                    ResponsiveGrid(
                      itemCount: items.length,
                      minItemWidth: 320,
                      itemBuilder: (context, index) => PondCard(pond: items[index]),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

class PondCard extends StatelessWidget {
  const PondCard({super.key, required this.pond});

  final Pond pond;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final details = [
      if (pond.code.isNotEmpty) pond.code,
      if (pond.stage != null) pond.stage!,
      if (pond.volumeM3 != null) '${Formatters.number(pond.volumeM3)} m³',
    ].join(' · ');

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.go(AppRoutes.pondDetail(pond.id)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.water, color: theme.colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      pond.name,
                      style: theme.textTheme.titleMedium,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const Icon(Icons.chevron_right),
                ],
              ),
              if (details.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  details,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  StatusChip(label: pond.healthLabel, level: pond.healthLevel),
                  if (pond.status != 'activo')
                    StatusChip(label: pond.statusLabel, level: pond.statusLevel),
                  if (!pond.fitForProduction)
                    const StatusChip(
                      label: 'No apta para producción',
                      level: StatusLevel.critical,
                    ),
                  if (pond.activeAlerts > 0)
                    StatusChip(
                      label: pond.activeAlerts == 1
                          ? '1 alerta activa'
                          : '${pond.activeAlerts} alertas activas',
                      level: StatusLevel.critical,
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
