# Acta de Constitución del Proyecto (Project Charter)

**SIGMAP-AQUA · BioAqua System**
Sistema automatizado para el monitoreo de parámetros del agua en estanques piscícolas

> Los campos con `________` quedan pendientes de diligenciar. Los valores entre `[CORCHETES]` son supuestos que se deben validar.

---

## 1. Información General

| Campo | Descripción |
|---|---|
| Nombre del proyecto | SIGMAP-AQUA – BioAqua System |
| Código / Ficha | Ficha 3230026 |
| Organización beneficiaria | Centro de Formación Agroindustrial La Angostura – SENA Regional Huila |
| Programa de formación | Tecnólogo en Análisis y Desarrollo de Software |
| Fecha del acta | ________ |
| Patrocinador | ________ |
| Gerente / Líder de proyecto | ________ |
| Equipo de desarrollo | Jhonny Stiven Yunda Guzmán · Yesman Ronaldo Ortega Ávila · Ángel Nicolás Abril Quimbaya · Juan José Gracia Cocomá |
| Fecha de inicio | ________ |
| Duración estimada | ________ |
| Presupuesto / Recursos | ________ |
| Versión del documento | 1.0 |

---

## 2. Propósito y Justificación

### 2.1 Problema

En el área piscícola del Centro de Formación La Angostura, el **pH**, el **oxígeno disuelto** y la **temperatura** del agua se miden de forma manual y esporádica. Esto provoca:

- **Datos imprecisos**, porque cada medición depende de una persona.
- **Detección tardía** de cambios bruscos, como la caída de oxígeno, que puede causar estrés, enfermedad o mortalidad de los peces.
- **Ausencia de registro histórico**, que impide analizar tendencias o evaluar si las acciones correctivas funcionaron.
- **Ausencia de alertas automáticas** cuando un parámetro sale de rango.
- **Decisiones basadas en la experiencia** y no en datos sobre la aptitud de una piscina para siembra o permanencia de peces.

### 2.2 Justificación

| Dimensión | Aporte del proyecto |
|---|---|
| Productiva | Menos riesgo de mortalidad y mejor aprovechamiento de las unidades de cultivo. |
| Tecnológica | Incorpora IoT (sensores + ESP32), una plataforma web y una app móvil en un proceso agroindustrial que hoy es manual. |
| Formativa | Los aprendices aplican competencias de desarrollo, IoT y análisis de datos en un caso real. |
| Ambiental | Supervisión continua del ecosistema acuático y bienestar animal. |
| Decisional | Información confiable, histórica y en tiempo real para actuar a tiempo. |

---

## 3. Objetivos del Proyecto (SMART)

### 3.1 Objetivo General

Desarrollar e implantar, en **[________ meses]**, un sistema web y móvil que automatice al **100 %** el monitoreo de pH, oxígeno disuelto y temperatura en las piscinas del Centro de Formación La Angostura. El sistema debe capturar los datos en tiempo real, conservar su historial y generar alertas para reducir en un **70 %** el riesgo de mortalidad atribuible a condiciones inadecuadas del agua.

### 3.2 Objetivos Específicos

| # | Objetivo | Indicador / Meta | Plazo |
|---|---|---|---|
| OE1 | Implementar la captura automática de datos con sensores conectados a un ESP32 que transmite al servidor. | 100 % de las piscinas piloto reportan lecturas sin intervención manual, a intervalos de **[≤ 1 min]**. | ________ |
| OE2 | Almacenar cada lectura con fecha, hora, parámetro, valor y piscina, sin pérdida de datos durante cortes de red (modo offline). | 0 lecturas perdidas o duplicadas en pruebas de desconexión y reconexión. | ________ |
| OE3 | Generar alertas automáticas y clasificar el estado del agua (óptimo / riesgo / crítico). | Alerta visible en **[≤ 1 ciclo de lectura]** desde que se detecta el valor fuera de rango; 100 % de las alertas registradas en auditoría. | ________ |
| OE4 | Entregar análisis histórico (gráficas, comparación de periodos, exportación) y evaluación de aptitud de cada piscina para producción. | Los 19 RF validados con pruebas automatizadas y aceptación del cliente. | ________ |
| OE5 | Controlar el acceso con una matriz de roles (Administrador/Instructor, Operario, Aprendiz) en la web y en el móvil. | 0 accesos no autorizados en pruebas de seguridad por rol. | ________ |

