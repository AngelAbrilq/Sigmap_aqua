import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_exception.dart';
import '../../../core/widgets/state_views.dart';
import 'auth_controller.dart';

/// Se muestra mientras se restaura la sesión guardada.
class SplashPage extends ConsumerWidget {
  const SplashPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authControllerProvider);

    if (session.hasError && !session.isLoading) {
      return Scaffold(
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: ErrorView(
                  message: errorMessageOf(session.error!),
                  onRetry: () => ref.invalidate(authControllerProvider),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: TextButton(
                  onPressed: () =>
                      ref.read(authControllerProvider.notifier).logout(),
                  child: const Text('Iniciar sesión con otra cuenta'),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return const Scaffold(
      body: LoadingView(message: 'Verificando sesión…'),
    );
  }
}
