import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/alerts/presentation/alerts_providers.dart';
import '../widgets/responsive_scaffold.dart';

/// Contenedor de las pestañas principales. Cada pestaña conserva su pila
/// de navegación (StatefulShellRoute.indexedStack).
class HomeShell extends ConsumerWidget {
  const HomeShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activeAlerts = ref.watch(activeAlertsCountProvider).value ?? 0;

    return ResponsiveScaffold(
      selectedIndex: navigationShell.currentIndex,
      // Tocar la pestaña activa vuelve a su pantalla inicial.
      onDestinationSelected: (index) => navigationShell.goBranch(
        index,
        initialLocation: index == navigationShell.currentIndex,
      ),
      destinations: [
        const AppDestination(
          label: 'Geomembranas',
          icon: Icons.water_outlined,
          selectedIcon: Icons.water,
        ),
        AppDestination(
          label: 'Alertas',
          icon: Icons.notifications_outlined,
          selectedIcon: Icons.notifications,
          badgeCount: activeAlerts,
        ),
        const AppDestination(
          label: 'Perfil',
          icon: Icons.person_outline,
          selectedIcon: Icons.person,
        ),
      ],
      body: navigationShell,
    );
  }
}