---

## 4. Alcance de Alto Nivel

### 4.1 In-Scope (Incluido)

1. **Monitoreo en tiempo real:** lectura de sensores de pH, oxígeno disuelto y temperatura, con un panel que se actualiza automáticamente y muestra un semáforo de estado.
2. **Registro y almacenamiento:** las mediciones se guardan en orden cronológico y organizadas por piscina (geomembrana).
3. **Análisis de datos:** gráficas de comportamiento con banda de rango óptimo, comparación entre periodos y exportación a CSV.
4. **Alertas inteligentes:** evaluación automática de cada lectura, apertura y cierre automático de alertas y notificación visual que permanece hasta que el usuario la reconoce.
5. **Evaluación de producción:** indicador de aptitud (apta / no apta) con recomendaciones básicas.
6. **Configuración de rangos óptimos** por parámetro, con validación de coherencia.
7. **Gestión de usuarios y control de acceso por roles (RBAC).**
8. **Auditoría de eventos:** alertas, cambios de configuración, accesos y acciones de usuarios.
9. **Modo offline:** cola local en el microcontrolador y sincronización sin duplicados al restablecerse la conexión.
10. **Detección de sensor caído** o sin transmisión.

### 4.2 Out-of-Scope (Excluido)

| # | Exclusión |
|---|---|
| 1 | ________ |
| 2 | ________ |
| 3 | ________ |
| 4 | ________ |
| 5 | ________ |

---

## 5. Requisitos de Alto Nivel

### 5.1 Tecnológicos

| Capa | Tecnología |
|---|---|
| Backend | Python · Django (arquitectura MVT por apps) |
| Base de datos | MySQL / MariaDB (`sigmap_agua`) |
| Frontend web | HTML5, CSS3, JavaScript; diseño responsive |
| Móvil | Flutter / Dart (Riverpod, go_router) que consume la API REST `/api/v1/movil/` con JWT |
| Hardware / IoT | ESP32 + sensores electroquímicos de pH, OD y temperatura; firmware C/C++ con cola en LittleFS |
| Comunicación | HTTP/HTTPS (TLS), WiFi, intercambio en JSON |
| IA (complementario) | Google Gemini para análisis y predicción de tendencias |
| DevOps | Git / GitHub (Conventional Commits) · [Docker] · servidor [Ubuntu Server 22.04 LTS] |

### 5.2 Funcionales

Se derivan del documento de requerimientos (**RF001–RF019**):

| Módulo | Requisitos |
|---|---|
| M1 · Monitoreo en tiempo real | RF001 Captura de sensores · RF002 Visualización · RF003 Actualización automática |
| M2 · Registro y almacenamiento | RF004 Registro · RF005 Historial · RF006 Organización por piscina |
| M3 · Análisis de datos | RF007 Gráficas · RF008 Comparación de periodos |
| M4 · Alertas inteligentes | RF009 Evaluación · RF010 Alertas · RF011 Clasificación · RF012 Notificación visual |
| M5 · Condiciones de producción | RF013 Aptitud + recomendaciones · RF014 Configuración de rangos |
| Transversal | RF015 Usuarios · RF016 Roles · RF017 Panel general · RF018 Eventos · RF019 Modo offline |

### 5.3 No Funcionales

| ID | Atributo | Criterio |
|---|---|---|
| RNF001 | Rendimiento | Procesar y mostrar las lecturas sin retrasos significativos; consultas indexadas y sin N+1. |
| RNF002 | Disponibilidad | Operativo durante toda la jornada del área piscícola. |
| RNF003 | Seguridad | Autenticación obligatoria, RBAC validado en el servidor, contraseñas con hash, JWT, HTTPS y auditoría. |
| RNF004 | Usabilidad | Interfaz intuitiva para operarios sin formación técnica; código de color verde/amarillo/rojo. |
| RNF005 | Escalabilidad | Agregar piscinas y sensores sin modificar el código. |
| RNF006 | Mantenibilidad | Código modular con pruebas automatizadas. |
| RNF007 | Portabilidad | Funciona en Windows 10+, macOS 11+, Linux, Android 10+ e iOS 14+. |

---

## 6. Cronograma de Hitos (Milestones)

