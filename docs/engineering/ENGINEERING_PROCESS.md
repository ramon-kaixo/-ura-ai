<!-- Engineering Process v1.9 -->

# ENGINEERING PROCESS — Metodología Universal de Ingeniería para Agentes

**Versión**: 1.9 (2026-08-12) · **Estado**: activo · **Fuente de verdad**: este archivo (git)

> **La regla más importante**: un plan nunca se ejecuta directamente sin análisis previo. Cuando un agente recibe un plan, lo interpreta como *propuesta de trabajo pendiente de revisión técnica*, no como orden ciega de programación.

## 1. Ciclo de trabajo

```
INTENCIÓN HUMANA → PLAN → CONTEXTO → ANÁLISIS CRÍTICO → OMISIONES/RIESGOS/CONTRADICCIONES
→ PROPUESTAS DE MEJORA → PLAN REVISADO → AUTORIZACIÓN/DECISIÓN → EJECUCIÓN → REVISIÓN
→ CORRECCIÓN → VALIDACIÓN → CIERRE
```

La preparación del trabajo forma parte del trabajo de ingeniería.

## 2. Qué debe recibir el agente

PLAN + INTENCIÓN + CONTEXTO + ESTADO ACTUAL + OBJETIVO + MÍNIMOS + PUNTOS CRÍTICOS + RESTRICCIONES + QUÉ NO HACER + VALIDACIÓN + CRITERIOS DE CIERRE.
Si falta información importante, el agente debe detectarlo.

## 3. Las 10 obligaciones del agente (antes de ejecutar)

1. **Entender la intención**: qué quiere el usuario, por qué, qué problema resuelve, qué resultado debe existir. Distinguir *objetivo real* de *método propuesto*.
2. **Leer el plan completo**: todos los capítulos, anexos, restricciones, dependencias, mínimos, criterios de cierre, pendientes, exclusiones.
3. **Reconstruir el contexto**: estado de Git, arquitectura, código relacionado, documentación, ADRs, planes anteriores, closeouts, decisiones, tests, configuración, dependencias, restricciones conocidas.
4. **Inspeccionar el código real**: ¿existe? ¿funciona así? ¿se usa? ¿hay consumidores? ¿hay restricciones que el plan desconoce? No asumir que el plan describe bien el proyecto.
5. **Buscar lo que falta**: requisitos ausentes, archivos no contemplados, tests faltantes, casos extremos, errores de integración, concurrencia, seguridad, operación, incompatibilidades. Responder: "El plan dice A, B y C, pero para que A funcione falta D."
6. **Buscar contradicciones**: plan vs código vs documentación vs decisiones anteriores. Ej.: API modificable vs contrato congelado; fase que usa funcionalidad de otra fase.
7. **Buscar riesgos**: funcionales, seguridad, concurrencia, recursos, arquitectura, operación, mantenimiento.
8. **Buscar casos extremos**: agente parado, otro agente trabajando, misma zona, tarea a medias, commit fallido, proceso desaparecido, secreto faltante, repo sucio, reanudación, información antigua, planes contradictorios. El comportamiento degradado se diseña, no aparece por accidente.
9. **Detectar trabajo prematuro**: cada plan indica FASE ACTUAL y FASES POSTERIORES. Si hay trabajo de fase futura: señalarlo, NO implementarlo automáticamente.
10. **Buscar mejoras**: "¿Existe una forma más sencilla, segura, mantenible o fiable de conseguir el mismo objetivo?" Sin ampliar el alcance sin control.

## 4. Clasificación de descubrimientos

Todo descubrimiento se clasifica (obligatorio — ver `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md`):

| Clase | Definición |
|-------|------------|
| **OBLIGATORIO** | Sin resolverlo no se cumple el objetivo. |
| **NECESARIO** | No estaba explícito pero es necesario para que la solución sea correcta. |
| **MEJORA** | Aumenta calidad; el objetivo se cumple sin ella. |
| **DESCUBRIMIENTO** | Problema relevante hallado durante la investigación; queda registrado. |
| **PENDIENTE** | Debe resolverse posteriormente. |
| **FUERA DE ALCANCE** | No debe tocarse ahora. |

