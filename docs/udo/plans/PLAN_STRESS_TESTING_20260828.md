# PLAN — Stress Testing de OpenCode (Fases 0-8)

- **Estado**: GUARDADO, NO ANALIZADO, NO EJECUTADO (2026-08-28)
- **Instrucción de Ramón (2026-08-28)**: guardar este plan para más adelante. NO ejecutar, NO analizar.
  Cuando se vaya a hacer, entonces se analiza (puntos buenos/malos/mejoras) y se decide si merece la pena.
- **Origen**: propuesta de plan de pruebas de estrés con k6 para OpenCode (GX10/Mac).

---

# PLAN DE EJECUCIÓN DETALLADO (FASES 0 A 8)

## FASE 0 — PREPARACIÓN DEL ENTORNO (ÚNICA VEZ)

**Objetivo**: Asegurar que el Asus tiene las herramientas necesarias y que el repositorio está preparado.

**Acciones**:
- Instalar k6 en el Asus (si no está instalado). Es un binario ligero que se descarga con un solo comando.
- Crear la carpeta `tests/stress/` dentro del proyecto `URA/ura_ia_1972/`.
- Definir que todas las pruebas usarán la IP de Tailscale (`100.72.103.12`) como endpoint fijo. La IP WiFi (`10.164.1.247`) se usará solo como alternativa.
- Verificar que los servicios de OpenCode (web, API, worker) están activos y responden a las IPs definidas.
- Responsable: Puedes hacerlo tú o delegar en OpenCode mediante una tarea UDO.

**Verificación**: `k6 --version` debe devolver la versión instalada.

## FASE 1 — DEFINIR ESCENARIOS DE PRUEBA (MÍNIMO 4)

**Objetivo**: Crear guiones (scripts) que simulen el uso real de OpenCode.

**Escenarios a cubrir**:

| Escenario | Descripción | Métricas clave |
|-----------|-------------|----------------|
| Chat simulado | 50 usuarios conversando simultáneamente con el modelo `qwen3-coder:30b-mejorado`. Piden análisis de código y respuestas estructuradas (`[ANÁLISIS]`). | Latencia P95, tasa de fallos, checks de contenido. |
| API REST | Consultas al estado de los servicios (`/api/status`), lista de modelos (`/api/tags`), y lanzamiento de tareas simples. | Tiempo de respuesta, tasa de errores HTTP. |
| WebSockets | Simular 30 conexiones persistentes (como las que usa la interfaz web). Enviar pings y recibir pongs. | Tiempo de conexión, tasa de mensajes recibidos. |
| Orquestación | Lanzar tareas que activen el worker y el rotador de modelos (model-router). Simular 10 tareas concurrentes. | Tiempo de ejecución de tareas, uso de colas. |

**Acciones**:
- Crear un archivo por escenario dentro de `tests/stress/scenarios/`.
- Cada archivo debe definir:
  - El número de usuarios virtuales (VUs) y la rampa de carga (aumento progresivo).
  - Los umbrales específicos para ese escenario (latencia máxima, tasa de fallos).
  - Las comprobaciones (checks) que validan que la respuesta es correcta (ej: que contiene `[ANÁLISIS]`).
- Responsable: Puedes pedir a OpenCode que genere estos escenarios automáticamente describiéndole el comportamiento deseado.

## FASE 2 — CONFIGURAR UMBRALES DE RENDIMIENTO (SLOs)

**Objetivo**: Establecer límites claros de rendimiento que, si se superan, harán fallar la prueba.

**Umbrales base propuestos**:

| Métrica | Umbral (SLO) | Severidad |
|---------|--------------|-----------|
| Latencia P95 de chat | < 500 ms | Crítico |
| Tasa de fallos HTTP | < 1% | Crítico |
| Tiempo de conexión WebSocket P95 | < 1 s | Alto |
| Tiempo de ejecución de tarea P95 | < 10 s | Medio |
| Uso de CPU en Asus durante carga | < 80% | Crítico |
| Uso de RAM en Asus durante carga | < 75% | Crítico |

**Acciones**:
- Crear un archivo `tests/stress/config/thresholds.json` con estos valores.
- Los umbrales se aplicarán automáticamente a cada escenario.
- Deben poder ajustarse fácilmente en el futuro (si las pruebas muestran que son demasiado estrictos o permisivos).
- Responsable: Puedes definirlos tú basándote en la experiencia, o pedir a OpenCode que los sugiera tras ejecutar una prueba de referencia.

