import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/presentation/auth_controller.dart';
import '../storage/token_storage.dart';
import 'api_client.dart';

final tokenStorageProvider = Provider<TokenStorage>(
  (ref) => const TokenStorage(),
);

final apiClientProvider = Provider<ApiClient>(
  (ref) => ApiClient(
    tokenStorage: ref.watch(tokenStorageProvider),
    // Se lee en el momento del callback (no al construir), así que no
    // crea una dependencia circular con el controlador de sesión.
    onSessionExpired: () =>
        ref.read(authControllerProvider.notifier).onSessionExpired(),
  ),
);
