# BioAqua Mobile (SIGMAP-AQUA)

App Flutter para Instructor Líder, Operario y Aprendiz: estado de las geomembranas, lecturas en vivo, historial con gráficas, alertas (reconocer/resolver) y predicciones de IA. Consume la API REST `/api/v1/movil/` del backend Django del mismo repositorio.

## Requisitos

- Flutter estable 3.38 o superior (`flutter --version`) y `flutter doctor` en verde.
- Android Studio con un emulador, o un celular Android con depuración USB.
- Backend Django corriendo con la API móvil (`apps/api_movil`, ver [Contrato de la API](#contrato-de-la-api)).

## Puesta en marcha

```powershell
cd mobile
powershell -ExecutionPolicy Bypass -File .\tool\setup.ps1   # solo la primera vez
```

El script corre `flutter create .` (genera `android/` e `ios/` sin tocar `lib/`, `test/` ni `pubspec.yaml`), agrega el permiso INTERNET, habilita HTTP local solo en debug, instala dependencias y corre `flutter analyze` y `flutter test`.

Backend (en otra terminal, desde la raíz del repo):

```powershell
python manage.py runserver 0.0.0.0:8000
```

Ejecutar la app:

| Dónde | Comando |
|---|---|
| Emulador Android | `flutter run` (usa `http://10.0.2.2:8000/api/v1/movil`) |
| Celular físico | copiar `dart_defines.example.json` a `dart_defines.local.json`, poner la IP LAN del PC (`ipconfig`) y correr `flutter run --dart-define-from-file=dart_defines.local.json` |
| APK de prueba | `flutter build apk --release --dart-define=API_URL=https://tu-servidor/api/v1/movil` |

Si el celular no conecta: firewall de Windows (permitir puerto 8000 en red privada), misma red WiFi o hotspot, y `ALLOWED_HOSTS`/`DEBUG=True` en el `.env`.

## Arquitectura

Feature-first con capas. Los widgets nunca llaman a Dio: widget → provider (Riverpod) → repositorio → `ApiClient`.

```
lib/
├── main.dart                  # ProviderScope + idioma
├── app.dart                   # MaterialApp.router + tema
├── core/
│   ├── config/                # Env (--dart-define), nombres de módulos RBAC
│   ├── network/               # ApiClient (Bearer + refresh), ApiException, parseo {success,data,message}
│   ├── storage/               # TokenStorage (Keystore/Keychain)
│   ├── router/                # go_router: rutas protegidas + pestañas
│   ├── theme/                 # Material 3 + semáforo óptimo/riesgo/crítico
│   ├── utils/                 # Parseo de Decimal/fechas de DRF, formatos es-CO
│   └── widgets/               # ResponsiveScaffold, ResponsiveGrid, StatusChip, vistas de estado
└── features/
    ├── auth/                  # Login, splash, perfil, AuthController
    ├── ponds/                 # Geomembranas: listado y detalle
    ├── monitoring/            # Lecturas (polling) + ReadingCard
    ├── history/               # Historial con fl_chart
    ├── alerts/                # Alertas: filtro, reconocer, resolver
    └── predictions/           # Predicciones de IA
```

| Paquete | Uso |
|---|---|
| `dio` | Cliente HTTP con interceptores |
| `flutter_riverpod` | Estado global y caché de peticiones |
| `go_router` | Navegación con guardias de sesión |
| `flutter_secure_storage` | Tokens JWT cifrados |
| `fl_chart` | Gráficas |
| `intl` | Fechas y números en español |

### Decisiones

- **Tokens**: en Keystore/Keychain con `flutter_secure_storage`, nunca en `shared_preferences`. Es el equivalente móvil a las cookies httpOnly de la web.
- **Refresh automático**: ante un 401, `ApiClient` renueva el access token una vez y reintenta. Si el refresh falla, cierra la sesión y el router lleva al login.
- **RBAC**: `auth/me/` devuelve `modulos` y `modulos_escritura`. La app oculta lo que el rol no ve y los botones que no puede usar (el Aprendiz no ve "Resolver"), pero quien decide es el backend (403).
- **Tiempo real**: polling cada `POLLING_SECONDS` (60 s por defecto) solo en la pantalla visible. Riverpod pausa los providers de pestañas ocultas.
- **Responsive**: `NavigationBar` en menos de 600 dp, `NavigationRail` desde 600 dp y rail extendido desde 840 dp. Las tarjetas se reparten en 1 a 4 columnas según el ancho.
- **Accesibilidad**: el estado nunca se comunica solo con color (ícono + texto), `Semantics` en tarjetas y gráficas, áreas táctiles de 48 dp.

## Contrato de la API

Implementado en `apps/api_movil/` (Django) y probado en `tests/test_api_movil.py`. Si cambias un campo allá, cambia el `fromJson` correspondiente aquí.

Base: `/api/v1/movil/`. Autenticación: `Authorization: Bearer <access>`. Todas las respuestas, incluidos los errores, vienen como `{ "success": bool, "data": ..., "message": str }`. Los listados paginados traen `data = {total, pagina, paginas, resultados}` y aceptan `page_size` (máximo 500).

| Método | Ruta | Cuerpo / query | `data` |
|---|---|---|---|
| POST | `auth/token/` | `{email, password}` | `{access, refresh, usuario}` |
| POST | `auth/refresh/` | `{refresh}` | `{access, refresh}` (rotativo) |
| POST | `auth/logout/` | `{refresh}` | — |
| GET | `auth/me/` | — | usuario + `modulos: {lectura, escritura}` |
| GET | `geomembranas/` | `page_size` | paginado |
| GET | `geomembranas/{id}/` | — | detalle |
| GET | `geomembranas/{id}/ultimas-lecturas/` | — | `{geomembrana, nombre, estado_operativo, alertas_activas, parametros: [...]}` |
| GET | `lecturas/` | `geomembrana, parametro, desde, hasta, estado, page_size` | paginado, más reciente primero |
| GET | `alertas/` | `estado` (por defecto `activa`), `severidad`, `geomembrana` | paginado |
| POST | `alertas/{id}/reconocer/` | — | alerta (409 si ya no está activa) |
| POST | `alertas/{id}/resolver/` | `{accion_tomada}` | alerta |
| GET | `predicciones/` | `geomembrana, estado` | paginado + `precision` |
| GET/POST | `notificaciones/`, `notificaciones/leidas/` | — | bandeja del usuario |

Formas JSON que lee la app (los `Decimal` llegan como texto):

```jsonc
// auth/me/
{ "id": 1, "email": "lider@sena.edu.co", "nombre_completo": "Ana Rojas", "rol": "Instructor Lider",
  "foto_perfil": null, "modulos": { "lectura": "todos", "escritura": ["alertas", "geomembranas"] } }

// geomembranas/ -> resultados[]
{ "id": 1, "nombre_piscina": "Estanque 1", "codigo_identificacion": "GM-01", "ubicacion": "Lote A",
  "estado": "activo", "apta_para_produccion": true, "etapa": "Engorde",
  "estado_operativo": "ok" | "warn" | "crit", "estado_operativo_label": "Óptimo", "alertas_activas": 2 }

// ultimas-lecturas -> parametros[]  (un sensor mudo llega con valor null y "sin_datos")
{ "parametro_id": 2, "parametro": "pH", "unidad": "pH", "sensor": "SEN-PH", "valor_medida": "7.2500",
  "estado_lectura": "normal" | "riesgo" | "critico" | "sin_datos",
  "timestamp_lectura": "2026-09-17T10:00:00-0500", "rango_min": "6.5000", "rango_max": "8.5000" }

// alertas/ -> resultados[]
{ "id": 5, "geomembrana": 1, "piscina": "Estanque 1", "parametro": "Oxígeno disuelto",
  "tipo_alerta": "critico", "severidad": "critica", "estado": "activa",
  "mensaje_alerta": "Oxígeno en 2.1 mg/L", "valor_que_disparo": "2.1000",
  "fecha_generacion": "2026-09-17T10:00:00-0500", "accion_tomada": "" }

// predicciones/ -> resultados[]
{ "id": 3, "parametro": "Temperatura", "unidad": "°C", "valor_esperado": "27.5", "valor_min": "26.8",
  "valor_max": "28.3", "probabilidad_fuera_rango": 35, "fecha_objetivo": "2026-09-20",
  "justificacion": "…", "estado": "pendiente" }
```

## Pruebas

```powershell
flutter test
flutter analyze
```

- `test/core/api_response_test.dart`: parseo del formato estándar y de la paginación.
- `test/features/models_test.dart`: permisos por rol, Decimal como texto, estados desconocidos.
- `test/features/login_page_test.dart`: validación del formulario y error del servidor (repositorio simulado con mocktail).
- `test/widget_test.dart`: navegación responsive a 360 dp y a 900 dp.
