import 'package:flutter/material.dart';

import 'breakpoints.dart';

/// Destino de navegación principal.
class AppDestination {
  const AppDestination({
    required this.label,
    required this.icon,
    required this.selectedIcon,
    this.badgeCount = 0,
  });

  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final int badgeCount;
}

/// Cambia la navegación según el ancho disponible:
/// - `< 600 dp`: [NavigationBar] inferior.
/// - `600–839 dp`: [NavigationRail] compacto.
/// - `>= 840 dp`: [NavigationRail] extendido con etiquetas.
class ResponsiveScaffold extends StatelessWidget {
  const ResponsiveScaffold({
    super.key,
    required this.selectedIndex,
    required this.destinations,
    required this.onDestinationSelected,
    required this.body,
  });

  final int selectedIndex;
  final List<AppDestination> destinations;
  final ValueChanged<int> onDestinationSelected;
  final Widget body;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;

    if (Breakpoints.isCompact(width)) {
      return Scaffold(
        body: body,
        bottomNavigationBar: NavigationBar(
          selectedIndex: selectedIndex,
          onDestinationSelected: onDestinationSelected,
          destinations: [
            for (final destination in destinations)
              NavigationDestination(
                label: destination.label,
                icon: _BadgedIcon(destination.icon, destination.badgeCount),
                selectedIcon:
                    _BadgedIcon(destination.selectedIcon, destination.badgeCount),
              ),
          ],
        ),
      );
    }

    final extended = Breakpoints.isExpanded(width);
    return Scaffold(
      body: Row(
        children: [
          SafeArea(
            right: false,
            child: NavigationRail(
              extended: extended,
              labelType: extended
                  ? NavigationRailLabelType.none
                  : NavigationRailLabelType.all,
              selectedIndex: selectedIndex,
              onDestinationSelected: onDestinationSelected,
              leading: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Icon(
                  Icons.water_drop,
                  color: Theme.of(context).colorScheme.primary,
                  semanticLabel: 'BioAqua',
                ),
              ),
              destinations: [
                for (final destination in destinations)
                  NavigationRailDestination(
                    label: Text(destination.label),
                    icon: _BadgedIcon(destination.icon, destination.badgeCount),
                    selectedIcon: _BadgedIcon(
                      destination.selectedIcon,
                      destination.badgeCount,
                    ),
                  ),
              ],
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(child: body),
        ],
      ),
    );
  }
}

class _BadgedIcon extends StatelessWidget {
  const _BadgedIcon(this.icon, this.count);

  final IconData icon;
  final int count;

  @override
  Widget build(BuildContext context) {
    if (count <= 0) return Icon(icon);
    return Badge.count(count: count, child: Icon(icon));
  }
}
