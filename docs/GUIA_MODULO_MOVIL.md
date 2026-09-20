# Guía del Módulo Móvil — SIGMAP-AQUA / BioAqua System

> Documento técnico de referencia para construir la app móvil (Flutter/Dart) que consume el backend Django de SIGMAP-AQUA.
> Stack objetivo: **Flutter 3.44+ / Dart 3.12+** · **Django 5.2 + DRF 3.17 + SimpleJWT 5.5** · **MySQL**.

---

## 1. Descripción

La app móvil permite a Instructor Líder, Operario y Aprendiz consultar desde el celular el estado de las geomembranas, las lecturas de los sensores, el historial, las alertas y las predicciones de IA, respetando la misma matriz de roles (RBAC) de la versión web.

### 1.1 Diagnóstico del repositorio actual (importante)

| Hallazgo | Consecuencia para el móvil |
|---|---|
| La web se sirve con **templates Django** (HTML renderizado en servidor). | Flutter **no puede consumir HTML**. Hay que exponer una **API REST JSON** para usuarios. |
| La única API existente es `/api/v1/` para los **ESP32** (`Authorization: Device <token>`). | No sirve para personas. Se crea un espacio nuevo: `/api/v1/movil/` con **JWT**. |
| `djangorestframework_simplejwt` ya está en `requirements.txt` y en `DEFAULT_AUTHENTICATION_CLASSES`, pero **no hay endpoints de login JWT** ni `SIMPLE_JWT` configurado. | Se agrega la configuración y los endpoints `token/`, `refresh/`, `logout/`. |
| `django-cors-headers` está instalado pero **no** está en `INSTALLED_APPS`. | Una app nativa (Android/iOS) **no necesita CORS**. Solo se activa si compilan también Flutter Web. |
| `apps/usuarios/permissions.py` ya tiene `puede_ver_modulo()` y `puede_editar_modulo()`. | Se **reutilizan** en una clase de permiso DRF → mismo RBAC en web y móvil (DRY). |
| `apps/monitoreo/views.py` ya tiene el helper `respuesta(success, data, message)`. | Se mueve a un módulo común y se usa en toda la API móvil. |
| La lógica de `reconocer`/`resolver` alerta vive en `apps/alertas/views.py`. | Se extrae a `apps/alertas/services.py` para que web y API llamen la misma función. |

**Conclusión:** el trabajo tiene **dos frentes**, y el primero es el backend:

1. **Backend (Django):** API REST para la app → `apps/api_movil/`.
2. **Frontend (Flutter):** proyecto en la carpeta `mobile/`.

---

## 2. ¿Hay que crear una carpeta `mobile/`? — Sí

Monorepo: el backend y la app viven en el mismo repositorio, cada uno con su propia raíz.

```
Sigmap_aqua/
├── apps/
│   ├── api_movil/          ← NUEVO: API REST para la app (Django)
│   ├── alertas/  monitoreo/  piscinas/  usuarios/  ia/  reportes/  core/
├── config/
├── firmware/               ← ESP32
├── mobile/                 ← NUEVO: proyecto Flutter (flutter create)
├── templates/  static/  tests/
├── docs/
│   └── GUIA_MODULO_MOVIL.md
└── manage.py
```

Ventajas: un solo PR puede cambiar endpoint + pantalla; el equipo ve todo en un solo repo. Flutter genera su propio `.gitignore` dentro de `mobile/`, así que `build/` y `.dart_tool/` no se suben.

> ⚠️ No mezclar `pubspec.yaml` con la raíz de Django. Todo lo de Dart vive **dentro** de `mobile/`.

---

## 3. Requerimientos

### 3.1 Funcionales (MVP)

