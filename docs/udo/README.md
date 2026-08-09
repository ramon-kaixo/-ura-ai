# UDO — URA Development Orchestrator (F1 + F2 + F2.2)

Capa mínima de coordinación entre agentes (Web/TERM/Ramón) y Git.
**Fuente de verdad: Git (código) + `docs/udo/` (proceso).** Sin BD, sin panel, sin servidor.

## Principios

- **Reversible**: `rm -rf docs/udo/ && rm scripts/pro/ura-udo` deja URA intacta.
- **No duplica memoria**: enlaza la existente (ver Enlaces), no la copia.
- **No toca** `motor/`, `core/`, `tests/`, `scripts/pro/tuneladora/`.
- **Un solo archivo por tarea** (`docs/udo/tasks/TASK-YYYYMMDD-NNN.md`) con estado y historial dentro.

## Estados

`PLANNED → IN_PROGRESS → REVIEW → DONE` (+ `BLOCKED`, `CONFLICT`, `CANCELLED`)
Toda transición queda registrada en `historial:` del expediente.

**Regla de integridad (CASO B)**: `DONE` solo desde `REVIEW` — sin revisión
válida previa la tarea no se cierra. Excepción: `--force` explícito con nota
(autorización expresa, queda auditada en el historial). No se finge una revisión:
si el revisor está idle, la tarea permanece `REVIEW`.

**Gate de integridad de revisión (F2.2)**: al cerrar `DONE` sin `--force`,
`ura-udo update` exige que la revisión signifique algo:

1. `commits:` con al menos un commit registrado (ejecutar `verify` antes de cerrar);
2. diff `commit_base..HEAD` no vacío (hay trabajo revisable);
3. todos los SHAs de `commits:` son ancestros de `HEAD` en el momento del cierre
   (**pinning** — una historia reescrita tras la verificación bloquea el DONE);
4. árbol de trabajo limpio fuera del expediente (sin cambios sin commitear).

**Marca honesta de auto-revisión (F2.2)**: si se cierra sin `--revisor` o el
revisor coincide con el ejecutor, la herramienta añade `AUTO-REVISIÓN` al
historial automáticamente (la dice la herramienta, no el texto libre). La
revisión de un único agente queda así distinguida de una revisión cruzada.

## CLI

```bash
ura-udo create "descripción"            # crea TASK-YYYYMMDD-NNN (solicitante: URA_SOLICITANTE o RAMON)
ura-udo show TASK-20260808-001          # ver expediente completo
ura-udo update TASK-... --estado DONE --nota "razón"   # transición auditada (DONE solo desde REVIEW)
ura-udo update TASK-... --nota "apunte" # nota sin cambio de estado
ura-udo update TASK-... --reserva "r1,r2"              # declarar reserva al update ("" vacía)
ura-udo update TASK-... --instrucciones "…" --restricciones "…"  # contexto propagable (F2)
ura-udo update TASK-... --agente_web "WEB (ejecutor)" --agente_terminal "TERM (revisor)"  # roles duales
ura-udo update TASK-... --estado DONE --revisor "WEB" --nota "..."  # revisión (F2.2): sin --revisor o revisor==ejecutor → AUTO-REVISIÓN
ura-udo reserve TASK-... [--add "r1,r2"] [--clear]     # gestión acumulativa de reserva (enforcement activo)
ura-udo check [ruta...]                 # reservas activas; con rutas: detector de conflicto
ura-udo context TASK-...                # contexto compartido (F2): expediente + commits + reservas
ura-udo list [ESTADO]                   # tareas por estado
ura-udo status                          # resumen del proyecto (incluye reservas activas)
ura-udo verify TASK-...                 # request + commit + git + discrepancias reserva vs diff
ura-ask TASK-...                        # consultor de contexto compartido (wrapper de ura-udo context)
ura-ask status                          # resumen del proyecto
```

- IDs únicos: contador monotónico por fecha en `docs/udo/.seq` (sin colisiones `ls|wc`).
- Escrituras con `flock` (`docs/udo/.lock`, patrón ADR-002).
- Concurrencia Web/TERM: solo se usa `flock` — sin dispatcher.

## Reserva de archivos (F2)

**Regla**: antes de pasar a `IN_PROGRESS` (o justo al empezar), el canal declara qué archivos/áreas va a modificar:

```bash
ura-udo reserve TASK-20260808-005 --add "motor/core/llm/router.py,motor/core/llm/config.py"
ura-udo check motor/core/llm/router.py   # si devuelve CONFLICTO, NO tocar esos archivos
```