| # | Hito | Entregable | Fecha |
|---|---|---|---|
| H1 | Formulación del proyecto | Propuesta de proyecto formativo | ________ |
| H2 | Análisis de requerimientos | Documento de requerimientos, casos de uso e historias de usuario | ________ |
| H3 | Diseño | Modelo entidad-relación, diccionario de datos, arquitectura IoT, guía visual | ________ |
| H4 | Desarrollo núcleo web (M1–M5) | Backend Django + panel web con los RF001–RF019 | ________ |
| H5 | Integración IoT | Firmware ESP32, ingesta de datos, modo offline y simulador de nodo | ________ |
| H6 | Módulo móvil e IA | App Flutter + API JWT; predicciones con Gemini | ________ |
| H7 | Pruebas y QA | Suite de pruebas automatizadas aprobada y pruebas de aceptación | ________ |
| H8 | Instalación en campo | Cableado y calibración de sensores en las piscinas piloto | ________ |
| H9 | Despliegue en producción | Servidor con HTTPS (certificado + proxy inverso) | ________ |
| H10 | Cierre del proyecto | Entrega final, manuales y sustentación | ________ |

---

## 7. Riesgos Iniciales de Alto Nivel

| ID | Riesgo | Tipo | Prob. | Impacto | Respuesta / Mitigación |
|---|---|---|---|---|---|
| R1 | Deriva o descalibración de los sensores electroquímicos (pH y OD) en el agua, con lecturas erróneas | Técnico | Alta | Alto | Plan de calibración periódica, validación de rangos físicos en la ingesta y detección de sensor caído o anómalo. |
| R2 | Pérdida de conectividad WiFi en la zona de piscinas | Operativo | Media | Alto | Cola local (LittleFS) con reenvío y deduplicación; alerta de nodo sin reporte. |
| R3 | Daño del hardware por humedad, agua o condiciones climáticas | Operativo | Media | Alto | Carcasas IP65+, prensaestopas, repuestos críticos y pruebas previas al despliegue en campo. |
| R4 | Falsas alertas por umbrales mal configurados que generan "fatiga de alertas" | Técnico / Negocio | Media | Medio | Rangos validados con el instructor del área, edición restringida al administrador y auditoría de cambios. |
| R5 | Despliegue sin HTTPS que expone credenciales y tokens | Seguridad | Media | Alto | Certificado TLS, proxy inverso, cabeceras defensivas, `DEBUG=False` y secretos en variables de entorno. |
| R6 | Disponibilidad limitada del equipo (formación paralela) y dependencia del conocimiento de pocos integrantes | Organizacional | Media | Medio | Ramas por integrante, documentación técnica en el repositorio y revisiones cruzadas. |
| R7 | Presupuesto insuficiente para adquirir los sensores | Financiero | ________ | ________ | ________ |

---

## 8. Criterios de Éxito

El proyecto se considera **terminado y exitoso** cuando:

1. Los **19 requerimientos funcionales** (RF001–RF019) y los **7 no funcionales** están implementados y aprobados en la prueba de aceptación del cliente.
2. La suite de pruebas automatizadas se ejecuta **100 % en verde** contra MySQL.
3. Las piscinas piloto transmiten lecturas reales de pH, OD y temperatura de forma continua durante **[7 días]** sin intervención manual.
4. Las pruebas de desconexión no pierden ni duplican ninguna lectura.
5. Toda lectura fuera de rango genera una alerta visible y auditada dentro del ciclo de lectura.
6. Los tres roles (Administrador, Operario, Aprendiz) solo acceden a las funciones permitidas, en web y en móvil.
7. El sistema está desplegado con **HTTPS** y disponible durante la operación del área piscícola.
8. Se entregan el manual de usuario, el manual técnico y el acta de cierre firmada por el patrocinador.

---

## 9. Firmas de Aprobación

| Rol | Nombre | Cargo / Organización | Firma | Fecha |
|---|---|---|---|---|
| Patrocinador | ________ | ________ | ________ | ________ |
| Gerente / Líder de proyecto | ________ | ________ | ________ | ________ |
| Cliente / Usuario líder (Instructor del área) | ________ | ________ | ________ | ________ |
| Equipo de desarrollo | ________ | ________ | ________ | ________ |
| Equipo de desarrollo | ________ | ________ | ________ | ________ |
| Equipo de desarrollo | ________ | ________ | ________ | ________ |
| Equipo de desarrollo | ________ | ________ | ________ | ________ |
