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
ura-udo update TASK-... --estado DONE --nota "razón"   # transición auditada
ura-udo update TASK-... --nota "apunte" # nota sin cambio de estado
ura-udo list [ESTADO]                   # tareas por estado
ura-udo status                          # resumen del proyecto
ura-udo verify TASK-...                 # request + commit + git status
```

- IDs únicos: contador monotónico por fecha en `docs/udo/.seq` (sin colisiones `ls|wc`).
- Escrituras con `flock` (`docs/udo/.lock`, patrón ADR-002).
- Concurrencia Web/TERM: solo se usa `flock` — sin dispatcher.

## Flujo de trabajo

1. **Web o Terminal** crea tarea → `PLANNED`
2. Ejecuta → `IN_PROGRESS`
3. **Commit** con formato `tipo(scope): [TASK-YYYYMMDD-NNN][WEB|TERM] desc`
4. Resultado → `REVIEW` (revisión del otro agente o Ramón)
5. `DONE` solo al cerrar

## Verificación

```bash
ura-udo verify TASK-...   # pide: expediente OK, commit con [TASK-ID], git limpio
```

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