| ID | Requerimiento | Roles |
|---|---|---|
| RFM-01 | Iniciar / cerrar sesión con correo y contraseña (JWT). | Todos |
| RFM-02 | Ver listado de geomembranas con su estado general. | Todos |
| RFM-03 | Ver últimas lecturas por parámetro (T°, pH, O₂, turbidez) de una geomembrana, con color según rango. | Todos |
| RFM-04 | Consultar historial de lecturas con filtros (parámetro, rango de fechas) y gráfica. | Todos |
| RFM-05 | Ver alertas activas; **reconocer** y **resolver** alertas. | Ver: todos · Acciones: Instructor, Operario |
| RFM-06 | Ver notificaciones y marcarlas como leídas. | Todos |
| RFM-07 | Ver predicciones de IA vigentes por geomembrana. | Todos |
| RFM-08 | Perfil del usuario autenticado (nombre, rol, foto). | Todos |

Fase 2: CRUD de geomembranas/sensores desde el móvil, notificaciones push (FCM), modo offline, comparación de periodos.

### 3.2 No funcionales

- **Responsive:** celular vertical/horizontal y tablet (breakpoints en §6.4).
- **Seguridad:** JWT de corta duración + refresh rotativo con blacklist; tokens en almacenamiento cifrado del sistema; HTTPS en producción.
- **Rendimiento:** listados paginados; sin consultas N+1 en el backend (`select_related`/`prefetch_related`).
- **Accesibilidad:** áreas táctiles ≥ 48 dp, contraste AA, `Semantics` en indicadores, soporte de escala de texto del sistema.
- **Consistencia:** todas las respuestas `{success, data, message}`.

---

## 4. Flujo general

```
┌────────────┐  POST /auth/token/   ┌────────────────────┐
│  App Flutter│ ───────────────────▶ │ Django API móvil    │
│             │ ◀── access+refresh ─ │ (DRF + SimpleJWT)   │
│  Dio + Auth │                      │                     │
│  interceptor│  GET /geomembranas/  │  PermisoModulo      │──▶ puede_ver_modulo()
│             │ ── Bearer access ──▶ │  (RBAC existente)   │──▶ puede_editar_modulo()
│             │                      │                     │
│  401? ──────┼─ POST /auth/refresh/▶│  rota refresh       │
│  reintenta  │ ◀── nuevo access ─── │  blacklist anterior │
└────────────┘                      └─────────┬──────────┘
                                              │ ORM
    ESP32 ── POST /api/v1/lecturas/ ──▶  MySQL sigmap_agua
```

Tiempo real (MVP): la app hace **polling** de últimas lecturas cada 30–60 s solo mientras la pantalla está visible. Los sensores reportan cada ~300 s (`intervalo_lectura_segundos`), así que un intervalo menor no aporta datos nuevos. Fase 2: push con FCM para alertas críticas.

---

## 5. Backend: API REST para la app (`apps/api_movil`)

### 5.1 Contrato de endpoints

Base: `/api/v1/movil/`

| Método | Ruta | Descripción | Módulo RBAC |
|---|---|---|---|
| POST | `auth/token/` | Login `{email, password}` → `{access, refresh, usuario}` | — (público, con throttling) |
| POST | `auth/refresh/` | `{refresh}` → nuevo `{access, refresh}` | — |
| POST | `auth/logout/` | `{refresh}` → lo invalida (blacklist) | autenticado |
| GET | `auth/me/` | Perfil + rol + módulos permitidos | autenticado |
| GET | `geomembranas/` | Listado paginado | `geomembranas` |
| GET | `geomembranas/{id}/` | Detalle | `geomembranas` |
| GET | `geomembranas/{id}/ultimas-lecturas/` | Última lectura por parámetro | `monitoreo` |
| GET | `lecturas/?geomembrana=&parametro=&desde=&hasta=` | Historial paginado | `historial` |
| GET | `alertas/?estado=activa&geomembrana=` | Alertas | `alertas` |
| POST | `alertas/{id}/reconocer/` | Reconocer | `alertas` (escritura) |
| POST | `alertas/{id}/resolver/` | `{accion_tomada}` | `alertas` (escritura) |
| GET | `notificaciones/` · POST `notificaciones/leidas/` | Bandeja del usuario | autenticado |
| GET | `predicciones/?geomembrana=` | Predicciones vigentes | `ai` |