- La reserva vive en el campo `reserva: [ruta1, ...]` del expediente → **persistente y versionada en Git** (no depende de la memoria del LLM).
- Solo las tareas con estado `IN_PROGRESS`/`REVIEW` protegen sus reservas.
- **Enforcement (bloqueo real)**: `reserve --add` y `update --reserva` **rechazan** declarar una ruta ya reservada por otra tarea activa (`ERROR: está reservada por TASK-X`). Excepción: `--force` (autorización expresa, queda en historial). La tarea ajena debe liberar (`reserve --clear`) o autorizar.
- **Liberación automática**: al pasar a `DONE`/`CANCELLED`, la reserva deja de estar activa; el historial queda en el expediente (quién reservó qué y cuándo).
- **Al cerrar (verify)**: compara `git diff <commit_base>..HEAD` + working tree contra la reserva →
  1. archivos modificados sin declarar (`MODIFICADOS SIN DECLARAR`);
  2. reservados que no se modificaron (`RESERVADOS NO MODIFICADOS — liberación sugerida`).
- `commit_base` se registra automáticamente al pasar a `IN_PROGRESS` (delimita el diff de la tarea).

### Límites del mecanismo (documentación honesta)

- La reserva es **garantía dentro de UDO** (no se puede declarar conflicto) + **auditoría sobre Git**:
  el conflicto REAL de ejecución se detecta al commitear. Ningún proceso impide físicamente que otro
  agent modifique un archivo reservado sin declararlo — `ura-udo verify` lista esas invasiones.
- Mitigación integrada: enforcement en declaración + `verify` lista invasiones + flujo de commit
  con `[TASK-ID]` permite correlacionar quién tocó qué.

## Contexto compartido (F2)

El contexto de una tarea **no depende de la conversación**: vive en Git (expediente + commits).

- `ura-udo context TASK-ID` emite: ID, estado, descripción/objetivo, canal, roles, reserva,
  commit_base, commits recientes con `[TASK-ID]`, reservas activas y último historial.
- `ura-ask TASK-ID` es el consultor de contexto (wrapper de `ura-udo context`).
- **Propagación**: `ura-opencode` inyecta el bloque de contexto en el prompt enviado al Web
  (tarea + objetivo + zona + roles), de modo que el Web arranca con el contexto completo.
- **Recuperación con agente idle**: `ura-ask TASK-ID` / `ura-udo context` funcionan aunque el
  otro agente esté ausente — la fuente es el expediente, no la memoria del LLM.
- `ura-chat` es el chat LLM a Ollama (herramienta distinta, NO es contexto compartido).

## Flujo de trabajo

1. **Web o Terminal** crea tarea → `PLANNED` (campo `canal:` = solicitante)
2. Se registran **roles duales** (`--agente_web` / `--agente_terminal`) → ejecutor + revisor independiente
3. Declara **reserva** (`reserve --add`) y pasa a `IN_PROGRESS` (se auto-registra `commit_base`)
4. **Commit** con formato `tipo(scope): [TASK-YYYYMMDD-NNN][WEB|TERM] desc`
5. Resultado → `REVIEW` — la reserva **sigue activa en REVIEW** (quien revisa no modifica la zona que revisa)
6. **Revisión**: el revisor verifica (`verify` + lectura del diff); corrige en `IN_PROGRESS` si procede → nueva `REVIEW`
7. `DONE` solo desde `REVIEW` (o `--force` explícito) — `verify` reporta discrepancias reserva vs diff y registra el commit en `commits:`

## Verificación

```bash
ura-udo verify TASK-...   # pide: expediente OK, commit con [TASK-ID], git limpio, discrepancias reserva vs git
```

## Modelo operativo dual (Web ejecuta / Terminal revisa)

Principios (Anexo A — modelo dual):

- **Web = ejecutor por defecto; Terminal = revisor por defecto.** Roles **por tarea** (no permanentes):
  el mismo OpenCode puede ser ejecutor de una tarea y revisor de otra; se registran con
  `--agente_web "WEB (ejecutor)"` y `--agente_terminal "TERM (revisor)"` (ver TASK-006).
