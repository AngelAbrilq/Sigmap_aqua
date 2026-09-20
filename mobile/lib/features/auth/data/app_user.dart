import '../../../core/utils/json_parsers.dart';

/// Usuario autenticado con sus permisos por módulo (RBAC del backend).
class AppUser {
  const AppUser({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    this.photoUrl,
    this.visibleModules = const {},
    this.writableModules = const {},
  });

  /// Espera la forma de `GET auth/me/`:
  /// `modulos: {lectura: [...] | "todos", escritura: [...] | "todos"}`.
  factory AppUser.fromJson(Map<String, dynamic> json) {
    final modules = json['modulos'];
    final byAccess = modules is Map ? modules : const {};
    return AppUser(
      id: parseInt(json['id']) ?? 0,
      email: parseString(json['email']) ?? '',
      fullName: parseString(json['nombre_completo']) ?? '',
      role: parseString(json['rol']) ?? '',
      photoUrl: parseString(json['foto_perfil']),
      visibleModules: _parseModules(byAccess['lectura']),
      writableModules: _parseModules(byAccess['escritura']),
    );
  }

  final int id;
  final String email;
  final String fullName;
  final String role;
  final String? photoUrl;

  /// `null` significa acceso total (Instructor Líder).
  final Set<String>? visibleModules;
  final Set<String>? writableModules;

  bool canView(String module) =>
      visibleModules == null || visibleModules!.contains(module);

  /// Escribir implica poder ver: la escritura es subconjunto de la lectura.
  bool canEdit(String module) =>
      canView(module) &&
      (writableModules == null || writableModules!.contains(module));

  String get initials {
    final parts = fullName.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty);
    if (parts.isEmpty) return '?';
    return parts.take(2).map((part) => part[0].toUpperCase()).join();
  }

  /// Si el backend no envía la clave, se niega el acceso (falla segura).
  static Set<String>? _parseModules(Object? raw) => switch (raw) {
        'todos' => null,
        final List<dynamic> modules => modules.map((m) => '$m').toSet(),
        _ => const <String>{},
      };
}
