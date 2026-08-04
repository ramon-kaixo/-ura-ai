# Plan Maestro de la Tuneladora — Auditoría completa (ADN del proyecto)

**Fecha:** 2026-08-04
**Fuente:** Análisis de código real (`scripts/pro/tuneladora/`, ~3,800 stmts, 566 tests, 89.6% cobertura)

---

## 1. ¿Qué está automatizado?

### 1.1 Scheduler systemd (ura-watch-daemon.service + ura-watch-daemon.sh)
`scripts/pro/tuneladora/scheduler_daemon.py` ejecuta 3 pipelines programados:

| Pipeline | Intervalo | auto_execute_safe | Qué hace |
|---|---|---|---|
| `health` | 5 min | ✅ | health_disk + limpieza logs si < 50GB libre |
| `cleanup` | 60 min | ✅ | vacuum_sqlite + cleanup_embeddings |
| `audit` | 360 min | ❌ | solo propone (no ejecuta sin aprobación) |

Además el daemon levanta el Dashboard web en :9092.

### 1.2 Watchers (ura-watcher + ura-watcher-auditoria + watchdog_buffer)
- `ura-watcher.service`: indexa cambios de archivos en tiempo real (inotifywait)
- `ura-watcher-auditoria.service`: dispara auditoría al recibir datos
- `watchdog_buffer.sh`: vigila el buffer de 30GB

### 1.3 Timers systemd activos
- `ura-watchdog.timer` — cada 5 min (ejecuta ura-watchdog.service)
- `ura-maintenance-v2.timer` — cada 6h (tuneladora de mantenimiento)
- `ura-pipeline.timer` — cada 5 min
- `ura-memory-watchdog.timer`, `ura-mochila-guard.timer` — cada 5 min

### 1.4 Git hooks (pre-commit)
- `commit-msg` → validación de formato
- `post-commit` → change_log
- `pre-push` → orchestrator (make validate)

### 1.5 Fases del pipeline que corren solas (sin intervención)
`PipelineRunner.run()` ejecuta automáticamente: preflight → snapshot → static → refactor (plugins) → Sofia → dynamic → api_diff → index → integrity → commit (SKIP) → plugin post → verdict → rollback automático si FAIL → memoria → reporte JSON.

---

## 2. ¿Qué usa IA? (LLM local)

**Endpoint:** `http://localhost:11434` (Ollama, configurable: `URA_OLLAMA_HOST/PORT`)

| Componente | Endpoint | Modelo | Temperatura | Cuándo | Prompt que envía |
|---|---|---|---|---|---|
| **Sofia** (`sofia.py`) | `/api/generate` | `qwen2.5-coder:14b` (cfg.sofia_model) | **0** (determinista, seed 42) | Modos gate/fix, entre static y dynamic | Revisa el diff con markers `___SOFIA_DIFF___`, `___SOFIA_TESTS___`, `___SOFIA_API___`; pide JSON `{hallazgos:[{tipo,archivo,linea,mensaje,sugerencia}], resumen}` |
| **LLMFallback** (`llm_fallback.py`) | `/api/generate` | `qwen2.5-coder:14b` (TUNEL_LLM_FALLBACK_MODEL) | (por defecto) | Cuando ruff/pytest fallan en una fase | Pide UN diff patch unificado del error; `num_predict` ajustado por `ajustar_contexto.estimar_tokens` |
| **BlockReviewer** (`block_reviewer.py`) | `/api/generate` | cfg.review_model | (por defecto) | Revisión por bloques (thread en background) | Pide reporte markdown del diff |

**Qué recibe:** texto (respuesta del modelo) — nunca se parsea ejecutable, solo texto/diff/JSON.

**Límites:** `llm_retries = 2` (3 intentos); si Ollama no responde → `pending_fixes` con estado `imposible` (no reintenta).

---

## 3. ¿Qué es manual? (requiere Ramón)

| Acción | Comando |
|---|---|
| Ejecutar tuneladora a demanda | `make tuneladora` (modo check) |
| Validación completa | `make validate` (~6.5 min) |
| Lint estricto | `make lint-strict` |
| Auditoría | `make audit` |
| Commit (con hooks) | `git add <archivo> && git commit` |
| Gate de calidad de código | `python3 scripts/pro/quality_gate.py` |
| Servicios systemd | `systemctl status/start/stop ura-watch-daemon ura-watcher...` |
| Aprobación de auto-commit | **DESACTIVADO por diseño** — `phase_commit` devuelve SKIP siempre (regla de aprobación humana, ver comentario en runner.py) |

**Nada commitea código automáticamente.** El auto-commit está deliberadamente desactivado.

---

## 4. Arquitectura del pipeline (flujo completo)

