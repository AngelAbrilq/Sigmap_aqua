import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_modules.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/theme/status.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/responsive_grid.dart';
import '../../../core/widgets/state_views.dart';
import '../../../core/widgets/status_chip.dart';
import '../../auth/presentation/auth_controller.dart';
import '../data/alert.dart';
import 'alerts_providers.dart';
import 'resolve_alert_dialog.dart';

/// Bandeja de alertas con filtro por estado.
/// Reconocer y resolver solo aparece si el rol tiene escritura en `alertas`.
class AlertsPage extends ConsumerStatefulWidget {
  const AlertsPage({super.key});

  @override
  ConsumerState<AlertsPage> createState() => _AlertsPageState();
}

class _AlertsPageState extends ConsumerState<AlertsPage> {
  static const _filters = [
    AlertStatus.active,
    AlertStatus.acknowledged,
    AlertStatus.resolved,
  ];

  AlertStatus _status = AlertStatus.active;
  final Set<int> _busyAlertIds = {};

  Future<void> _runAction(
    Alert alert,
    Future<void> Function() action,
    String successMessage,
  ) async {
    setState(() => _busyAlertIds.add(alert.id));
    final messenger = ScaffoldMessenger.of(context);
    try {
      await action();
      if (mounted) {
        ref
          ..invalidate(alertsProvider)
          ..invalidate(activeAlertsCountProvider);
      }
      messenger.showSnackBar(SnackBar(content: Text(successMessage)));
    } catch (error) {
      messenger.showSnackBar(SnackBar(content: Text(errorMessageOf(error))));
    } finally {
      if (mounted) setState(() => _busyAlertIds.remove(alert.id));
    }
  }

  Future<void> _acknowledge(Alert alert) => _runAction(
        alert,
        () => ref.read(alertsRepositoryProvider).acknowledge(alert.id),
        'Alerta reconocida.',
      );

  Future<void> _resolve(Alert alert) async {
    final actionTaken = await showResolveAlertDialog(context, alert);
    if (actionTaken == null) return;
    await _runAction(
      alert,
      () => ref
          .read(alertsRepositoryProvider)
          .resolve(alert.id, actionTaken: actionTaken),
      'Alerta resuelta.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final alerts = ref.watch(alertsProvider(_status));
    final canEdit =
        ref.watch(authControllerProvider).value?.canEdit(AppModule.alerts) ??
            false;

    return Scaffold(
      appBar: AppBar(title: const Text('Alertas')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: SizedBox(
              width: double.infinity,
              child: SegmentedButton<AlertStatus>(
                segments: [
                  for (final status in _filters)
                    ButtonSegment(value: status, label: Text(status.label)),
                ],
                selected: {_status},
                showSelectedIcon: false,
                onSelectionChanged: (selection) =>
                    setState(() => _status = selection.first),
              ),
            ),
          ),
          Expanded(
            child: AsyncValueView<List<Alert>>(
              value: alerts,
              onRetry: () => ref.invalidate(alertsProvider(_status)),
              data: (items) => RefreshIndicator(
                onRefresh: () => ref.refresh(alertsProvider(_status).future),
                child: items.isEmpty
                    ? ListView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        children: [
                          const SizedBox(height: 80),
                          EmptyView(
                            title: _status == AlertStatus.active
                                ? 'Todo en orden'
                                : 'No hay alertas ${_status.label.toLowerCase()}',
                            message: _status == AlertStatus.active
                                ? 'No hay alertas activas en este momento.'
                                : null,
                            icon: Icons.verified_outlined,
                          ),
                        ],
                      )
                    : ListView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                        children: [
                          ResponsiveGrid(
                            itemCount: items.length,
                            minItemWidth: 420,
                            maxColumns: 2,
                            itemBuilder: (context, index) {
                              final alert = items[index];
                              return AlertCard(
                                alert: alert,
                                canEdit: canEdit,
                                isBusy: _busyAlertIds.contains(alert.id),
                                onAcknowledge: () => _acknowledge(alert),
                                onResolve: () => _resolve(alert),
                              );
                            },
                          ),
                        ],
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class AlertCard extends StatelessWidget {
  const AlertCard({
    super.key,
    required this.alert,
    required this.canEdit,
    required this.isBusy,
    required this.onAcknowledge,
    required this.onResolve,
  });

  final Alert alert;
  final bool canEdit;
  final bool isBusy;
  final VoidCallback onAcknowledge;
  final VoidCallback onResolve;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final palette = alert.severity.level.palette(context);
    final showActions =
        canEdit && (alert.canBeAcknowledged || alert.canBeResolved);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(left: BorderSide(color: palette.accent, width: 5)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  StatusChip(
                    label: 'Severidad ${alert.severity.label.toLowerCase()}',
                    level: alert.severity.level,
                  ),
                  StatusChip(label: alert.typeLabel, level: StatusLevel.neutral),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                [alert.pondName, if (alert.parameterName != null) alert.parameterName!]
                    .join(' · '),
                style: theme.textTheme.titleSmall,
              ),
              const SizedBox(height: 4),
              Text(alert.message, style: theme.textTheme.bodyMedium),
              const SizedBox(height: 6),
              Text(
                [
                  Formatters.dateTime(alert.createdAt),
                  if (alert.triggerValue != null)
                    'Valor: ${Formatters.number(alert.triggerValue)}',
                ].join(' · '),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              if (alert.actionTaken != null) ...[
                const SizedBox(height: 8),
                Text(
                  'Acción tomada: ${alert.actionTaken}',
                  style: theme.textTheme.bodySmall,
                ),
              ],
              if (showActions) ...[
                const SizedBox(height: 12),
                if (isBusy)
                  const LinearProgressIndicator()
                else
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    alignment: WrapAlignment.end,
                    children: [
                      if (alert.canBeAcknowledged)
                        OutlinedButton.icon(
                          onPressed: onAcknowledge,
                          icon: const Icon(Icons.visibility_outlined),
                          label: const Text('Reconocer'),
                        ),
                      if (alert.canBeResolved)
                        FilledButton.icon(
                          onPressed: onResolve,
                          icon: const Icon(Icons.task_alt),
                          label: const Text('Resolver'),
                        ),
                    ],
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
