# AUDITORÍA INDUSTRIAL URA COMPLETA — TODOS LOS NODOS

**Fecha:** 2026-08-28 (madrugada)
**Host ejecutor:** `gx10-64c3` (GX10 Desktop, Tailscale 100.72.103.12)
**Repo auditado:** `/home/ramon/URA/ura_ia_1972` (`origin: git@github.com:ramon-kaixo/-ura-ai.git`)
**Método:** comandos de solo lectura (`git`, `sqlite3`, `systemctl`, `ss`, `ssh`, `cat`, `ls`). No se modificó ningún artefacto.

---

## 1. RESUMEN EJECUTIVO

La auditoría industrial cobró **4 dominios** (Git, SQLite, Timers, Plan 1010) sobre los 3 nodos declarados: **GX10 Desktop**, **GX10 Web** y **Mac**.

**Hallazgos clave:**

1. **CRÍTICO — Nodo Mac NO accesible.** SSH denegado con las 5 llaves probadas y el registro P2P lo marca `degraded` (`last_seen=0.0`, `consecutive_failures=1`). El repo Git, la BD central de tareas y `launchctl` del Mac **no pudieron auditarse**. El commit `626432f1` (que desbloquea el worker Mac) no es verificable allí.
2. **ALTO — Orquestación estancada.** En la BD accesible hay **17 de 18 tareas en `failed`** con 17 `retry` acumulados, 0 `pending`, 0 `in_progress`. No hay cola activa de trabajo.
3. **ALTO — Esquema DB incompleto para la operativa pedida:** no existen `tasks_archive` ni `schema_version`, y la tabla `task_events` **no tiene columna `automatic`**. `TASK-0d9a8e` **no existe** en ninguna BD del nodo.
4. **MEDIO — Repo mutando en vivo.** Durante la auditoría un agente de fondo auto-commiteó (`HEAD` pasó de `a80264d4` → `ee...` → `c31fa513`, último a las 03:59 con `[TASK-20260828-gx10-wip2][TERM]`) y movió `.attic/` a `.gitignore`. Quedan **18 archivos untracked** sin versionar.
5. **MEDIO — WAL sin checkpoint:** `data/task_queue.db` pesa 32 KB pero su WAL 1.38 MB → datos sin consolidar.
6. **BAJO/INFO — "Plan 1010" no existe como artefacto** en el repo. Hay 9 planes de fases incompatibles; la coincidencia más coherente es **PLAN_DESARROLLO (testing F1-F4)** y el reciente **PLAN_STRESS_TESTING_20260828 (F0-F8)**, ambos con fases sin cerrar.

---

## 2. MATRIZ DE RIESGOS

| ID | Riesgo | Nivel | Impacto |
|---|---|---|---|
| R1 | Nodo Mac inaccesible (SSH + registry `degraded`) | **CRÍTICO** | BD central, git y launchctl del Mac sin auditar; el fix `626432f1` no se puede validar ni desplegar |
| R2 | 17/18 tareas `failed`, cola sin trabajo | **ALTO** | Orquestación multi-nodo estancada; el sistema no progresa |
| R3 | DB sin `tasks_archive`, `schema_version`, ni `automatic` en eventos | **ALTO** | Sin historial, sin versionado de esquema, sin trazabilidad de eventos automáticos |
| R4 | WAL de 1.38 MB sin checkpoint | **MEDIO** | Pérdida de tareas/eventos si el proceso muere antes de consolidar |
| R5 | Repo modificándose en vivo + 18 untracked (timers mutmut, tests nuevos, `revisiones/`) | **MEDIO** | Pérdida de trabajo no versionado; auditoría con estado cambiante |
| R6 | 2 stashes huérfanos con trabajo sin reclamar | **MEDIO** | `mutmut_daily.py` y `motor/core/utils/__init__.py` (+78 líneas) en riesgo de perderse |
| R7 | Ramas de fase sin fusionar (`merge-fase5` ~1058 commits, `ramon/fase-1-excavacion`) | **BAJO** | Deuda de integración |
| R8 | `ura-revisiones.service` FAILED + log de cleanup en ruta distinta de la esperada | **BAJO** | Monitorización incompleta |
| R9 | "Plan 1010" no trazable a ningún documento | INFO | Objetivo de alineación ambiguo |

---