## FASE 3 — CREAR EL ORQUESTADOR DE PRUEBAS (SCRIPT EJECUTOR)

**Objetivo**: Escribir un programa (ejecutable) que:
- Ejecute la prueba canary (1 usuario, 10 segundos). Si falla, detiene todo.
- Si la canary funciona, ejecuta los 4 escenarios uno tras otro.
- Guarda los resultados en una carpeta con fecha y hora.
- Al final, genera un resumen que indica si el sistema está "VERDE" (todo ok) o "ROJO" (algún umbral falló).
- Al terminar (tanto si hay éxito como si hay fallo), ejecuta una limpieza post-prueba para cerrar conexiones y vaciar colas temporales.

**Acciones**:
- Crear un script `tests/stress/run-stress.sh` (ejecutable) que contenga esta lógica.
- Asegurarse de que puede ejecutarse desde cualquier máquina (Asus o Mac) sin dependencias externas más que k6.
- Responsable: OpenCode puede generar este script siguiendo las instrucciones del plan.

## FASE 4 — INTEGRACIÓN CON EL SISTEMA (EJECUCIÓN AUTOMÁTICA PROGRAMADA)

**Objetivo**: Hacer que el orquestador se ejecute automáticamente sin intervención humana.

**Frecuencias definidas**:

| Cuándo | Motivo |
|--------|--------|
| Cada noche a las 3:00 AM | Para detectar degradaciones silenciosas sin interrumpir el trabajo. |
| Cada vez que se fusiona una rama a main | Para detectar regresiones de rendimiento inmediatamente. |
| Manual, bajo demanda | Para lanzar pruebas puntuales si se sospecha de algún problema. |

**Acciones**:
- Configurar un cron en el Asus para ejecutar `bash tests/stress/run-stress.sh` a las 3 AM diarias.
- Añadir un paso en el pipeline de CI/CD (ej: GitHub Actions) que ejecute las pruebas después de cada merge a main (usando la IP de Tailscale).
- Crear un "skill" en OpenCode que permita lanzar las pruebas con una orden como "ejecuta pruebas de estrés ahora".
- Responsable: OpenCode puede modificar el archivo de CI/CD y crear el skill, pero la configuración del cron en el Asus puede requerir acción manual (sudo).

## FASE 5 — SISTEMA DE LIMPIEZA Y RECUPERACIÓN

**Objetivo**: Garantizar que las pruebas no dejen residuos que degraden el sistema.

**Acciones**:
- Pre-limpieza (antes de empezar):
  - Vaciar la cola de tareas de prueba (si existe).
  - Cerrar conexiones WebSocket abiertas de ejecuciones anteriores.
  - Matar cualquier proceso zombi relacionado con pruebas previas.
- Post-limpieza (después de terminar):
  - Cerrar todas las conexiones WebSocket abiertas durante la prueba.
  - Matar procesos zombis que pueda haber dejado el worker de prueba.
  - Restaurar el estado del worker de producción (si se usó uno específico para pruebas).
  - Eliminar logs y archivos temporales generados por la prueba.
- Responsable: El orquestador debe incluir estas fases de limpieza. OpenCode puede supervisar que se ejecuten correctamente.

## FASE 6 — DOCUMENTACIÓN DEL SISTEMA

**Objetivo**: Dejar registro claro de cómo funciona el sistema de pruebas de estrés para que cualquier persona (o agente de OpenCode) pueda entenderlo y mantenerlo.

**Documento a crear**: `docs/architecture/STRESS_TESTING.md`

**Contenido obligatorio**:
- Propósito: Por qué existen estas pruebas y qué validan.
- Escenarios: Descripción de cada uno, qué simula y qué umbrales tiene.
- Ejecución local: Cómo lanzar las pruebas manualmente desde el Asus o el Mac.
- Ejecución automática: Cómo se programan (cron, CI/CD) y cómo se interpretan los resultados.
- Interpretación de resultados: Qué significa VERDE/ROJO, cómo leer los reportes generados.
- Cómo ajustar umbrales: Explicación de `thresholds.json` y cómo modificarlo.
- Cómo crear nuevos escenarios: Instrucciones para añadir nuevos scripts de prueba.
- Troubleshooting: Problemas comunes y cómo resolverlos (ej: k6 no instalado, IP no accesible, logs llenos).
- Responsable: OpenCode puede redactar este documento basándose en el plan y en los resultados de las pruebas.

