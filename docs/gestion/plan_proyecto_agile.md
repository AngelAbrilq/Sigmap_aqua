# PLANTILLA DE PLAN DE PROYECTO AGILE

| | | | |
|---|---|---|---|
| **NOMBRE DEL PROYECTO** | SIGMAP-AQUA (BioAqua System) | **FECHA DE INICIO** | 28/07/2026 |
| **ADMINISTRADOR DEL PROYECTO** | Angel Nicolas Abril Quimbaya | **FECHA DE FINALIZACIÓN** | 19/12/2026 |
| **PROGRESO GENERAL** | **53 %** (100 de 187 puntos de historia completados · corte 15/10/2026) | | |

**RESULTADO DEL PROYECTO**

Sistema automatizado de monitoreo de la calidad del agua (pH, oxígeno disuelto, temperatura y turbidez) en geomembranas piscícolas: nodos ESP32 envían lecturas a una plataforma web Django + MySQL que clasifica el estado del agua, genera alertas, guarda el historial, produce gráficas y reportes, y apoya la toma de decisiones con IA; incluye app móvil Flutter.

**DECLARACIÓN SOBRE EL ALCANCE**

Incluye: captura y envío de datos desde el ESP32 con respaldo sin conexión; recepción, validación y almacenamiento de mediciones; gestión de geomembranas, dispositivos, sensores, calibraciones, rangos y usuarios con control por roles (Administrador, Operario piscícola, Aprendiz); evaluación del estado del agua, alertas y aptitud para producción; panel en tiempo real, historial, gráficas, comparación de periodos, eventos y reportes PDF/Excel; análisis con IA y app móvil. Excluye: control automático de equipos (aireadores, bombas) — las recomendaciones de la IA son solo informativas.

---