## 3. ANÁLISIS POR NODO

### 3.1 NODO gx10-desktop (este host, `gx10-64c3`)

#### Comisión 1 — Git y repositorio

- **Remote:** `origin = git@github.com:ramon-kaixo/-ura-ai.git`.
- **Hash `626432f1`:** **EXISTE** localmente.
  `626432f147e8bf5048ac7177f363571b94b87a8a` — 2026-08-28 03:26:24 — `fix(worker): [TASK-20260827-001][TERM] _build_command usa shlex.split ... desbloquea worker Mac`.
- **Ramas `feature/opencode-*` y estado de fusión** (`git branch --merged main`):

| Rama | ¿Fusionada en `main`? |
|---|---|
| `feature/opencode-gx10` | SÍ |
| `feature/opencode-mac` | SÍ |
| `feature/opencode-web` | SÍ |

- **Branches relevantes NO fusionadas:** `ia/TASK-20260828-gx10-wip`, `merge-fase5` (~1058 commits, punta `f96ba531`), `ramon/fase-1-excavacion` (punta `bd996c7c`), `dev/v3.1-expansion`.
- **Rama actual:** `ia/TASK-20260828-gx10-wip2` (HEAD `c31fa513`, 03:59).
- **Estado del working tree (estado estable tras auto-commit):**
  - Modificados unstaged: **0** · Staged: **0** · Borrados: **0** · Untracked: **18**.
  - Untracked notables:
    - `Modelfile-qwen-mejorado`, `OpenCode.md`
    - `deploy/timers/ura-mutmut*.service|.timer` (4 archivos)
    - `docs/udo/coverage-reports/2026-08-2[5-8].md`
    - `docs/udo/plans/PLAN_STRESS_TESTING_20260828.md`
    - `motor/example_util.py`, `scripts/pro/ura-worker-watchdog.sh`
    - `revisiones/`
    - 5 tests unit nuevos (`test_extraction_service_cobertura.py`, `test_fase7.py`, `test_mochila_server_cobertura.py`, `test_motor_qdrant_client.py`)
  - Nota: durante la captura inicial el status mostraba 93 líneas (staged + unstaged + untracked, incl. masivo `.attic/tools/scripts_pro/`); un agente de fondo commitó y añadió `.attic/`, `.opencode runtime` y `opencode.json.bak.*` al `.gitignore` (`c31fa513`). **El repo no estaba quieto.**
- **Stashes (2):**

| Stash | Fecha | Mensaje | Contenido resumido |
|---|---|---|---|
| `stash@{0}` | 2026-08-27 | `WIP on main: b0f7b27f merge: feature/opencode-mac → main` | `docs/udo/coordination.json` (±2); **`scripts/pro/mutmut_daily.py` nuevo (257 líneas)** — trabajo no versionado |
| `stash@{1}` | 2026-08-27 | `WIP on ia/TASK-20260826-018: 075e8d40 fix configs Mac+GX10` | `docs/udo/coordination.json` (±2); **`motor/core/utils/__init__.py` (+78 / −3)** |

#### Comisión 2 — Base de datos SQLite (`data/task_queue.db`)

Esquema completo:

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    plan_phase TEXT DEFAULT '',
    assigned_to TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retries INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    context_json TEXT DEFAULT '{}',
    worktree_path TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT DEFAULT '',
    last_heartbeat TEXT DEFAULT '',
    error_log TEXT DEFAULT '',
    commit_sha TEXT DEFAULT '',
    reviewer TEXT DEFAULT ''