## FASE 7 — CREACIÓN DE UN SKILL PARA OPENCODE (MANTENIMIENTO)

**Objetivo**: Permitir que OpenCode gestione las pruebas de estrés con órdenes en lenguaje natural.

**Órdenes a implementar**:

| Orden en lenguaje natural | Acción que ejecuta OpenCode |
|---------------------------|------------------------------|
| "Crea un nuevo escenario de estrés para la nueva función X" | Genera un archivo en `scenarios/` con la estructura base, los parámetros de carga y los checks adecuados. |
| "Ajusta los umbrales de latencia a 600 ms" | Modifica `thresholds.json` y actualiza la documentación. |
| "Ejecuta las pruebas de estrés ahora" | Lanza el orquestador y devuelve el resumen VERDE/ROJO. |
| "Muestra el último reporte de estrés" | Busca el reporte más reciente y lo muestra en el chat. |

**Acciones**:
- Diseñar un "skill" dentro de OpenCode (ej: `stress-manager`) que contenga estas capacidades.
- El skill debe leer los archivos de configuración, generar scripts y ejecutar comandos en el sistema de forma segura.
- Responsable: OpenCode puede crear este skill siguiendo las especificaciones. Tú solo tienes que aprobarlo.

## FASE 8 — VERIFICACIÓN Y PUESTA EN MARCHA

**Objetivo**: Validar que todo funciona correctamente en el entorno real antes de dejarlo automatizado.

**Acciones**:
- Ejecutar una prueba completa en horario no laboral (ej: tarde/noche).
- Verificar que:
  - La canary pasa.
  - Los 4 escenarios se ejecutan sin errores.
  - Los umbrales se cumplen (o, si no se cumplen, se ajustan).
  - La limpieza post-prueba deja el sistema limpio (comprobar que no quedan procesos colgados).
  - El documento final se actualiza con los resultados reales.
- Si todo funciona, configurar la ejecución automática (cron/CI). Si algo falla, ajustar y repetir.
- Responsable: Tú supervisas, OpenCode ejecuta y reporta.

---

## ENTREGABLES FINALES (LO QUE OBTENDRÁS)

| Entregable | Descripción |
|------------|-------------|
| Carpeta `tests/stress/` | Estructura completa con escenarios, configuraciones, librerías y orquestador. |
| 4 escenarios de prueba | Scripts funcionales para chat, API, WebSocket y orquestación. |
| Orquestador | Script ejecutable que lanza la canary, ejecuta los escenarios, genera reportes y ejecuta limpieza. |
| Sistema de programación | Cron en el Asus + pipeline de CI/CD configurados. |
| Documentación | `docs/architecture/STRESS_TESTING.md` completo. |
| Skill de OpenCode | Habilidad para gestionar pruebas de estrés con órdenes en lenguaje natural. |
| Primer informe real | Reporte con métricas y validación del sistema en el entorno real. |

## MANTENIMIENTO Y EVOLUCIÓN FUTURA

- Nuevos escenarios: Si se añaden funcionalidades (ej: nuevas herramientas en el modelo), se crean nuevos scripts usando el skill de OpenCode.
- Ajuste de umbrales: Si el sistema mejora, se endurecen los SLOs. Si empeora, se aflojan temporalmente mientras se investiga.
- Actualización de documentación: Cada cambio debe reflejarse en el documento `STRESS_TESTING.md`.
- Revisión periódica: Cada mes, revisar los reportes acumulados para detectar tendencias (ej: degradación gradual de la latencia).

## CONCLUSIÓN (del plan original)

Este plan es accionable, fiable y mantenible. Cubre todos los fallos detectados en la versión anterior, incorpora mejoras de seguridad, limpieza y automatización, y deja el sistema preparado para que OpenCode pueda gestionarlo de forma autónoma en el futuro.

---

*Guardado por TERM el 2026-08-28 por instrucción de Ramón: pendiente de análisis futuro (puntos buenos/malos/mejoras) antes de decidir su ejecución.*