| EN RIESGO | NOMBRE DE LA TAREA | TIPO DE CARACTERÍSTICA | RESPONSABLE | PUNTOS DE HISTORIA | INICIO | FINALIZACIÓN | DURACIÓN (días) | ESTADO | COMENTARIOS |
|---|---|---|---|---|---|---|---|---|---|
| **No** | **SPRINT 0 · Arranque, entorno y base de datos (M0)** | | **Angel Abril** | **13** | **28/07/2026** | **05/08/2026** | **9** | **Completado** | **3/3 tareas completadas** |
| No | Estructura Django por apps y entorno (.env, Laragon) | Infra / Seguridad | Angel Abril | 3 | 28/07/2026 | 31/07/2026 | 4 | Completado | Repo GitHub, ramas por integrante |
| No | Modelo de datos MySQL, migraciones y datos iniciales | Backend | Juan José Gracia | 5 | 29/07/2026 | 05/08/2026 | 8 | Completado | Tablas en snake_case; comando cargar_datos_iniciales |
| No | Requerimientos, casos de uso e historias de usuario v8 | Documentación | Equipo | 5 | 28/07/2026 | 05/08/2026 | 9 | Completado | Actualizados al 15-oct-2026 (26 RF / 26 HU) |
| **No** | **SPRINT 1 · Autenticación y roles (M1)** | | **Angel Abril** | **10** | **06/08/2026** | **19/08/2026** | **14** | **Completado** | **2/2 tareas completadas** |
| No | HU 024 · Inicio de sesión y control por roles | Infra / Seguridad | Angel Abril | 5 | 06/08/2026 | 14/08/2026 | 9 | Completado | Login por rol + matriz de permisos; admin nativo bloqueado |
| No | HU 023 · Gestión de usuarios | Backend | Angel Abril | 5 | 10/08/2026 | 19/08/2026 | 10 | Completado | Protege la propia cuenta; correo y documento únicos |
| **Sí** | **SPRINT HW · Prototipo y sensores** | | **Yesman Ortega** | **19** | **01/08/2026** | **26/10/2026** | **87** | **En curso** | **3/4 tareas completadas** |
| Sí | HU 001 · Lectura de sensores en el ESP32 | Hardware / IoT | Yesman Ortega | 8 | 01/08/2026 | 26/10/2026 | 87 | En curso | Firmware 1.2.0 listo (4 sensores); falta prueba en estanque real |
| No | HU 002 · Sincronización de hora (NTP) y paquete JSON | Hardware / IoT | Yesman Ortega | 3 | 01/09/2026 | 19/09/2026 | 19 | Completado | Validar escenario "hora no sincronizada" en campo |
| No | HU 004 · Almacenamiento local ante pérdida de conexión | Hardware / IoT | Yesman Ortega | 5 | 20/09/2026 | 06/10/2026 | 17 | Completado | Cola LittleFS + deduplicación en servidor |
| No | Firmware de calibración y banco de pruebas Wokwi | Hardware / IoT | Yesman Ortega | 3 | 15/09/2026 | 06/10/2026 | 22 | Completado | Incluye guía de hardware y video de instalación |
| **Sí** | **SPRINT 2 · Gestión de geomembranas, sensores y rangos (M2)** | | **Juan José Gracia** | **16** | **20/08/2026** | **02/11/2026** | **75** | **En curso** | **3/4 tareas completadas** |
| No | HU 022 · Gestión de geomembranas | Backend | Angel Abril | 5 | 20/08/2026 | 30/08/2026 | 11 | Completado | Desactiva en vez de borrar si hay lecturas (21 pruebas) |
| No | HU 010 · Configuración de rangos y límites de riesgo | Backend | Juan José Gracia | 3 | 25/08/2026 | 05/09/2026 | 12 | Completado | Valida normal ⊂ riesgo ⊂ crítico y audita el cambio |
| No | CRUD de sensores | Frontend web | Juan José Gracia | 3 | 20/08/2026 | 05/09/2026 | 17 | Completado | Módulo /sensores/ |
| Sí | HU 005 · Gestión de dispositivos ESP32 (módulo web) | Backend | Angel Abril | 5 | 01/09/2026 | 02/11/2026 | 63 | Atrasado | Modelo y token listos; falta CRUD web y regenerar token |
| **No** | **SPRINT 3 · Ingesta de lecturas, firmware y simulador (M3)** | | **Angel Abril** | **18** | **06/09/2026** | **02/11/2026** | **58** | **En curso** | **2/5 tareas completadas** |
| No | HU 008 · Registro y almacenamiento de mediciones | Backend | Angel Abril | 3 | 06/09/2026 | 12/09/2026 | 7 | Completado | Dedup por (sensor, timestamp) |
| No | HU 003 · Envío por HTTP POST con token | Hardware / IoT | Yesman Ortega | 5 | 06/09/2026 | 26/10/2026 | 51 | En curso | Falta devolver el intervalo en cada respuesta de ingesta |
| No | HU 007 · Validación de los datos recibidos | Backend | Angel Abril | 5 | 10/09/2026 | 02/11/2026 | 54 | En curso | Faltan eventos de falla de sensor, hora estimada y descartados |
| No | HU 011 · Configuración del intervalo de lectura | Backend | Angel Abril | 3 | 15/09/2026 | 26/10/2026 | 42 | En curso | Editable por sensor; falta límites y envío en ingesta |
| No | Simulador de nodo ESP32 | Hardware / IoT | Angel Abril | 2 | 15/09/2026 | 19/09/2026 | 5 | Completado | firmware/tools/simular_nodo.py |
| **No** | **SPRINT 4 · Estado del agua, alertas y eventos (M4)** | | **Juan José Gracia** | **17** | **20/09/2026** | **05/10/2026** | **16** | **Completado** | **5/5 tareas completadas** |
| No | HU 012 · Evaluación y clasificación del estado del agua | Backend | Juan José Gracia | 3 | 20/09/2026 | 25/09/2026 | 6 | Completado | Óptimo / riesgo / crítico + historial |
| No | HU 013 · Generación de alertas | Backend | Juan José Gracia | 5 | 20/09/2026 | 30/09/2026 | 11 | Completado | Sin alertas repetidas; cierre al normalizarse |
| No | HU 009 · Detección de pérdida de comunicación | Backend | Juan José Gracia | 3 | 25/09/2026 | 05/10/2026 | 11 | Completado | Falta programar la ejecución periódica |
| No | HU 019 · Evaluación de aptitud para producción | Backend | Juan José Gracia | 3 | 28/09/2026 | 05/10/2026 | 8 | Completado | Recomendaciones por parámetro |
| No | HU 020 · Historial de eventos del sistema | Backend | Juan José Gracia | 3 | 20/09/2026 | 05/10/2026 | 16 | Completado | App auditoria /eventos/ |
| **No** | **SPRINT 5 · Dashboard web (M5)** | | **Jhonny Yunda** | **34** | **06/10/2026** | **31/10/2026** | **26** | **En curso** | **6/11 tareas completadas** |
| No | HU 014 · Panel de control en tiempo real | Frontend web | Jhonny Yunda | 5 | 06/10/2026 | 12/10/2026 | 7 | Completado | Refresco automático; mejoras de UI del 7-oct |
| No | HU 015 · Notificación y reconocimiento de alertas | Frontend web | Jhonny Yunda | 3 | 06/10/2026 | 12/10/2026 | 7 | Completado | Aprendiz sin opción de reconocer |
| No | HU 016 · Consulta del historial de mediciones | Frontend web | Jhonny Yunda | 3 | 06/10/2026 | 12/10/2026 | 7 | Completado | Paginación + CSV |
| No | HU 017 · Gráficas de comportamiento | Frontend web | Jhonny Yunda | 3 | 06/10/2026 | 12/10/2026 | 7 | Completado | Chart.js |
| No | HU 018 · Comparación de datos por periodos | Frontend web | Juan José Gracia | 3 | 06/10/2026 | 12/10/2026 | 7 | Completado | Promedio, mínimo y máximo |
| No | HU 026 · Análisis de datos con IA (Gemini) | Backend | Angel Abril | 5 | 06/10/2026 | 12/10/2026 | 7 | Completado | Fase futura adelantada: diagnóstico y predicciones |
| No | Diagramas UML (clase y ER listos) | Documentación | Angel Abril | 3 | 06/10/2026 | 31/10/2026 | 26 | En curso | Faltan CU, actividades, secuencia, componentes, despliegue y paquetes |
| No | Pulido de interfaz y prueba en navegadores | Frontend web | Jhonny Yunda | 3 | 13/10/2026 | 26/10/2026 | 14 | En curso | Chrome, Firefox, Edge y Safari |
| No | Refresco configurable del panel | Frontend web | Jhonny Yunda | 1 | 20/10/2026 | 26/10/2026 | 7 | Sin iniciar | Hoy fijo en 15 s |
| No | Tareas programadas: sensores caídos y predicciones | Infra / Seguridad | Juan José Gracia | 2 | 20/10/2026 | 26/10/2026 | 7 | Sin iniciar | cron / Programador de tareas |
| No | HU 025 · Recuperación de contraseña | Infra / Seguridad | Angel Abril | 3 | 20/10/2026 | 26/10/2026 | 7 | Sin iniciar | Requiere SMTP en .env |
| **Sí** | **SPRINT 6 · Aplicación móvil y reportes (M6)** | | **Jhonny Yunda** | **31** | **27/10/2026** | **16/11/2026** | **21** | **En curso** | **1/5 tareas completadas** |
| No | App Flutter: login JWT, monitoreo, historial, alertas y predicciones | App móvil | Jhonny Yunda | 8 | 27/10/2026 | 05/11/2026 | 10 | Completado | Adelantada; consume /api/v1/movil/ |
| No | Notificaciones push y APK release | App móvil | Jhonny Yunda | 5 | 03/11/2026 | 16/11/2026 | 14 | Sin iniciar | Pruebas en dispositivo real |
| No | HU 021 · Reportes en PDF y Excel | Backend | Juan José Gracia | 5 | 27/10/2026 | 09/11/2026 | 14 | En curso | Hoy solo CSV |
| No | Notificaciones externas para alertas críticas | Backend | Juan José Gracia | 5 | 03/11/2026 | 16/11/2026 | 14 | Sin iniciar | Push, correo o WhatsApp |
| Sí | HU 006 · Gestión de calibraciones de sensores | Backend | Yesman Ortega | 8 | 27/10/2026 | 09/11/2026 | 14 | Sin iniciar | Requisito nuevo de la v8; no existe el módulo |
| **Sí** | **SPRINT 7 · Integración, despliegue y pruebas (M7)** | | **Angel Abril** | **19** | **17/11/2026** | **30/11/2026** | **14** | **En curso** | **1/5 tareas completadas** |
| Sí | Docker + despliegue en Ubuntu Server | Infra / Seguridad | Angel Abril | 5 | 17/11/2026 | 23/11/2026 | 7 | Sin iniciar | restart: always |
| No | HTTPS con proxy inverso y certificado | Infra / Seguridad | Angel Abril | 3 | 17/11/2026 | 23/11/2026 | 7 | Sin iniciar | Definir conexión de los ESP32 |
| No | Pruebas de rendimiento y carga | Backend | Equipo | 3 | 24/11/2026 | 30/11/2026 | 7 | Sin iniciar | < 1 s ingesta, < 2 s gráficas |
| Sí | Pruebas de integración en campo y con usuarios | Hardware / IoT | Equipo | 5 | 24/11/2026 | 30/11/2026 | 7 | Sin iniciar | Nodo → backend → web → app |
| No | Suite de pruebas automatizadas (190 tests) | Backend | Angel Abril | 3 | 17/11/2026 | 30/11/2026 | 14 | Completado | Adelantada: en verde desde el 6-oct |
| **No** | **SPRINT 8 · Documentación y sustentación (M8)** | | **Equipo** | **10** | **01/12/2026** | **19/12/2026** | **19** | **Sin iniciar** | **0/4 tareas completadas** |
| No | Manual de usuario | Documentación | Equipo | 3 | 01/12/2026 | 12/12/2026 | 12 | Sin iniciar |  |
| No | Manual técnico y de despliegue | Documentación | Equipo | 3 | 01/12/2026 | 12/12/2026 | 12 | Sin iniciar |  |
| No | ERD, diccionario y lineamientos actualizados | Documentación | Angel Abril | 2 | 01/12/2026 | 12/12/2026 | 12 | Sin iniciar | Corregir PHP → Django y nivel de agua → turbidez |
| No | Sustentación final | Documentación | Equipo | 2 | 13/12/2026 | 19/12/2026 | 7 | Sin iniciar |  |

