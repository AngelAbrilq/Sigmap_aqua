import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/env.dart';
import '../../../core/network/providers.dart';
import '../data/alert.dart';
import '../data/alerts_repository.dart';

final alertsRepositoryProvider = Provider<AlertsRepository>(
  (ref) => AlertsRepository(ref.watch(apiClientProvider)),
);

final alertsProvider =
    FutureProvider.autoDispose.family<List<Alert>, AlertStatus>(
  (ref, status) => ref.watch(alertsRepositoryProvider).fetchAlerts(status: status),
);

/// Contador del badge; se refresca con el mismo intervalo que las lecturas.
final activeAlertsCountProvider = FutureProvider.autoDispose<int>((ref) {
  final timer = Timer(Env.pollingInterval, ref.invalidateSelf);
  ref.onDispose(timer.cancel);
  return ref.watch(alertsRepositoryProvider).countActive();
});