Formato estándar:

```json
{ "success": true, "data": { ... }, "message": "Operación exitosa" }
{ "success": false, "data": { "email": ["Este campo es obligatorio."] }, "message": "Datos inválidos" }
```

### 5.2 Configuración (`config/settings.py`)

```python
from datetime import timedelta

INSTALLED_APPS += [
    'rest_framework_simplejwt.token_blacklist',  # logout real + rotación segura
    'apps.api_movil',
    # 'corsheaders',  # SOLO si compilan Flutter Web
]

REST_FRAMEWORK.update({
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'apps.api_movil.excepciones.manejador_errores',
    'DEFAULT_THROTTLE_RATES': {'login': '5/min'},
})

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

Luego: `python manage.py migrate` (crea las tablas del blacklist).

> El `EXCEPTION_HANDLER` es global: afecta también la API de ESP32. Después de activarlo, correr `python manage.py test tests.test_ingesta_alertas` para confirmar que el firmware sigue recibiendo lo esperado.

### 5.3 Estructura del app

```
apps/api_movil/
├── __init__.py
├── apps.py
├── respuestas.py        # respuesta() compartido (movido desde monitoreo/views.py)
├── excepciones.py       # manejador global → {success, data, message}
├── permisos.py          # PermisoModulo (reutiliza RBAC existente)
├── serializers.py       # salida JSON para la app
├── views/
│   ├── auth.py
│   ├── geomembranas.py
│   ├── lecturas.py
│   ├── alertas.py
│   └── predicciones.py
└── urls.py
```

### 5.4 Piezas clave

**`permisos.py`** — el mismo RBAC de la web:

```python
"""Permiso DRF que reutiliza la matriz RBAC de apps.usuarios.permissions."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.usuarios.permissions import puede_editar_modulo, puede_ver_modulo


class PermisoModulo(BasePermission):
    """
    La vista declara `modulo = '<url_name>'`.
    GET/HEAD/OPTIONS exigen lectura; POST/PUT/PATCH/DELETE exigen escritura.
    """
    message = 'Tu rol no tiene permiso para esta acción.'

    def has_permission(self, request, view):
        usuario = request.user
        if not usuario.is_authenticated or usuario.estado != 'activo':
            return False
        modulo = getattr(view, 'modulo', None)
        if modulo is None:
            return True
        if request.method in SAFE_METHODS:
            return puede_ver_modulo(usuario, modulo)
        return puede_editar_modulo(usuario, modulo)
```

**`excepciones.py`**:

```python
"""Unifica los errores de DRF al formato {success, data, message}."""
from rest_framework.views import exception_handler


def manejador_errores(exc, context):
    """
    Envuelve la respuesta de error por defecto de DRF.

    :param exc: excepción lanzada
    :param context: contexto de la vista
    :return: Response con formato estándar, o None (error 500 no controlado)
    """
    respuesta = exception_handler(exc, context)
    if respuesta is None:
        return None
    detalle = respuesta.data
    mensaje = detalle.get('detail', 'Datos inválidos') if isinstance(detalle, dict) else 'Error'
    respuesta.data = {
        'success': False,
        'data': None if 'detail' in (detalle if isinstance(detalle, dict) else {}) else detalle,
        'message': str(mensaje),
    }
    return respuesta
```

**`views/auth.py`** — login con datos del rol en el token:

```python
"""Autenticación JWT para la app móvil."""
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.usuarios.permissions import MODULOS_POR_ROL, obtener_nombre_rol

from ..respuestas import respuesta
from ..serializers import UsuarioMovilSerializer


class LoginSerializer(TokenObtainPairSerializer):
    """Login por email (USERNAME_FIELD). Rechaza cuentas inactivas."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = obtener_nombre_rol(user)
        return token

    def validate(self, attrs):
        datos = super().validate(attrs)
        if self.user.estado != 'activo':
            raise AuthenticationFailed('La cuenta está inactiva.')
        datos['usuario'] = UsuarioMovilSerializer(self.user).data
        return datos


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        base = super().post(request, *args, **kwargs)
        return respuesta(True, base.data, 'Inicio de sesión exitoso')


