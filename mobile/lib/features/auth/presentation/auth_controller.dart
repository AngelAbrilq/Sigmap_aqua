import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';
import '../data/app_user.dart';
import '../data/auth_repository.dart';

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(
    ref.watch(apiClientProvider),
    ref.watch(tokenStorageProvider),
  ),
);

/// Sesión actual: `AsyncData(null)` = sin sesión; `AsyncData(user)` = activa.
final authControllerProvider =
    AsyncNotifierProvider<AuthController, AppUser?>(AuthController.new);

class AuthController extends AsyncNotifier<AppUser?> {
  @override
  Future<AppUser?> build() => ref.read(authRepositoryProvider).restoreSession();

  /// Lanza [ApiException] si falla; el formulario muestra el mensaje.
  /// No pasa el estado a "cargando" para no sacar al usuario del login.
  Future<void> login({required String email, required String password}) async {
    await _awaitInitialBuild();
    final user = await ref
        .read(authRepositoryProvider)
        .login(email: email, password: password);
    state = AsyncData(user);
  }

  Future<void> logout() async {
    await ref.read(authRepositoryProvider).logout();
    state = const AsyncData(null);
  }

  /// Llamado por [ApiClient] cuando el refresh token ya no sirve.
  void onSessionExpired() {
    if (state.value != null) state = const AsyncData(null);
  }

  /// Evita que la restauración inicial pise el resultado de un login.
  Future<void> _awaitInitialBuild() async {
    try {
      await future;
    } catch (_) {
      // Si la restauración falló, el login igual puede continuar.
    }
  }
}
