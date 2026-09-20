import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/env.dart';
import '../../../core/network/providers.dart';
import '../data/monitoring_repository.dart';
import '../data/reading.dart';

final monitoringRepositoryProvider = Provider<MonitoringRepository>(
  (ref) => MonitoringRepository(ref.watch(apiClientProvider)),
);

/// Últimas lecturas con polling.
///
/// - `autoDispose`: al salir de la pantalla se cancela el temporizador.
/// - Riverpod 3 pausa los providers de widgets que no están visibles,
///   así que no se consulta la API desde pestañas ocultas.
/// - Durante el refresco se conservan los datos anteriores en pantalla.
final latestReadingsProvider =
    FutureProvider.autoDispose.family<List<Reading>, int>((ref, pondId) {
  final timer = Timer(Env.pollingInterval, ref.invalidateSelf);
  ref.onDispose(timer.cancel);
  return ref.watch(monitoringRepositoryProvider).fetchLatestReadings(pondId);
});

/// Rango de tiempo para el historial.
enum HistoryRange {
  day(1, '24 h'),
  week(7, '7 días'),
  month(30, '30 días');

  const HistoryRange(this.days, this.label);

  final int days;
  final String label;
}

/// Clave del historial. Los records comparan por valor, así que sirven
/// como parámetro de `family` sin escribir `==` ni `hashCode`.
typedef HistoryQuery = ({int pondId, int parameterId, HistoryRange range});

final historyProvider =
    FutureProvider.autoDispose.family<List<Reading>, HistoryQuery>((ref, query) {
  final now = DateTime.now();
  return ref.watch(monitoringRepositoryProvider).fetchHistory(
        pondId: query.pondId,
        parameterId: query.parameterId,
        from: now.subtract(Duration(days: query.range.days)),
        to: now,
      );
});
