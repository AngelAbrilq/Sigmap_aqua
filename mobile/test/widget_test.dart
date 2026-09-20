import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sigmap_aqua_mobile/core/widgets/responsive_scaffold.dart';

void main() {
  const destinations = [
    AppDestination(label: 'Geomembranas', icon: Icons.water, selectedIcon: Icons.water),
    AppDestination(label: 'Alertas', icon: Icons.notifications, selectedIcon: Icons.notifications),
  ];

  Future<void> pumpAtWidth(WidgetTester tester, double width) async {
    tester.view
      ..physicalSize = Size(width, 800)
      ..devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        home: ResponsiveScaffold(
          selectedIndex: 0,
          destinations: destinations,
          onDestinationSelected: (_) {},
          body: const Text('contenido'),
        ),
      ),
    );
  }

  testWidgets('celular (360 dp) usa NavigationBar inferior', (tester) async {
    await pumpAtWidth(tester, 360);

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byType(NavigationRail), findsNothing);
  });

  testWidgets('tablet (900 dp) usa NavigationRail extendido', (tester) async {
    await pumpAtWidth(tester, 900);

    expect(find.byType(NavigationBar), findsNothing);
    final rail = tester.widget<NavigationRail>(find.byType(NavigationRail));
    expect(rail.extended, isTrue);
  });
}