Regla: no convertir cada descubrimiento en trabajo nuevo.

## 5. Partes obligatorias de todo plan

- **MÍNIMOS OBLIGATORIOS**: condiciones que sí o sí se cumplen. Si un mínimo no puede cumplirse, no se declara el trabajo terminado.
- **PUNTOS CRÍTICOS / INVARIANTES**: trazabilidad, contexto, seguridad, compatibilidad, reversibilidad, contratos, documentación, integridad, ausencia de regresiones.
- **COMPORTAMIENTO ESPERADO**: cómo se comporta el sistema después del cambio (no solo qué archivos tocar).
- **NO HACER**: zonas que no tocar, funcionalidades que no implementar, fases que no adelantar, dependencias que no introducir, decisiones que no cambiar, mejoras no autorizadas.
- **VALIDACIÓN y CRITERIOS DE CIERRE**: cómo se demuestra que está terminado.

## 6. Anti-sobreingeniería y reutilización

- Buscar la solución **más sencilla que cumpla todos los mínimos y puntos críticos**.
- NO crear bases de datos, servicios, APIs, capas, agentes, colas o paneles si un mecanismo existente resuelve el problema (complejidad justificada).
- Antes de crear algo nuevo: buscar si ya existe, si puede reutilizarse o extenderse, si hay una herramienta estándar del proyecto.

## 7. Análisis del plan y veredicto

Antes de ejecutar, el agente produce el **ANÁLISIS DEL PLAN** (ver `PLAN_REVIEW_TEMPLATE.md`): qué entiende, qué comprobó, qué coincide, qué falta, contradicciones, riesgos, casos extremos, qué cambiaría, qué no tocaría, qué es obligatorio/opcional, qué pertenece a otra fase, plan corregido, valoración.

Termina con un veredicto:
- **GO**: suficientemente sólido para ejecutar.
- **GO CON CAMBIOS**: hay modificaciones que incorporar antes.
- **NO-GO**: existe un problema que impide ejecutar correctamente.

El veredicto es una valoración técnica para que el humano decida; **no** es autorización automática. La autoridad sobre el alcance es del coordinador humano.

## 8. Ejecución

```
PLAN APROBADO → RESERVAS → EJECUCIÓN → COMMITS → VALIDACIÓN
```

- Durante la ejecución se sigue buscando problemas.
- Problema nuevo: clasificar → ¿bloquea? sí → resolver/detener; no → ¿necesario? sí → incorporar; no → documentar.
- Zonas de trabajo identificadas (reservas UDO). Si se descubre una dependencia necesaria fuera de reserva: parar, informar, actualizar reserva antes de modificar.
- Conflicto detectado ≠ conflicto resuelto: no tocar zona ajena; informar, esperar o pedir autorización explícita. `--force` es excepción auditada.

## 9. Roles (preparador / ejecutor / revisor)