```
OpenCode Web (Ramón)
   │  "genera módulo X" → escribe archivos .py/.json
   ▼
git add <archivos> + git commit
   │  hooks: commit-msg (formato) + post-commit (change_log)
   ▼
TUNELADORA (make tuneladora / scheduler / watch daemon)
   │
   ├─ 1. _acquire_lock  → .tuneladora/pipeline.lock (pid + timestamp; lock de PID muerto se sobrescribe)
   ├─ 2. preflight      → ¿ruff/pytest/bandit/mypy disponibles? (por modo)
   ├─ 3. plugin_registry "pre"  (gate/fix)
   ├─ 4. phase_snapshot → snapshot delta (openclaw_firmador)
   ├─ 5. phase_static   → py_compile → ruff → bandit → mypy (con retry)
   ├─ 6. plugin_registry "refactor" (gate/fix)
   ├─ 7. SOFIA (LLM)    → review del diff → WARN si hallazgos (gate/fix)
   ├─ 8. phase_dynamic  → pytest (tests enfocados o suite completa) + LLMFallback si falla
   ├─ 9. phase_api_diff → compara API actual vs HEAD (funciones eliminadas/cambiadas)
   ├─ 10. phase_index   → extrae funciones/clases → aprende en memoria semántica
   ├─ 11. phase_integrity → blast radius, test_manipulation, disco
   ├─ 12. phase_commit  → SKIP (desactivado)
   ├─ 13. plugin_registry "post" (gate/fix)
   ├─ 14. phase_verdict → FAIL si hay fail; WARN si hay warn; si FAIL → rollback snapshot automático
   ├─ 15. _finish       → memoria episódica + LTM + change_log + auditoria_continua
   └─ 16. reporte JSON  → data/tuneladora_reports/<episode_id>.json
   ▼
SUPERVISOR (ura-watchdog.timer 5min + auditoria_continua)
   │  lee reporte JSON → detecta regresiones → guarda alertas en memoria episódica
   ▼
RAMÓN (revisa, decide, commitea lo validado)
```

**Modos:** `check` (detección, no bloquea), `fix` (auto-corrige con LLM), `gate` (bloquea si falla + Sofia).

---

## 5. Puntos de conexión

### 5.1 Tuneladora ↔ Memoria

| Capa | Clase/DB | Dónde escribe | Qué datos |
|---|---|---|---|
| Episódica | `EpisodicMemory` → `knowledge/episodic.db` | `_finish()` línea 798 | Un episodio por ejecución: episode_id, pipeline, status, summary, details, duration_ms |
| Largo plazo | `LongTermMemory` → `knowledge/ltm.db` | `_finish()` (si OK) + `phase_integrity` | LTMEntry: key `ok_<episode_id>`, files, duration, msg; tags (pipeline, ok) |
| Semántica | `SemanticMemory` → `knowledge/knowledge.db` | `phase_index` líneas 429-439 | Concept (función/clase del código) + Relation (calls) |
| Corto plazo | `ShortTermMemory` (cache, TTL 60s) | `phase_dynamic` | Resultados de pytest enfocado (cache 120s) |

**Nota:** las memorias de la tuneladora son las de `scripts/pro/tuneladora/memory/` — separadas de `core/memoria/` y `motor/intelligence/memory/` (ver docs/MEMORIA.md — no son duplicados).

### 5.2 Tuneladora ↔ Supervisor
- **Al terminar cada ejecución** (`_finish`): llama `auditoria_continua.run_all()` → score en log
- **Check "Regresiones tuneladora"** (auditoria_continua): lee `data/tuneladora_reports/` (último + anterior) → detecta FAIL/cobertura/tests → guarda alertas en `EpisodeStore` (motor/intelligence/memory/episodic)
- **Frecuencia**: cada ejecución de tuneladora + cada `make audit` + ura-watchdog.timer cada 5 min
- **quality_gate.py** (independiente): lee el mismo reporte y da ACCEPTED/REJECTED

### 5.3 Tuneladora ↔ SQLite/Qdrant
- **SQLite** (las 3 DBs de tuneladora): `knowledge/knowledge.db` (semántica + pending_fixes + tuneladora_runs), `knowledge/episodic.db`, `knowledge/ltm.db`
- **Qdrant**: configurado (`URA_QDRANT_HOST/PORT`, localhost:6333) pero la tuneladora NO lo usa directamente — la capa semántica es SQLite local. Qdrant lo usan core/memoria y knowledge/engine.

### 5.4 Tuneladora ↔ LLM local
Endpoint `http://localhost:11434/api/generate`, modelo `qwen2.5-coder:14b`, Sofia con temperature 0/seed 42, timeout `timeout_llm`, 3 intentos máx, fallback → pending_fixes "imposible".

---

## 6. Formatos de datos

