import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/alerts/presentation/alerts_page.dart';
import '../../features/auth/data/app_user.dart';
import '../../features/auth/presentation/auth_controller.dart';
import '../../features/auth/presentation/login_page.dart';
import '../../features/auth/presentation/profile_page.dart';
import '../../features/auth/presentation/splash_page.dart';
import '../../features/history/presentation/history_page.dart';
import '../../features/ponds/presentation/pond_detail_page.dart';
import '../../features/ponds/presentation/ponds_page.dart';
import 'app_routes.dart';
import 'home_shell.dart';

/// Enrutador con rutas protegidas: sin sesión solo se puede ver el login.
///
/// La autorización real la hace el backend (403); aquí solo se decide
/// qué pantallas tiene sentido mostrar.
final routerProvider = Provider<GoRouter>((ref) {
  final session = ValueNotifier<AsyncValue<AppUser?>>(const AsyncLoading());
  ref.listen(
    authControllerProvider,
    (previous, next) => session.value = next,
    fireImmediately: true,
  );

  final router = GoRouter(
    initialLocation: AppRoutes.ponds,
    debugLogDiagnostics: kDebugMode,
    refreshListenable: session,
    redirect: (context, state) =>
        _guard(session.value, state.matchedLocation),
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (context, state) => const SplashPage(),
      ),
      GoRoute(
        path: AppRoutes.login,
        builder: (context, state) => const LoginPage(),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            HomeShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.ponds,
                builder: (context, state) => const PondsPage(),
                routes: [
                  GoRoute(
                    path: ':id',
                    redirect: (context, state) =>
                        _pondIdOf(state) == null ? AppRoutes.ponds : null,
                    builder: (context, state) =>
                        PondDetailPage(pondId: _pondIdOf(state)!),
                    routes: [
                      GoRoute(
                        path: 'historial',
                        builder: (context, state) => HistoryPage(
                          pondId: _pondIdOf(state)!,
                          initialParameterId: int.tryParse(
                            state.uri.queryParameters['parametro'] ?? '',
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.alerts,
                builder: (context, state) => const AlertsPage(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.profile,
                builder: (context, state) => const ProfilePage(),
              ),
            ],
          ),
        ],
      ),
    ],
  );

  ref.onDispose(() {
    router.dispose();
    session.dispose();
  });
  return router;
});

int? _pondIdOf(GoRouterState state) =>
    int.tryParse(state.pathParameters['id'] ?? '');

String? _guard(AsyncValue<AppUser?> session, String location) {
  final onSplash = location == AppRoutes.splash;
  final onLogin = location == AppRoutes.login;

  // Mientras se restaura la sesión (o si falló por red) se queda en splash.
  final resolved = session.hasValue && !session.hasError;
  if (!resolved) return onSplash ? null : AppRoutes.splash;

  final isLoggedIn = session.value != null;
  if (!isLoggedIn) return onLogin ? null : AppRoutes.login;
  if (onLogin || onSplash) return AppRoutes.ponds;
  return null;
}