- Modelo: PREPARADOR → EJECUTOR → REVISOR → CORRECCIÓN → VALIDACIÓN. El ejecutor no certifica solo su trabajo.
- Actualmente: OpenCode Web = programador principal; OpenCode Terminal = revisor. Son **roles por tarea**, no dependencias arquitectónicas.
- Futuro (2×Terminal o sin Web): los roles se alternan (A programa / B revisa; B programa / A revisa). La infraestructura no cambia.
- Mecanismo concreto: **UDO** (`scripts/pro/ura-udo`): estados PLANNED → IN_PROGRESS → REVIEW → DONE; gate de integridad F2.2 (commits registrados, pinning de SHAs, árbol limpio); `--revisor`; **AUTO-REVISIÓN** automática si revisor ausente o == ejecutor. No se finge una revisión que no ocurrió.
- Degradación: si el revisor no está disponible, la tarea queda PENDIENTE DE REVISIÓN o usa AUTO-REVISIÓN marcada; nunca se inventa la revisión.
- **Revisión diferida (B1, PLAN 1)**: cuando una tarea se cierra con AUTO-REVISIÓN (revisor idle o inexistente), se registra en `docs/udo/review-pending.md`. Al cerrar una fase, el lote de tareas pendientes se revisa en bloque (revisión cruzada por el otro agente o por el humano). **Una fase no se cierra con el lote sin revisar o sin aceptación explícita de Ramón** (decisión humana, nunca automática). Las tareas revisadas se marcan en el archivo con fecha + revisor + veredicto.
- Preparar trabajo para otro agente implica transmitir: intención, plan, contexto, mínimos, puntos críticos, restricciones, NO HACER, archivos afectados, reservas, estado, commits relevantes, problemas encontrados, decisiones tomadas. Nunca "el otro ya sabe lo que estoy haciendo".

## 10. Trazabilidad y memoria

- Cada trabajo es reconstruible: PLAN → TAREA → RESERVA → CAMBIOS → COMMIT → VALIDACIÓN → REVISIÓN → CIERRE.
- Responder siempre: qué se pidió, qué se hizo, quién, qué commit, quién revisó, qué pruebas pasaron, qué problemas aparecieron, qué quedó pendiente.
- Memoria = Git + documentación + decisiones + planes + closeouts. NO depende de conversaciones ni memoria implícita del LLM. La conversación sirve para interactuar; la documentación para recordar.
- No crear bases de datos que dupliquen tareas/commits/estados/revisiones/decisiones.

## 11. Reglas globales de OpenCode

La metodología llega a todo agente OpenCode por:
1. `AGENTS.md` del proyecto → sección "Metodología universal" (puntero a este documento).
2. `~/.config/opencode/AGENTS.md` (global de usuario) → copia de `deploy/engineering/AGENTS.md.global`.
3. Comprobación: `scripts/pro/ura-engineering-check` (versión, presencia, checksum, sincronización).

Fuente única: el repo (git). Web y Terminal comparten binario/home/config; el check garantiza que ambas copias coinciden.

**Reinicio tras instalar/actualizar (A4)**: la config de opencode se carga al arrancar, NO es hot-reload. Tras instalar o actualizar `~/.config/opencode/AGENTS.md`, los servicios en ejecución (p.ej. `opencode.service`, puerto 8081) no tienen la metodología cargada hasta reiniciarse. Acción obligatoria tras cada instalación: `systemctl restart opencode.service` (puede requerir sudo — F14-F01) y verificar con `ura-engineering-check`. Si no se puede reiniciar, marcarlo explícitamente como PENDIENTE, nunca asumir que la Web "ya aplica" la metodología.

**Instalación en Mac (A5)**: la metodología vive en el repo (git). En Mac (`/Users/ramonesnaola/URA/ura_ia_1972/`) la copia global se instala igual: `cp deploy/engineering/AGENTS.md.global ~/.config/opencode/AGENTS.md`. `ura-engineering-check` en Mac avisa si falta (instalación equivalente, sin máquina-específica). La fuente única sigue siendo el repo (git); la sincronización Mac↔ASUS es el flujo habitual (scp/rsync).

## 11bis. Comprobación previa del entorno (A3)

Antes de empezar una sesión de trabajo: `ura-engineering-check --env`. Comprueba rootfs rw/ro, servicios críticos (opencode, model-router, ollama, ura-api), secretos, disco y git. Resultado OK / OK CON WARNINGS / FAIL. El entorno degradado se detecta ANTES de trabajar, no durante.

## 12. Versionado y mejora continua

- Cabecera `<!-- Engineering Process vX.Y -->` + changelog en este archivo.
- Tras cada problema importante: PROBLEMA → ANÁLISIS → ¿es fallo del proceso? → SI → mejorar metodología. No se modifica la metodología por incidentes aislados; se exige evidencia de valor (ver `docs/engineering/POSTMORTEMS.md`).
- Bump + reinstalar AGENTS.md global + verificar con `ura-engineering-check` + commit.