---

## Resumen por estado

| ESTADO | TAREAS | PUNTOS |
|---|---|---|
| Sin iniciar | 14 | 50 |
| En curso | 7 | 32 |
| Completado | 26 | 100 |
| Necesita revisión | 0 | 0 |
| Aprobado | 0 | 0 |
| Atrasado | 1 | 5 |
| En espera | 0 | 0 |
| **Total** | **48** | **187** |


## Resumen de pendientes (corte 15/10/2026)

Solo sprints con tareas en curso, sin iniciar o atrasadas. El detalle de cada tarea está en la tabla principal (columna ESTADO).

| EN RIESGO | SPRINT | | RESPONSABLE | PUNTOS | INICIO | FIN | DÍAS | ESTADO | PENDIENTES |
|---|---|---|---|---|---|---|---|---|---|
| **Sí** | **SPRINT HW · Prototipo y sensores** | | **Yesman Ortega** | **8** | **01/08/2026** | **26/10/2026** | **87** | **En curso** | **1 pendiente(s)** |
| **Sí** | **SPRINT 2 · Gestión de geomembranas, sensores y rangos (M2)** | | **Juan José Gracia** | **5** | **01/09/2026** | **02/11/2026** | **63** | **En curso** | **1 pendiente(s)** |
| **No** | **SPRINT 3 · Ingesta de lecturas, firmware y simulador (M3)** | | **Angel Abril** | **13** | **06/09/2026** | **02/11/2026** | **58** | **En curso** | **3 pendiente(s)** |
| **No** | **SPRINT 5 · Dashboard web (M5)** | | **Jhonny Yunda** | **12** | **06/10/2026** | **31/10/2026** | **26** | **En curso** | **5 pendiente(s)** |
| **Sí** | **SPRINT 6 · Aplicación móvil y reportes (M6)** | | **Jhonny Yunda** | **23** | **27/10/2026** | **16/11/2026** | **21** | **En curso** | **4 pendiente(s)** |
| **Sí** | **SPRINT 7 · Integración, despliegue y pruebas (M7)** | | **Angel Abril** | **16** | **17/11/2026** | **30/11/2026** | **14** | **Sin iniciar** | **4 pendiente(s)** |
| **No** | **SPRINT 8 · Documentación y sustentación (M8)** | | **Equipo** | **10** | **01/12/2026** | **19/12/2026** | **19** | **Sin iniciar** | **4 pendiente(s)** |

**Total pendiente: 22 tareas · 87 puntos de historia.**

## Referencias desplegables

| SÍ / NO | PRIORIDAD | ESTADO |
|---|---|---|
| Sí | Bajo | Sin iniciar |
| No | Medio | En curso |
|  | Alto | Completado |
|  |  | Necesita revisión |
|  |  | Aprobado |
|  |  | Atrasado |
|  |  | En espera |

> Fuentes: repositorio Sigmap_aqua (rama main, 190 pruebas en verde), Requerimientos_Sigmap_Aqua (15/10/2026), Historias_de_Usuario_Sigmap_Aqua_v8 y tablero Trello "BioAqua System Analisis". Puntos de historia estimados en escala Fibonacci.