### JSON que genera
| Archivo | Contenido |
|---|---|
| `data/tuneladora_reports/<episode_id>.json` | **Reporte principal**: episode_id, pipeline, mode, verdict, summary, files, duration_ms, telemetry (head, duration_s, n_files, sofia_*), sofia {criticos, advertencias}, timestamp |
| `.tuneladora/pipeline.lock` | {pid, start, mode} |
| `.tuneladora/repo_index.json` | Índice semántico: stats {functions, classes, relations, files} + sources {funcs, calls} |
| `.tuneladora/patches/<ts>_<file>.diff` | Parches LLM del fallback |
| `.nervioso/ledger/<execution_id>.json` | Ledger de ejecución (append-only) |
| `.nervioso/audits/audit_<ts>.json` | Historial de auditorías (con health_index) |

### SQLite (pending_fixes + tuneladora_runs)
`pending_fixes`: id, created_ts, bloque, archivo, herramienta, severidad, error_raw, sugerencia_llm, estado (pendiente/hecho/imposible), intentos
`tuneladora_runs`: ts, model, mode, verdict, seconds, n_files, head, failures

### JSON que lee
- `auditoria_continua.leer_ultimo_reporte_tuneladora()` → reportes del runner
- `quality_gate._buscar_reportes_json()` → reportes del runner + `.tuneladora/snapshots/*/meta.json`
- `generate_index` → escribe repo_index.json

---

## 7. Gaps (para flujo automático OpenCode → repo sin terminal)

| # | Gap | Impacto |
|---|---|---|
| 1 | **Auto-commit desactivado** (phase_commit SKIP) | El ciclo termina en el reporte; el código validado NO entra al repo solo — requiere commit manual de Ramón |
| 2 | **make tuneladora manual** — no hay hook que ejecute la tuneladora tras `git commit` | El código se commitea SIN pasar la tuneladora (los hooks actuales no la ejecutan) |
| 3 | **El reporte JSON no llega a nadie**: nadie notifica (Telegram/email) si verdict=FAIL | El fallo queda en el log/reporte; Ramón debe mirar |
| 4 | **quality_gate no está conectado** a ningún hook/CI | Existe pero nadie lo ejecuta |
| 5 | **Verificación de Cobertura en el reporte**: el runner no incluye coverage real en telemetry | `detectar_regresiones` y `quality_gate` no pueden evaluar cobertura (campos opcionales) |
| 6 | **phase_commit código muerto**: el bloque tras el SKIP inicial nunca se ejecuta | Deuda: ~40 líneas inalcanzables |

**Solución propuesta (para fase post-núcleo):** hook `pre-commit` o `post-commit` que ejecute `tuneladora --mode check --files <changed>` y bloquee el commit si FAIL (gate), o notificación por notifier.py cuando verdict=FAIL.

---

## 8. Riesgos (qué puede romper si modificamos X)

| Si modificas... | Riesgo |
|---|---|
| `runner.run()` (orden de fases) | El pipeline completo depende del orden: snapshot antes que static (rollback), Sofia entre static y dynamic, integrity al final. Cambiar el orden rompe el flujo de rollback |
| `phase_commit` (reactivar auto-commit) | **Violaría la regla de aprobación humana** (ADR pendiente documentado en el código). Riesgo de commits no revisados |
| Lock (`_acquire_lock`) | Dos tuneladoras concurrentes corrompen DBs; el lock de PID muerto ya está resuelto (liveness) pero el timeout de 1800s sigue para procesos vivos largos |
| Memoria (paths de DBs) | Cambiar `knowledge/*.db` rompe el histórico de episodios/LTM; las DBs son la memoria del sistema |
| LLM (sofia temperature>0) | Sofia deja de ser determinista → hallazgos no reproducibles entre ejecuciones |
| Modos (rules del preflight) | Si `check` exige bandit/mypy, el pipeline aborta en entornos sin esas herramientas |
| `_finish` (orden de escrituras) | El episodio + LTM + reporte + auditoria deben persistir en ese orden; el reporte JSON es la fuente del supervisor |
| `generate_index`/`phase_index` | La memoria semántica (conceptos del código) se corrompe con índices parciales |
| **Scheduler/daemon systemd** | Si el daemon se reinicia a mitad de un pipeline, el lock queda (ya recuperable por liveness); el pending_queue recupera jobs |

---

## Resumen ejecutivo

La tuneladora es un **pipeline de validación completo** (16 fases) que: valida código con herramientas locales (ruff/pytest/bandit/mypy), usa el LLM local para revisar diffs y generar parches, guarda TODO en 4 capas de memoria, genera reportes JSON, y se ejecuta por scheduler (5/60/360 min) o manualmente. **El único paso deliberadamente manual es el commit** — por diseño. El siguiente paso natural es conectar la tuneladora a un hook de commit (gate automático) y notificar fallos.