## 12bis. Proporcionalidad del análisis (B4)

El análisis previo debe ser proporcional al riesgo del plan:
- **Plan trivial** (cosmético, doc, refactor pequeño): análisis breve (5-10 líneas).
- **Plan complejo** (arquitectura, cambios en contratos, fases completas): análisis completo (ANÁLISIS DEL PLAN + veredicto).
El objetivo es que el proceso no entorpezca el trabajo simple ni trate a la ligera el trabajo de riesgo. En el closeout se anota el tiempo de análisis vs ejecución como métrica de coste del proceso.

## 13. Compatibilidad y portabilidad

Esta metodología no depende de: modelo concreto, Qwen, OpenCode Web/Terminal, Ollama ni una máquina concreta. Vive en git; se instala copiando un archivo (AGENTS.md global). Portable por diseño.

## 14. Anti-alucinación: verificación obligatoria antes de afirmar (v1.2)

**Origen**: TASK-20260811-003 — una instancia de OpenCode (TERM, Web en Mac :8091) generó informes detallados de trabajo (plan de 47 problemas, commits, TASK, reservas) que no existían en Git: ningún archivo creado, ningún commit, ningún expediente. La conversación afirmaba con checkmarks; Git desmentía todo. Lección: **creer ≠ hacer; decir ≠ verificar**.

Reglas (resumen ejecutivo; el texto completo está en `deploy/engineering/AGENTS.md.global` §ANTI-ALUCINACIÓN):

1. **Nada se afirma sin evidencia**: toda afirmación comprobable (commit, archivo, tarea, servicio, veredicto) exige el comando de verificación y su salida (`git log --oneline -1`, `ls -la <ruta>`, `systemctl is-active <svc>`). Sin salida → no afirmar.
2. **"NO LO SÉ" es respuesta válida**: si no sabes, dilo. Prohibido rellenar con plausibilidad no verificada.
3. **NO VERIFICADO se escribe literalmente**: no presentar conjeturas como hechos; no usar ✅ para trabajo no demostrado.
4. **Estructura de reporte**: QUÉ SE PIDIÓ · QUÉ SE HIZO (SHA y rutas) · QUÉ NO SE HIZO · QUÉ NO SE VERIFICÓ · PENDIENTES.
5. **Identidad y trabajo ajeno**: prohibido usar IDs de TASK existentes para trabajo nuevo, atribuirse commits ajenos o cambiar de rol/máquina sin autorización.
6. **Rutas y máquinas**: verificar `pwd` y `git rev-parse --show-toplevel` antes de afirmar ubicación; ASUS y Mac son repos distintos; un archivo local no sincronizado es "local, pendiente de sync".
7. **Sincronización**: el trabajo del Mac no existe en ASUS hasta scp/rsync o push a `mac-veredictos` + integración del detector.
8. **Ante la duda, verifica**: si no puedes ejecutar la verificación → responde NO VERIFICADO.
9. **No heredar afirmaciones de terceros**: la conversación no es evidencia; solo Git, logs y salidas de comandos lo son.

## 15. Anti-bucle: no loops de pregunta sin respuesta (v1.3)

**Origen**: TASK-20260811-005 — TERM (qwen3-coder:30b, Mac :8091) terminó su trabajo y preguntó "Next Steps Needed" vía la herramienta `question`; al no recibir respuesta, el loop de opencode reintentó la pregunta una y otra vez (8 llamadas, 4 dismissed, 90 compactaciones, 8.7M tokens quemados) y **bloqueó la sesión**: los mensajes del usuario no se procesaban mientras la pregunta quedaba `running`.

Reglas (resumen ejecutivo; el texto completo está en `deploy/engineering/AGENTS.md.global` §ANTI-BUCLE):

