import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:sigmap_aqua_mobile/core/network/api_exception.dart';
import 'package:sigmap_aqua_mobile/features/auth/data/auth_repository.dart';
import 'package:sigmap_aqua_mobile/features/auth/presentation/auth_controller.dart';
import 'package:sigmap_aqua_mobile/features/auth/presentation/login_page.dart';

class _MockAuthRepository extends Mock implements AuthRepository {}

void main() {
  late _MockAuthRepository repository;

  setUp(() {
    repository = _MockAuthRepository();
    when(() => repository.restoreSession()).thenAnswer((_) async => null);
  });

  Future<void> pumpLogin(WidgetTester tester) => tester.pumpWidget(
        ProviderScope(
          overrides: [authRepositoryProvider.overrideWithValue(repository)],
          child: const MaterialApp(home: LoginPage()),
        ),
      );

  testWidgets('valida campos vacíos sin llamar a la API', (tester) async {
    await pumpLogin(tester);

    await tester.tap(find.text('Iniciar sesión'));
    await tester.pump();

    expect(find.text('Ingresa tu correo.'), findsOneWidget);
    expect(find.text('Ingresa tu contraseña.'), findsOneWidget);
    verifyNever(
      () => repository.login(
        email: any(named: 'email'),
        password: any(named: 'password'),
      ),
    );
  });

  testWidgets('muestra el mensaje del servidor si las credenciales fallan',
      (tester) async {
    when(
      () => repository.login(
        email: any(named: 'email'),
        password: any(named: 'password'),
      ),
    ).thenThrow(
      const ApiException('Correo o contraseña incorrectos.', statusCode: 401),
    );
    await pumpLogin(tester);

    await tester.enterText(find.byType(TextFormField).at(0), 'op@sena.edu.co');
    await tester.enterText(find.byType(TextFormField).at(1), 'clave-mala');
    await tester.tap(find.text('Iniciar sesión'));
    await tester.pumpAndSettle();

    expect(find.text('Correo o contraseña incorrectos.'), findsOneWidget);
  });
}
