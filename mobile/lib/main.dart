import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:intl/intl.dart';

import 'app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  Intl.defaultLocale = 'es';
  await initializeDateFormatting('es');

  runApp(
    ProviderScope(
      // Riverpod 3 reintenta por defecto los providers que fallan.
      // Se desactiva: un 401/403 o un servidor caído no se arreglan
      // reintentando en bucle; el usuario decide con el botón "Reintentar".
      retry: (retryCount, error) => null,
      child: const BioAquaApp(),
    ),
  );
}