1. **Máximo 1 pregunta por turno** — solo si es imprescindible para avanzar en trabajo solicitado.
2. **Pregunta descartada/expiró (dismissed/error/rejected)** → NO reintentar en el siguiente turno sin input nuevo del usuario; finalizar el turno con resumen y esperar.
3. **Máximo 3 preguntas sin respuesta en la misma sesión** → detenerse; no seguir preguntando ni analizando lo mismo.
4. **Si el usuario dice "estás en bucle"/"no entiendo"** → parar inmediatamente y responderle directamente.
5. **Mensajes del usuario pendientes tienen prioridad** sobre cualquier trabajo autónomo.
6. **Sesiones largas** (muchas compactaciones) → sugerir sesión nueva en vez de seguir en la misma.

## 16. Modo de revisión autónoma de fondo (v1.4-v1.5-v1.7-v1.8)

**Origen**: petición de Ramón — cuando un agente no tiene nada que hacer, debe revisar el código de URA (fallos, duplicados, arquitectura) en lugar de quedarse parado o preguntar en bucle.

- **Activación automática (v1.8)**: el despertador `deploy/mac/despertador-fondo.sh` + launchd `com.ura.fondo-wake` (Mac, cada 30 min) envía al TERM el mensaje "MODO FONDO" vía `opencode run --attach`. Verificado: TERM revisó `core/mochila/` y registró 2 hallazgos con plan (2026-08-11).
- **Prioridades**: 1) mensajes del usuario (para todo), 2) tareas UDO asignadas, 3) revisiones pendientes (`ura-udo list REVIEW`), 4) modo fondo.
- **Solo lectura**: no corrige nada sin autorización; revisa 1 carpeta/módulo por turno y registra progreso.
- **Registro persistente (v1.5)**: hallazgos en `docs/udo/hallazgos-fondo.md` (tabla: fecha | ruta:línea | hallazgo | gravedad | estado). La conversación NO es memoria.
- **Gravedad**: CRÍTICA (seguridad/pérdida de datos/rotura) · ALTA · MEDIA · BAJA · INFO. CRÍTICA además se notifica (`core/notifier.py`) o se resalta al inicio del siguiente mensaje al humano.
- **Plan propuesto (v1.7)**: todo hallazgo accionable se registra como `propuesto (con plan)` con QUÉ · POR QUÉ · IMPACTO · VERIFICACIÓN · RIESGO/REVERSIBILIDAD; se presenta al humano y, si se aprueba, se convierte en TASK UDO. Un hallazgo es `corregido` solo con corrección hecha y verificada.
- **Límite por turno**: 1 carpeta/módulo; si la sesión se degrada, registrar progreso y cerrar el turno (no ahogarse).

## 17. Entorno y despliegue: lecciones operativas (v1.6)

1. **Mount namespaces pueden diferir**: el bash tool de opencode puede correr en un namespace distinto del host real (incidente 2026-08-11: el remount `rw` del usuario no se veía desde el namespace del agente, y viceversa). Ante discrepancia de estado del sistema, verificar `readlink /proc/self/ns/mnt` y pedir al usuario su salida antes de concluir.
2. **Instalación global en ASUS requiere sudo del humano**: el rootfs de ASUS suele estar RO en el host; el agente no puede escribir en `~/.config/opencode/`. Procedimiento: preparar `sudo cp <repo>/deploy/engineering/AGENTS.md.global ~/.config/opencode/AGENTS.md && head -1 ...`, pedir al humano que lo ejecute, verificar (head + grep + diff contra repo). En la Mac se usa `scp` directo.
3. **Commits en entorno degradado**: si pre-commit falla por rootfs RO (`OSError: Read-only file system` en `~/.cache/pre-commit`), usar `SKIP=semgrep git -c core.hooksPath=/dev/null commit` (solo hooks rotos por el entorno, nunca para saltarse verificaciones del cambio). Ejecutar `ura-engineering-check --env` al inicio de sesión.
4. **Sincronización ASUS→Mac (v1.8)**: los commits hechos en ASUS NO llegan solos al repo de la Mac. Copiar los archivos afectados con `scp` (rutas exactas) y verificar con `git status`/`git diff` en la Mac. Un `M archivo` en la Mac puede ser el propio cambio recién copiado.