class PerfilView(APIView):
    """Datos del usuario + módulos visibles, para armar el menú en la app."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rol = obtener_nombre_rol(request.user)
        modulos = MODULOS_POR_ROL.get(rol)
        datos = UsuarioMovilSerializer(request.user).data
        datos['modulos'] = 'todos' if modulos is None else sorted(modulos or [])
        return respuesta(True, datos, 'Perfil')
```

**Últimas lecturas sin N+1** (una sola consulta con subquery, usa el índice existente `geomembrana, -timestamp_lectura`):

```python
from django.db.models import Max, Subquery

ultimos_ids = (Lectura.objects
               .filter(geomembrana_id=pk)
               .values('tipo_parametro')
               .annotate(ultimo=Max('id'))
               .values('ultimo'))
lecturas = (Lectura.objects
            .filter(id__in=Subquery(ultimos_ids))
            .select_related('tipo_parametro', 'sensor'))
```

**`urls.py`** y registro en `config/urls.py`:

```python
# apps/api_movil/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .views import alertas, auth, geomembranas, lecturas, predicciones

app_name = 'api_movil'
router = DefaultRouter()
router.register('geomembranas', geomembranas.GeomembranaViewSet, basename='geomembranas')
router.register('alertas', alertas.AlertaViewSet, basename='alertas')

urlpatterns = [
    path('auth/token/', auth.LoginView.as_view(), name='token'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('auth/logout/', TokenBlacklistView.as_view(), name='logout'),
    path('auth/me/', auth.PerfilView.as_view(), name='perfil'),
    path('lecturas/', lecturas.HistorialLecturasView.as_view(), name='lecturas'),
    path('predicciones/', predicciones.PrediccionesView.as_view(), name='predicciones'),
    path('', include(router.urls)),
]

# config/urls.py  (ANTES de la línea de api/v1/ de los ESP32)
path('api/v1/movil/', include('apps.api_movil.urls')),
```

### 5.5 Índices recomendados (MySQL)

Ya existen: `lecturas_sensores(geomembrana, -timestamp_lectura)`, `(sensor, -timestamp_lectura)`, `alertas(estado, -fecha_generacion)`, `alertas(geomembrana, estado)`, `notificaciones_push(usuario, leida, -fecha_creacion)`.

Agregar para el historial filtrado por parámetro:

```python
models.Index(fields=['geomembrana', 'tipo_parametro', '-timestamp_lectura'],
             name='idx_lect_geo_param_ts')
```

Verificar con:

```sql
EXPLAIN SELECT id, valor_medida, timestamp_lectura
FROM lecturas_sensores
WHERE geomembrana_id = 1 AND tipo_parametro_id = 2
  AND timestamp_lectura BETWEEN '2026-09-01' AND '2026-09-17'
ORDER BY timestamp_lectura DESC LIMIT 20;
-- Esperado: type=range, key=idx_lect_geo_param_ts, sin "Using filesort"
```

### 5.6 Probar la API antes de tocar Flutter

```powershell
python manage.py runserver 0.0.0.0:8000
curl -X POST http://127.0.0.1:8000/api/v1/movil/auth/token/ -H "Content-Type: application/json" -d "{\"email\":\"lider@sena.edu.co\",\"password\":\"...\"}"
curl http://127.0.0.1:8000/api/v1/movil/geomembranas/ -H "Authorization: Bearer <access>"
```

> Regla: **no se empieza una pantalla Flutter si su endpoint no responde bien en curl/Postman.**

---

## 6. Frontend: proyecto Flutter (`mobile/`)

### 6.1 Instalación y creación

1. Instalar Flutter SDK (canal stable), Android Studio (SDK + emulador) y la extensión Flutter de VS Code.
2. `flutter doctor` → todo en verde (Android toolchain, licencias: `flutter doctor --android-licenses`).
3. Desde la raíz del repo:

```powershell
flutter create --org co.edu.sena.bioaqua --project-name sigmap_aqua_mobile --platforms android,ios mobile
cd mobile
flutter pub add dio flutter_riverpod go_router flutter_secure_storage fl_chart intl json_annotation freezed_annotation
flutter pub add --dev build_runner json_serializable freezed mocktail
```

| Paquete | Para qué |
|---|---|
| `dio` | Cliente HTTP con interceptores (equivale a la instancia base de Axios). |
| `flutter_riverpod` | Estado global y caché de peticiones, fácil de testear. |
| `go_router` | Navegación declarativa + redirección si no hay sesión (rutas protegidas). |
| `flutter_secure_storage` | Guarda tokens en **Android Keystore / iOS Keychain**. |
| `fl_chart` | Gráficas de historial. |
| `freezed` + `json_serializable` | Modelos inmutables y `fromJson` generado (tipado fuerte). |
| `mocktail` | Mocks para tests. |

> Sobre tokens: en web la regla es httpOnly cookies, nunca localStorage. En móvil el equivalente seguro es **Keystore/Keychain vía `flutter_secure_storage`**. Nunca `shared_preferences` para tokens.

### 6.2 Arquitectura: feature-first + capas

```
mobile/lib/
├── main.dart
├── app.dart                         # MaterialApp.router + tema
├── core/
│   ├── config/env.dart              # API_URL por --dart-define
│   ├── network/
│   │   ├── api_client.dart          # Dio base + interceptores
│   │   ├── auth_interceptor.dart    # Bearer + refresh automático en 401
│   │   └── api_response.dart        # parsea {success, data, message}
│   ├── storage/token_storage.dart
│   ├── router/app_router.dart       # go_router + guardias por sesión/rol
│   ├── theme/app_theme.dart         # colores de estado: normal/riesgo/crítico
│   └── widgets/                     # componentes reutilizables
│       ├── responsive_scaffold.dart
│       ├── estado_chip.dart
│       └── vista_error.dart
└── features/
    ├── auth/
    │   ├── data/        (auth_repository.dart, models/usuario.dart)
    │   └── presentation/(login_page.dart, auth_controller.dart)
    ├── geomembranas/    (data/ + presentation/)
    ├── monitoreo/       (últimas lecturas, polling)
    ├── historial/       (filtros + fl_chart)
    ├── alertas/
    ├── notificaciones/
    └── predicciones/
```

Regla de dependencias: `presentation → data → core`. **Los widgets nunca llaman a Dio directamente**: widget → provider (Riverpod) → repository → `ApiClient`.

### 6.3 Código base

**`core/config/env.dart`**

```dart
/// URL base de la API. Se inyecta al compilar:
/// flutter run --dart-define=API_URL=http://192.168.1.50:8000/api/v1/movil
class Env {
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1/movil', // emulador Android → PC
  );
}
```

**`core/network/api_client.dart`** (instancia base + interceptor de refresh)

```dart
import 'package:dio/dio.dart';
import '../config/env.dart';
import '../storage/token_storage.dart';

/// Cliente HTTP único de la app. Añade el Bearer y renueva el access
/// token automáticamente cuando el servidor responde 401.
class ApiClient {
  ApiClient(this._storage) {
    dio = Dio(BaseOptions(
      baseUrl: Env.apiUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      headers: {'Accept': 'application/json'},
    ));
    dio.interceptors.add(QueuedInterceptorsWrapper(
      onRequest: (options, handler) async {
        final access = await _storage.leerAccess();
        if (access != null) options.headers['Authorization'] = 'Bearer $access';
        handler.next(options);
      },
      onError: (error, handler) async {
        final esAuth = error.requestOptions.path.contains('/auth/');
        if (error.response?.statusCode != 401 || esAuth) {
          return handler.next(error);
        }
        final renovado = await _renovarToken();
        if (!renovado) {
          await _storage.borrar();
          return handler.next(error); // el router enviará al login
        }
        final reintento = await dio.fetch(error.requestOptions
          ..headers['Authorization'] = 'Bearer ${await _storage.leerAccess()}');
        handler.resolve(reintento);
      },
    ));
  }

  final TokenStorage _storage;
  late final Dio dio;

  Future<bool> _renovarToken() async {
    final refresh = await _storage.leerRefresh();
    if (refresh == null) return false;
    try {
      final r = await Dio(BaseOptions(baseUrl: Env.apiUrl))
          .post('/auth/refresh/', data: {'refresh': refresh});
      await _storage.guardar(access: r.data['access'], refresh: r.data['refresh']);
      return true;
    } on DioException {
      return false;
    }
  }
}
```

**`core/storage/token_storage.dart`**

```dart
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Tokens JWT en Keystore (Android) / Keychain (iOS).
class TokenStorage {
  static const _access = 'access_token';
  static const _refresh = 'refresh_token';
  final _secure = const FlutterSecureStorage();

  Future<void> guardar({required String access, required String refresh}) async {
    await _secure.write(key: _access, value: access);
    await _secure.write(key: _refresh, value: refresh);
  }

  Future<String?> leerAccess() => _secure.read(key: _access);
  Future<String?> leerRefresh() => _secure.read(key: _refresh);
  Future<void> borrar() => _secure.deleteAll();
}
```

**Modelo tipado** (`features/monitoreo/data/models/lectura.dart`)

```dart
import 'package:freezed_annotation/freezed_annotation.dart';
part 'lectura.freezed.dart';
part 'lectura.g.dart';

enum EstadoLectura { normal, riesgo, critico }

@freezed
class Lectura with _$Lectura {
  const factory Lectura({
    required int id,
    required String parametro,
    required String unidad,
    @JsonKey(name: 'valor_medida') required String valorMedida, // Decimal llega como String
    @JsonKey(name: 'estado_lectura') required EstadoLectura estado,
    @JsonKey(name: 'timestamp_lectura') required DateTime timestamp,
  }) = _Lectura;

  factory Lectura.fromJson(Map<String, dynamic> json) => _$LecturaFromJson(json);
}
```

Generar: `dart run build_runner build --delete-conflicting-outputs`.

> DRF serializa `DecimalField` como **string** (`"7.2500"`). Recibirlo como `String` y convertir con `double.parse` solo para graficar evita perder precisión.

### 6.4 Responsive (celular, horizontal y tablet)

Breakpoints Material 3:

| Ancho | Tipo | Navegación | Layout |
|---|---|---|---|
| < 600 dp | Celular | `NavigationBar` inferior | 1 columna |
| 600–839 dp | Tablet chica / horizontal | `NavigationRail` | 2 columnas |
| ≥ 840 dp | Tablet grande | `NavigationRail` extendido | lista + detalle lado a lado |

```dart
/// Cambia la navegación según el ancho disponible.
class ResponsiveScaffold extends StatelessWidget {
  const ResponsiveScaffold({super.key, required this.indice,
      required this.destinos, required this.onCambio, required this.cuerpo});

  final int indice;
  final List<NavigationDestination> destinos;
  final ValueChanged<int> onCambio;
  final Widget cuerpo;

  @override
  Widget build(BuildContext context) {
    final ancho = MediaQuery.sizeOf(context).width;
    if (ancho < 600) {
      return Scaffold(
        body: SafeArea(child: cuerpo),
        bottomNavigationBar: NavigationBar(
          selectedIndex: indice, onDestinationSelected: onCambio, destinations: destinos),
      );
    }
    return Scaffold(
      body: SafeArea(
        child: Row(children: [
          NavigationRail(
            extended: ancho >= 840,
            selectedIndex: indice,
            onDestinationSelected: onCambio,
            destinations: [for (final d in destinos)
              NavigationRailDestination(icon: d.icon, label: Text(d.label))],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: cuerpo),
        ]),
      ),
    );
  }
}
```

Buenas prácticas de UI responsive:

- Grillas con `GridView` + `SliverGridDelegateWithMaxCrossAxisExtent(maxCrossAxisExtent: 320)` para las tarjetas de parámetros: se acomodan solas a 1, 2, 3 o 4 columnas.
- `LayoutBuilder` dentro de cada pantalla cuando el layout depende del espacio del padre, no de la pantalla completa.
- Nunca anchos fijos en píxeles; usar `Expanded`, `Flexible`, `ConstrainedBox(maxWidth: 600)` para formularios.
- No bloquear la orientación; probar en horizontal.
- Colores del estado (normal/riesgo/crítico) + **ícono o texto**, no solo color (accesibilidad).

### 6.5 Menú según rol

Al hacer login, `auth/me/` devuelve `modulos`. La app **oculta** lo que el rol no ve y **deshabilita** acciones de escritura (p. ej. el Aprendiz ve alertas pero sin botón "Resolver"). Aun así, **el backend es la autoridad**: si alguien fuerza la petición, `PermisoModulo` responde 403.

| Módulo | Instructor Líder | Operario | Aprendiz |
|---|---|---|---|
| Geomembranas | Ver/editar | Ver/editar | Ver |
| Monitoreo | Ver | Ver | Ver |
| Historial | Ver | Ver | Ver |
| Alertas | Ver + reconocer/resolver | Ver + reconocer/resolver | Ver |
| IA / predicciones | Ver | Ver | Ver |
| Usuarios | Sí (fase 2) | No | No |

### 6.6 Conexión a Django en desarrollo (Laragon/Windows)

| Dónde corre la app | `API_URL` |
|---|---|
| Emulador Android | `http://10.0.2.2:8000/api/v1/movil` |
| Celular físico (misma WiFi o hotspot 192.168.137.1) | `http://<IP LAN del PC>:8000/api/v1/movil` (ver con `ipconfig`) |
| Simulador iOS (solo macOS) | `http://127.0.0.1:8000/api/v1/movil` |

Checklist:

1. `python manage.py runserver 0.0.0.0:8000` (no solo `127.0.0.1`).
2. Firewall de Windows: permitir el puerto 8000 en red privada.
3. Android bloquea HTTP sin TLS: en **debug** agregar `android:usesCleartextTraffic="true"` en `android/app/src/debug/AndroidManifest.xml` (solo debug, nunca en release).
4. `flutter run --dart-define=API_URL=http://192.168.1.50:8000/api/v1/movil`.

---

## 7. Casos de uso (móvil)

**CU-M01 · Iniciar sesión**
Actor: cualquier rol. Pre: cuenta activa.
1. Ingresa email y contraseña → 2. App llama `POST auth/token/` → 3. Guarda tokens en secure storage → 4. Llama `auth/me/` → 5. Redirige al panel del rol.
Alternos: credenciales inválidas → mensaje del backend; cuenta inactiva → "La cuenta está inactiva"; 6 intentos/min → 429 "Demasiados intentos".

**CU-M02 · Monitorear geomembrana**
1. Selecciona geomembrana → 2. `GET geomembranas/{id}/ultimas-lecturas/` → 3. Tarjeta por parámetro con valor, unidad, hora y color de estado → 4. Refresca cada 60 s mientras la pantalla está activa; pull-to-refresh manual.
Alternos: sin lecturas → estado vacío "Sin datos del sensor"; sin red → banner y botón reintentar.

**CU-M03 · Resolver alerta**
Actor: Operario / Instructor. 1. Abre alerta activa → 2. "Reconocer" → 3. Escribe acción tomada → 4. "Resolver" (`POST alertas/{id}/resolver/`) → 5. Lista se actualiza.
Alterno: Aprendiz → botones no visibles; si fuerza la petición → 403.

**CU-M04 · Consultar historial**
1. Elige parámetro y rango de fechas → 2. `GET lecturas/?...` paginado → 3. Gráfica de línea con bandas de rango normal/riesgo.

---

## 8. Buenas prácticas

**Backend**
- Serializers de la app **separados** de los del ESP32 (distinto consumidor, distinto contrato).
- Vistas delgadas; lógica en `services.py` (reusada por web y API).
- Validar todo query param (`desde`/`hasta` como fecha, `geomembrana` como entero) con un serializer de filtros.
- Nunca devolver `token` de `Dispositivo` ni `password` en ningún serializer.
- Versionar: `/api/v1/movil/`; cambios incompatibles → `v2`.
- Throttling en login; HTTPS en producción; `DEBUG=False`.

**Flutter**
- `const` en todo widget que se pueda; listas con `ListView.builder` (no `ListView(children: [...])` con muchos elementos).
- `ref.watch(provider.select(...))` para reconstruir solo lo necesario (equivalente a `useMemo`/`React.memo`).
- Siempre 3 estados en pantalla: **cargando / error / datos** (`AsyncValue.when`).
- Cancelar el polling en `dispose` / con `ref.onDispose`.
- `flutter analyze` sin warnings; activar `flutter_lints` (viene por defecto).
- Textos de UI centralizados (fase 2: `flutter_localizations`).
- No `print()` en producción: usar `debugPrint` o `logger` solo en debug.

---

## 9. Pruebas

| Capa | Herramienta | Qué cubrir (AAA) |
|---|---|---|
| API Django | `APITestCase` en `tests/test_api_movil.py` | login ok / credenciales malas / cuenta inactiva; Aprendiz recibe 403 al resolver; paginación del historial; token inválido → 401 |
| Repositorios Flutter | `flutter_test` + `mocktail` | parseo de `{success,data,message}`, manejo de 401/500 |
| Widgets | `testWidgets` | login muestra error; tarjetas en 1 columna a 360 dp y 3 columnas a 900 dp |

```powershell
python manage.py test tests.test_api_movil
cd mobile; flutter test
```

---

## 10. Plan de trabajo sugerido

| Sprint | Entregable | Criterio de "hecho" |
|---|---|---|
| 0 | `apps/api_movil` + JWT + `auth/me/` | Login y perfil funcionan en Postman + tests verdes |
| 1 | `mobile/` creado, `ApiClient`, login, router con guardia | Login desde emulador y celular físico |
| 2 | Geomembranas + últimas lecturas + responsive shell | Se ve bien en 360 dp, horizontal y tablet |
| 3 | Alertas (ver/reconocer/resolver) + notificaciones | RBAC verificado con los 3 roles |
| 4 | Historial con gráfica + predicciones IA | Filtros y EXPLAIN revisados |
| 5 | Pulido, accesibilidad, tests, APK release | `flutter build apk --release --dart-define=API_URL=https://...` |

**Git:** rama `feature/app-movil` desde `dev` (o `main` si el equipo aún no usa `dev`). Commits separados por frente:

```
feat(api-movil): agregar autenticacion JWT y perfil para la app
feat(mobile): crear proyecto Flutter con cliente Dio y login
feat(mobile): pantalla de monitoreo responsive por geomembrana
```

---

## 11. Próximos pasos inmediatos

1. Instalar Flutter y dejar `flutter doctor` en verde.
2. Crear `apps/api_movil/` con JWT (§5.2–5.4) y probar login en Postman.
3. `flutter create ... mobile` y montar `core/` (§6.3).
4. Construir la pantalla de login contra la API real.
5. Seguir el plan de sprints de §10.