, node_id TEXT DEFAULT '', timeout_seconds INTEGER DEFAULT 1800);
CREATE TABLE task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT REFERENCES tasks(id),
    event TEXT NOT NULL,
    agent TEXT DEFAULT '',
    details TEXT DEFAULT '',
    timestamp TEXT NOT NULL
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assigned ON tasks(assigned_to);
CREATE INDEX idx_events_task ON task_events(task_id);
```

- **Conteo por estado** (pedido: PENDING / IN_PROGRESS / DONE / FAILED / BLOCKING):

| Estado | Conteo |
|---|---|
| PENDING / pending | **0** |
| IN_PROGRESS / (started) | 0 |
| DONE / done | **1** |
| FAILED / failed | **17** |
| BLOCKING | 0 |
| **Total** | **18** |

- **`tasks_archive`:** NO EXISTE. **`schema_version`:** NO EXISTE.
- **TASK-0d9a8e:** NO EXISTE en esta BD ni en ninguna otra `.db` con tabla `tasks` del nodo (búsqueda por patrón en todo el proyecto).
- **Columna `automatic` en `task_events`:** NO EXISTE. Los eventos registrados son: `created` (18), `assigned` (18), `retry` (17), `started` (1), `merged` (1).
- **Detección de nodos en tareas:** `gx10` (13), `mac` (3), `any` (2). Coherente con el registry P2P.
- **WAL:** `task_queue.db-wal` = 1.38 MB vs `.db` 32 KB → datos sin checkpoint (riesgo R4).
- **Conclusión:** la BD accesible es la **local del GX10**. La **central del Mac** (según hipótesis del encargo) **no se pudo consultar** (R1).

#### Comisión 3 — Timers y automatización (GX10)

- `systemctl list-timers | grep ura`: **18 timers activos** — `ura-cleanup`, `ura-cleanup-auto`, `ura-backup`, `ura-backup-mac` (Mac→GX10), `ura-auditd-watchdog`, `ura-audit-extra`, `ura-consolidate`, `ura-harden`, `ura-pipeline`, `ura-despertador`, `ura-memory-watchdog`, `ura-mochila-guard`, `ura-revisiones`, `ura-watchdog`, `ura-reindex`, `ura-maintenance-v2`, `ura-cobertura`, `ura-chaos`.
- `ura-cleanup.timer`: **active (waiting)**, `OnCalendar=*-*-* 04:00:00`, `RandomizedDelaySec=1800`, enabled desde 2026-08-23. Próximo disparo 04:15:17.
- **`/var/log/ura-cleanup.log`: NO EXISTE** (ruta pedida en el encargo no aplica en GX10).
  - Ruta real: **`/home/ramon/URA/logs/ura_cleanup.log`** — existe, 43.5 KB, permisos `-rwxr-xr-x ramon` (755). Última ejecución: **2026-08-27 04:27** con cierre OK ("=== fin ==="). Todas las limpiezas recientes correctas (jsonl.1 → 0, snapshots >30d, rotado logs, pycache, docker prune OK).
  - `ura-cleanup.sh` (ExecStart) escribe en esa ruta (`LOG="/home/ramon/URA/logs/ura_cleanup.log"`).
- **`ura-revisiones.service`:** FAILED (ya detectado en auditoría previa; su timer sigue disparándose).

### 3.2 NODO mac-mini (100.123.81.101)

- **Acceso: DENEGADO.** `ssh` rechazado con 5 llaves (`id_ed25519`, `id_gx10_mac`, `id_ura_backup`, `id_backup_mac`, `id_rsa`) — `Permission denied (publickey,password,keyboard-interactive)`. `caja0` (Windows) tampoco responde (timeout).
- **Registry P2P corrobora:** en `.ura/node_registry.json`, `mac` está `degraded`, `last_seen=0.0`, `consecutive_failures=1` (gx10 `online`, `last_latency_ms=26.5`).
- **Comisiones pendientes por nodo Mac** (sin auditar):
  - Git: `git status --porcelain`, `git stash list`, `git branch -a | grep feature/opencode-*`, comparar `626432f1`.
  - SQLite central: esquema, estados de tareas, `tasks_archive`, `schema_version`, `TASK-0d9a8e`.
  - `launchctl list | grep ura` y existencia de `com.ura.cleanup.plist`.
  - Permisos de `/var/log/ura-cleanup.log` (Mac).

### 3.3 NODO gx10-web (OpenCode Web + OpenClaw Gateway)

- **Detectado como servicio en este mismo host:** `opencode.service` = "OpenCode Web Server with OpenClaw Gateway and Ollama" (activo), `ai.opencode.desktop` escuchando en `127.0.0.1:3000`, Ollama en `*:11434`.
- No existe un nodo `web` independiente en `.ura/node_registry.json` (solo `gx10` y `mac`). El "nodo web" comparte el filesystem Git/DB del GX10, por lo que **Git y SQLite auditados en 3.1 son los mismos** para el nodo web (mismo host). El tenant de Web se diferencia únicamente por la rama `feature/opencode-web`, ya **fusionada en main**.

---

## 4. ALINEACIÓN CON "PLAN 1010"

**No existe ningún artefacto llamado "Plan 1010"** (ni `PLAN 1010`, `plan-1010`, `plan_1010`; verificado con `git grep` y `grep -rni`). El repositorio define **9 planes de fases incompatibles**. Los candidatos más plausibles para lo que pides:

| Plan | Fases | Estado | Coincidencia con lo pedido |
|---|---|---|---|
| **PLAN_DESARROLLO.md** | Testing F1-F4 | **F1 ✅ · F2 ⏳ hypothesis · F3 ⏳ locust/snapshot · F4 ⏳ mutmut nocturno** | Coincide con "Fase 1 parcial, Fase 2? Fase 3?" → es el más parecido |
| **PLAN_STRESS_TESTING_20260828.md** | F0-F8 | **Guardado, NO analizado, NO ejecutado** (creado HOY, 192 líneas) | Encaja con la conversación previa de estrés (SLOs P95 <500ms, errores <1%, CPU<80%, RAM<75%) |
| **PLAN_TOTAL_20260818.md** | P0→P3 | Parcial | Calidad/cobertura, no fases temáticas |
| **ARQUITECTURA_v4.0_PLAN.md** | F0-F8 | Fases 2 pilled: 7/10 puentes cortados | Refactor, no "fases de plan" |
| **MASTER_PLAN.md** | F1-F5 (refactor) | F1-F4 en curso hacia v4.0.0 | Refactor, no funcional |
| **F6-F10_PLAN_CONSOLIDADO.md** | F6-F10 | **0 fases ejecutadas** (seguridad CI/CD monitoreo backups obs) | Planificado |

**Matriz de implementación (PLAN_DESARROLLO, evaluado contra el código):**

| Fase | Prerequisito | Implementada | Evidencia / archivos a tocar |
|---|---|---|---|
| F1: baseline de testing | randomly/deadfixtures/radon/xenon | ✅ (parcial) | Suite existente en `tests/` |
| F2: property-based testing | `hypothesis`, ≥10 tests property | ❌ **Falta** | Crear `tests/property/` o `tests/unit/test_*_property.py` |
| F3: carga/snapshot | `locust` + `snapshot` + `API.md` | ❌ **Falta** | `locustfile.py`, `tests/snapshot/`, documentar API en `docs/` |
| F4: mutmut nocturno + chaos | mutmut + `make chaos` | ❌ **Parcial (guardado, sin timer)** | Timer existe sin versionar: `deploy/timers/ura-mutmut*.service|.timer` (untracked); falta el skill/script de orquestación |

**Nota sobre las fases del encargo (Fase 1/2/3):** si te refieres al ecosistema de **orquestación multi-nodo** (lo que el plan total llama sprints P2P: `ia/TASK-20260828-gx10-wip2`), el mapa real es:
- Fase 1 (parcial): parser de planes + tareas + colas sharded por nodo (`scripts/pro/parse_plan_to_tasks.py`, `motor/orchestration/{task_queue,node_registry,contracts}.py`) — hay commits Sprint-1.1/1.2/1.3.
- Fase 2: distribución P2P + failover (`motor/orchestration/{api,failover,employee}.py`, `worksteal.py`, `worker.py` — untracked/staged recién commiteados, en la rama actual NO fusionada).
- Fase 3: worker Mac + verificación real — **bloqueada por R1/R2** (17 tareas failed, Mac degradado, fix `626432f1` sin validar).

---

## 5. PLAN DE CORRECCIÓN

Ordenado por prioridad. Cada acción indica archivo/ruta concreto.

### P1 — Nodo Mac (R1 · CRÍTICO)
1. `git fetch origin main` y validar `626432f1` en el Mac → necesario para arrancar el worker.
2. Reinstalar clave pública en `mac-mini`: añadir `pub` correspondiente a `~/.ssh/authorized_keys` (usuario `barkaixo`) — hoy **ninguna** de las 5 llaves es aceptada.
3. Tras restaurar SSH ejecutar en el Mac: `git status --porcelain`, `git stash list`, `git branch --merged main`, `git cat-file -t 626432f1`, `launchctl list | grep ura`, `[ -f ~/Library/LaunchAgents/com.ura.cleanup.plist ]`, `ls -l /var/log/ura-cleanup.log`.
4. Actualizar `.ura/node_registry.json` (nodo `mac`: `last_seen`, `consecutive_failures`) cuando se recupere.

### P2 — Descongelar la orquestación (R2 · ALTO)
1. Auditar `error_log` de las 17 tareas failed: `sqlite3 data/task_queue.db "SELECT id,error_log FROM tasks WHERE status='failed';"`.
2. Resetear las tareas recuperables: `UPDATE tasks SET status='pending', retries=0 WHERE status='failed' AND error_log LIKE '%worker%';` (solo tras P1 en las de `mac`).
3. Verificar `motor/orchestration/worker.py` y `worksteal.py` (recién commiteados en `ia/TASK-20260828-gx10-wip2`) con una tarea de humo `node_id=gx10`.

### P3 — Migración de esquema SQLite (R3 · ALTO)
1. Crear tabla de versionado y mover los metadatos existentes:
   ```sql
   CREATE TABLE schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL);
   INSERT INTO schema_version VALUES (1, datetime('now'));
   ```
2. Crear `tasks_archive` (copia de `tasks` + columna `archived_at`) y migrar tareas `done`/`failed` >30 días.
3. Añadir `automatic INTEGER DEFAULT 0` a `task_events` y poblar en el productor de eventos (`motor/orchestration/api.py` / `task_queue.py`).

### P4 — Checkpoint y backup de BD (R4 · MEDIO)
1. WAL a fichero: `sqlite3 data/task_queue.db "PRAGMA wal_checkpoint(TRUNCATE);"` (con el servicio pausado o vía VACUUM).
2. Incluir `task_queue.db*` en `ura-backup.timer`/`ura-backup-mac.timer` (hoy `ura-backup-mac` corre pero no verifiqué que copie la BD).

### P5 — Estabilizar el repo (R5 · MEDIO)
1. Vavear o commitear los 18 untracked: priorizar `deploy/timers/ura-mutmut*.{service,timer}`, `scripts/pro/ura-worker-watchdog.sh`, `docs/udo/plans/PLAN_STRESS_TESTING_20260828.md`, `motor/example_util.py` (¿usado?).
2. Resolver los **2 stashes** (R6): revisar `scripts/pro/mutmut_daily.py` y `motor/core/utils/__init__.py` (+78 líneas); decidir merge (ya parcialmente recogido en `eebfabed` y commits de rama) o descartar con registro UDO.
3. Congelar la rama de trabajo para auditorías: solo auditar `main` cuando no haya agente de fondo commitando (usar `ura-despertador`/auditor como gate).

### P6 — Limpieza e integración (R7/R8/R9 · BAJO)
1. `ura-revisiones.service` fallido: revisar log `journalctl -u ura-revisiones` (sin revisor asignado) y reparar o retirar del timer.
2. Documentar la ruta real del log de cleanup en las guías de monitoreo (`/home/ramon/URA/logs/ura_cleanup.log`, no `/var/log/`), y ajustar permisos a `640` si se quiere leer por servicios de bajo privilegio.
3. Decidir sobre `merge-fase5` (~1058 commits) y `ramon/fase-1-excavacion`: integrar o archivar en `.attic/`.
4. **R9:** renombrar/crear el "Plan 1010" como artefacto formal si se quiere trazabilidad: proponer `docs/udo/plans/PLAN_1010.md` que consolide PLAN_DESARROLLO (F1-F4) + PLAN_STRESS_TESTING (F0-F8), para que PHIRAS-evaluaciones de fase tengan un único documento de referencia.

---

## 6. SERVICIOS Y ESTADO GLOBAL (contexto de la auditoría)

| Servicio | Estado |
|---|---|
| `ollama` (:11434) | Activo |
| `opencode.service` (Web + OpenClaw) + `.desktop` (:3000) | Activo |
| `model-router`, `ura-api`, `assistant`, `audit-api`, `mochila`, `voice`, `detector`, `go2rtc`, `qdrant`, `snc`, `swarm-discovery`, `llama-vision`, `tailscaled` | Activos |
| `ura-revisiones` | **FAILED** |
| Timers ura (18) | Todos activos |

---

*Fin de la auditoría industrial. Estado: 4 dominios revisados; 3 pendientes de verificar exclusivamente por bloqueo del nodo Mac (R1).*