## 18. Automatización de procesos (v1.9) — herramientas operativas

Para eliminar la fricción manual que causó fallos repetidos (2026-08-12: pegado de comandos, orden de cierre UDO, locks huérfanos, desincronización Mac↔ASUS):

| Herramienta | Qué hace | Uso |
|-------------|----------|-----|
| `scripts/pro/deploy-mac.sh` | Despliegue completo a la Mac en 1 comando: AGENTS.md.global + scripts (despertador, health-check) + recarga launchd + reinicio TERM + verificación. Opciones: `--solo-agents`, `--solo-scripts` | `bash scripts/pro/deploy-mac.sh` |
| `scripts/pro/ura-udo-cerrar TASK-ID "análisis" "validación" [--force]` | Cierra tarea UDO en el orden correcto (verify → IN_PROGRESS si falta → REVIEW → DONE), resolviendo el falso bloqueo por commit_base post-trabajo | `bash scripts/pro/ura-udo-cerrar TASK-XXX "an" "val"` |
| `deploy/mac/ura-fondo-health.sh [--fix]` | Health-check del sistema de fondo: servidor TERM, watchdog, lock (limpia huérfanos con --fix), último run, progreso, hallazgos, repo | `bash ~/bin/ura-fondo-health.sh --fix` |
| `deploy/mac/despertador-fondo.sh` | Despertador del modo fondo (launchd com.ura.fondo-wake, cada 30 min): mapa de carpetas, sesión fork, agente revisor-fondo, registro automático de progreso | automático |

**Reglas de uso**: (1) tras tocar `AGENTS.md.global` o scripts de la Mac → `deploy-mac.sh` (no scp sueltos); (2) al cerrar tareas UDO → `ura-udo-cerrar` (no secuencias manuales); (3) ante duda del estado del sistema → `ura-fondo-health.sh` (no grep sueltos de logs); (4) estas herramientas se ejecutan desde ASUS (repo fuente), la Mac las recibe por deploy-mac.sh.

## Changelog

| Versión | Fecha | Cambio |
|---------|-------|--------|
| 1.0 | 2026-08-08 | Versión inicial (Plan 0 v1.1 aprobado; TASK-20260808-016) |
| 1.1 | 2026-08-08 | PLAN 1 (TASK-019): A4 reinicio Web, A5 instalación Mac, A3 env check, B1 revisión diferida (ver §9), B4 proporcionalidad |
| 1.2 | 2026-08-11 | §14 Anti-alucinación: verificación obligatoria antes de afirmar (TASK-20260811-003, TERM fabricaba trabajo inexistente) |
| 1.3 | 2026-08-11 | §15 Anti-bucle (TASK-20260811-005, TERM en loop de preguntas "Next Steps Needed") |
| 1.4 | 2026-08-11 | §16 Modo de revisión autónoma de fondo (TASK-20260811-006) |
| 1.5 | 2026-08-11 | §16 Registro persistente de hallazgos (TASK-20260811-007) |
| 1.6 | 2026-08-11 | §17 Entorno y despliegue: lecciones operativas (TASK-20260811-008) |
| 1.7 | 2026-08-11 | §16 Plan propuesto obligatorio en hallazgos accionables (TASK-20260811-009) |
| 1.8 | 2026-08-11 | §16 Despertador real del modo fondo: launchd com.ura.fondo-wake (TASK-20260811-010) + C2 sincronización de este documento |
| 1.9 | 2026-08-12 | §18 Automatización de procesos: deploy-mac.sh, ura-udo-cerrar, ura-fondo-health.sh (TASK-20260812-010) + sync ASUS→Mac (§17.4) |
