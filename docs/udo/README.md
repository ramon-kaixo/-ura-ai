# UDO — URA Development Orchestrator (Fase 1)

Capa mínima de coordinación entre agentes (Web/TERM/Ramón) y Git.
**Fuente de verdad: Git (código) + `docs/udo/` (proceso).** Sin BD, sin panel, sin servidor.

## Principios

- **Reversible**: `rm -rf docs/udo/ && rm scripts/pro/ura-udo` deja URA intacta.
- **No duplica memoria**: enlaza la existente (ver Enlaces), no la copia.
- **No toca** `motor/`, `core/`, `tests/`, `scripts/pro/tuneladora/`.
- **Un solo archivo por tarea** (`docs/udo/tasks/TASK-YYYYMMDD-NNN.md`) con estado y historial dentro.

## Estados (transiciones auditadas)

`PLANNED → IN_PROGRESS → REVIEW → DONE` (+ `BLOCKED`, `CONFLICT`, `CANCELLED`)
Toda transición queda registrada en `historial:` del expediente.

## CLI

```bash
ura-udo create "descripción"            # crea TASK-YYYYMMDD-NNN (solicitante: URA_SOLICITANTE o RAMON)
ura-udo show TASK-20260808-001          # ver expediente completo
ura-udo update TASK-... --estado DONE --nota "razón"   # transición auditada (máquina formal, --force para saltos)
ura-udo update TASK-... --nota "apunte" # nota sin cambio de estado
ura-udo update TASK-... --reserva "r1,r2"              # declarar reserva al update ("" vacía)
ura-udo update TASK-... --agente_web "WEB (ejecutor)" --agente_terminal "TERM (revisor)"  # roles duales
ura-udo reserve TASK-... [--add "r1,r2"] [--clear]     # gestión acumulativa de reserva
ura-udo check [ruta...]                 # reservas activas; con rutas: detector de conflicto
ura-udo review TASK-... [--approve "nota" | --changes "razón"]  # revisión formal F3
ura-udo list [ESTADO]                   # tareas por estado
ura-udo status                          # resumen del proyecto (incluye reservas activas)
ura-udo verify TASK-...                 # request + commit + git + discrepancias reserva vs diff
```

- IDs únicos: contador monotónico por fecha en `docs/udo/.seq` (sin colisiones `ls|wc`).
- Escrituras con `flock` (`docs/udo/.lock`, patrón ADR-002).
- Concurrencia Web/TERM: solo se usa `flock` — sin dispatcher.

## Revisión formal (F3)

Ciclo: `IN_PROGRESS → REVIEW → CHANGES_REQUESTED → IN_PROGRESS → REVIEW → APPROVED → DONE`.
La máquina de transiciones bloquea saltos ilegítimos (`--force` para excepciones).

`ura-udo review TASK-ID` ejecuta el checklist de 8 comprobaciones (estado, commit,
diff, archivos vs reserva, requisitos, tests, documentación, regresiones) y con
`--approve`/`--changes` emite veredicto (registrado en `revision:` + historial,
revisor vía `URA_REVISOR`). La reserva sigue activa en REVIEW y CHANGES_REQUESTED.
Detalles: `docs/udo/F3_PROPOSAL.md`.

## Reserva de archivos (F2)

**Regla**: antes de pasar a `IN_PROGRESS` (o justo al empezar), el canal declara qué archivos/áreas va a modificar:

```bash
ura-udo reserve TASK-20260808-005 --add "motor/core/llm/router.py,motor/core/llm/config.py"
ura-udo check motor/core/llm/router.py   # si devuelve CONFLICTO, NO tocar esos archivos
```

- La reserva vive en el campo `reserva: [ruta1, ...]` del expediente → **persistente y versionada en Git** (no depende de la memoria del LLM).
- Solo las tareas con estado `IN_PROGRESS`/`REVIEW` protegen sus reservas.
- **Liberación automática**: al pasar a `DONE`/`CANCELLED`, la reserva deja de estar activa; el historial queda en el expediente (quién reservó qué y cuándo).
- **Al cerrar (verify)**: compara `git diff <commit_base>..HEAD` + working tree contra la reserva →
  1. archivos modificados sin declarar (`MODIFICADOS SIN DECLARAR`);
  2. reservados que no se modificaron (`RESERVADOS NO MODIFICADOS — liberación sugerida`).
- `commit_base` se registra automáticamente al pasar a `IN_PROGRESS` (delimita el diff de la tarea).

### Límites del mecanismo (documentación honesta)

- La reserva es **cortesía + auditoría, no exclusión de kernel**: Git sigue siendo la fuente de verdad y el conflicto REAL se detecta al commitear. Ningún proceso puede impedir físicamente que otro agent modifique un archivo reservado.
- La reserva solo funciona si **ambos canales consultan** (`ura-udo check`) antes de actuar — es disciplina de procedimiento, no de bloqueo.
- Mitigación integrada: `ura-udo verify` lista las invasiones (no las bloquea por defecto) y el flujo de commit con `[TASK-ID]` permite correlacionar quién tocó qué.

## Flujo de trabajo

1. **Web o Terminal** crea tarea → `PLANNED` (campo `canal:` = solicitante)
2. Se registran **roles duales** (`--agente_web` / `--agente_terminal`) → ejecutor + revisor independiente
3. Declara **reserva** (`reserve --add`) y pasa a `IN_PROGRESS` (se auto-registra `commit_base`)
4. **Commit** con formato `tipo(scope): [TASK-YYYYMMDD-NNN][WEB|TERM] desc`
5. Resultado → `REVIEW` — la reserva **sigue activa en REVIEW** (quien revisa no modifica la zona que revisa)
6. **Revisión formal** (`review --approve`/`--changes`): APPROVED, o CHANGES_REQUESTED → el ejecutor corrige → nueva REVIEW
7. `DONE` solo desde APPROVED — `verify` reporta discrepancias reserva vs diff y registra el commit en `commits:`

## Verificación

```bash
ura-udo verify TASK-...   # pide: expediente OK, commit con [TASK-ID], git limpio, discrepancias reserva vs git
```

## Modelo operativo dual (Web ejecuta / Terminal revisa)

Principios (Anexo A — modelo dual):

- **Web = ejecutor por defecto; Terminal = revisor por defecto.** Roles registrables por tarea con `--agente_web "WEB (ejecutor)"` y `--agente_terminal "TERM (revisor)"` (ver TASK-006).
- **El revisor no modifica la zona que revisa**: la reserva protege en `IN_PROGRESS` y `REVIEW`.
- **Una tarea independiente sí puede ser ejecutada por el otro agente** si `check` no detecta solapamiento de reservas (granularidad por archivo o prefijo `dir/`).
- **Terminal puede**: leer, inspeccionar, ejecutar tests, analizar, verificar (`show`/`status`/`check`/`verify`). **No debe** modificar zonas reservadas por otra tarea activa.
- **Terminal no se autodelega trabajo**: solo con TASK autorizada por Ramón o por la fase correspondiente.
- **Una única memoria operativa**: Git (código) + UDO (estado) + `docs/architecture/` (decisiones) + `docs/pro/sesiones/` (histórico). Las conversaciones no son fuente de verdad.

## Compatibilidad con tareas F1

- Tareas creadas antes de F2 (sin `reserva:` ni `commit_base:`) siguen funcionando: `verify` tolera campos ausentes.
- Al tocar una tarea F1 en `IN_PROGRESS` sin `commit_base`, este se auto-registra en el primer `update`.
- `--reserva ""` vacía la reserva (reset).

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