- **El revisor no modifica la zona que revisa**: la reserva protege en `IN_PROGRESS` y `REVIEW`.
- **Una tarea independiente sí puede ser ejecutada por el otro agente** si `check` no detecta solapamiento de reservas (granularidad por archivo o prefijo `dir/`).
- **Terminal puede**: leer, inspeccionar, ejecutar tests, analizar, verificar (`show`/`status`/`check`/`verify`). **No debe** modificar zonas reservadas por otra tarea activa.
- **Comportamiento con agente idle**:
  - CASO A — ejecutor + revisor disponibles: ejecutar → revisar → corregir → revisar → cerrar.
  - CASO B — ejecutor disponible + revisor idle: ejecutar → `REVIEW`, **nunca** `DONE` sin revisión válida (el script lo impide salvo `--force` explícito y auditado).
  - CASO C — revisor disponible + ejecutor idle: puede consultar/analizar o ejecutar una tarea independiente; **no** se apropia silenciosamente de la tarea asignada al ejecutor.
- **Terminal no se autodelega trabajo**: solo con TASK autorizada por Ramón o por la fase correspondiente.
- **Una única memoria operativa**: Git (código) + UDO (estado) + `docs/architecture/` (decisiones) + `docs/pro/sesiones/` (histórico). Las conversaciones no son fuente de verdad.

## Estructura canónica del expediente

Orden de campos (estable, no crece arbitrariamente): `id, fecha, solicitante, descripcion,
objetivo, estado, canal, agente_web, agente_terminal, revisor, reserva, commit_base, contexto,
cambios, commits, revision, pendientes, resultado, historial`.

- Los campos nuevos se insertan **antes de `historial:`** (nunca al final del archivo).
- Los expedientes antiguos con campos al final se leen igualmente por clave (`clave: valor`)
  → compatibilidad hacia atrás, sin migración forzada.

## Enlaces (memoria existente — NO duplicar)

| Sistema | Ubicación | Rol |
|---|---|---|
| Sesiones | `docs/pro/sesiones/` | Registro diario de actividad (lo usa `ura-udo status` vía git log) |
| Arquitectura + ADRs | `docs/architecture/` | Decisiones técnicas (375+ archivos, ADR-002 flock) |
| Memoria | `docs/MEMORIA.md` | Visión global del proyecto |
| Closeouts de fases | `.opencode/plans/` | Propuestas y cierres por fase |
| Config global | `AGENTS.md` | Instrucciones para agentes |

## Notas de implementación (F1)

- `ura-task`/`ura-status`/`docs/orchestration/` retirados en favor de `ura-udo` (esta estructura).
- Credenciales de OpenCode web: `OPENCODE_WEB_PASS` desde entorno o `/etc/ura/secrets.env` (nunca en el repo).
- La retirada de OpenClaw vive en su propio commit (ver `git log --grep OpenClaw`).

## Retirada OpenClaw (`c6d60c8c`, 2026-08-08)

Criterio: `grep -rli openclaw scripts/ core/ motor/ deploy/` → **0** (código vivo).

| Excepción | Razón | Estado |
|---|---|---|
| `monitor/openclaw.py` + SNC (`monitor/snc.py`) | Brazo de emergencia del SNC — decisión Ramón | 🔒 Intacto |
| `core/model_router/cli.py` | Auth de arranque con `OPENCLAW_GATEWAY_TOKEN` | 🔒 Intacto (ADR-007) |
| `data/openclaw_stats.json` | Estadísticas runtime | 🔒 Intacto |
| `tests/integration/test_openclaw.py` | Test muerto (módulo `monitor/` — zona protegida tests/) | ⚠️ No tocar (regla) |
| `scripts/pro/tuneladora/snapshot.py` | Zona protegida (tuneladora) | ⚠️ Pendiente decisión |

Pendientes Ramón (sudo): `systemctl stop+disable ura-openclaw.service`, añadir
`OPENCODE_WEB_PASS` a `/etc/ura/secrets.env`, borrar `/home/ramon/.openclaw/`,
re-apuntar `/usr/local/bin/opencode`.

## Cola de pendientes de fase (F2.3)

Los pendientes de un plan pueden posponerse (cola) **sin bloquear el avance** a la siguiente fase, PERO **la fase NO se cierra** hasta que la cola esté resuelta o justificada por Ramón.

```bash
ura-udo pendientes add TASK-ID "pendiente"      # registrar un pendiente pospuesto
ura-udo pendientes list                          # ver la cola
ura-udo pendientes resolver TASK-ID "nota"       # marcar resuelto
ura-udo pendientes check                         # ¿puede cerrarse la fase? (gate)
```

Registro: `docs/udo/pendientes-fase.md` (Git). El `check` devuelve BLOQUEADO si hay pendientes ABIERTOs — el cierre de fase exige cola vacía o aprobación expresa de Ramón.
