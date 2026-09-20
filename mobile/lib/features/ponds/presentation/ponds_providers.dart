import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/pond.dart';
import '../data/ponds_repository.dart';

final pondsRepositoryProvider = Provider<PondsRepository>(
  (ref) => PondsRepository(ref.watch(apiClientProvider)),
);

final pondsProvider = FutureProvider.autoDispose<List<Pond>>(
  (ref) => ref.watch(pondsRepositoryProvider).fetchPonds(),
);

final pondProvider = FutureProvider.autoDispose.family<Pond, int>(
  (ref, pondId) => ref.watch(pondsRepositoryProvider).fetchPond(pondId),
);
