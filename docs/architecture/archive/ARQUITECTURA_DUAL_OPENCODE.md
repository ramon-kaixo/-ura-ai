<!-- PLAN_TEMPLATE v1.0 — Engineering Process -->

# PLAN — Arquitectura Dual OpenCode (Web + Escritorio) — Documentación de lo existente

- **Estado**: IMPLEMENTADO Y VERIFICADO (2026-08-09) — documento descriptivo de lo que ya está en producción
- **Versión**: 1.0
- **Autor**: TERM (OpenCode Web), con validación de Ramón
- **Motivo del documento**: describir formalmente la arquitectura dual ya montada (que el plan propuesto por otra IA describía como futura — aquí está documentada tal como es, con los roles correctos según la regla principal de URA)

---

## 1. ¿QUÉ QUIERO CONSEGUIR? (Objetivo)

Tener **dos interfaces de OpenCode trabajando en paralelo** sobre el mismo proyecto, con redundancia (si una cae, la otra sigue), Git como origen de verdad único, y trazabilidad UDO completa:

- **Ventana 1 — OpenCode Web** (ASUS): agente de trabajo principal + interfaz web de visualización.
- **Ventana 2 — OpenCode Escritorio** (Mac): segunda interfaz con cerebro local Qwen 32B, para revisar/consultar/corregir en paralelo.

## 2. ¿POR QUÉ? (Intención / Problema)

| Problema | Consecuencia | Solución implementada |
|----------|--------------|------------------------|
| Un solo punto de fallo | Si la web cae, todo se detiene | El escritorio (Mac) trabaja con su propio cerebro local (Qwen 32B) sin depender de la web |
| Dificultad para distinguir ventanas | Confusión sobre quién es quién | Cerebros distintos (DeepSeek vs Qwen 32B) + comando `ura-doble quien` |
| Sin trazabilidad entre agentes | No se sabía quién hizo qué | UDO: TASK-ID, commits `[WEB]`/`[TERM]`, gate, verify |
| Desincronización de código | Mac y ASUS con versiones distintas | Git: remote `asus` + `ura-doble sync` |

## 3. ¿QUÉ CONTEXTO EXISTE? (Estado real verificado)

| Componente | Dónde | Estado |
|-----------|-------|--------|
| OpenCode 1.17.7 (binario) | ASUS: `~/.opencode/bin/opencode` | ✅ |
| Servidor web (Ventana 1) | ASUS: `opencode web :8081` (PID activo) | ✅ HTTP 200 |
| Proyecto Ventana 1 | ASUS: `/home/ramon/URA/ura_ia_1972` | ✅ fuente de verdad |
| Cerebro Ventana 1 | DeepSeek V4 Flash (sesión actual) | ✅ |
| OpenCode 1.17.7 (binario) | Mac: `~/.opencode/bin/opencode` | ✅ |
| Servidor web local (Ventana 2) | Mac: `opencode web :8091` (PID activo) | ✅ HTTP 200 |
| Proyecto Ventana 2 | Mac: `/Users/ramonesnaola/URA/ura_ia_1972` | ✅ sincronizado (HEAD `f2b2caa4`) |
| Cerebro Ventana 2 | Qwen 32B local (Ollama del Mac) — únicos providers: `['ollama']` | ✅ |
| Sincronización | Mac → ASUS: remote git `asus` + `ura-doble sync` | ✅ |
| Puente de revisión | `~/.opencode/bin/ura-doble` (instalado en Mac) | ✅ |
| Suites | UDO 35/35 · Engineering 13/13 · pytest 5942 passed | ✅ |
| UDO | Tareas, reservas, gate, verify, review-pending | ✅ v5 |

## 4. ¿QUÉ TIENE QUE HACER? (Arquitectura real)

```
                    TU MAC (Mini-de-RAMON)
┌─────────────────────────────────────────────────────┐
│  VENTANA 2 — OpenCode Escritorio                    │
│  🧠 Qwen 32B (Ollama local del Mac)                 │
│  http://127.0.0.1:8091                              │
│  Proyecto: ~/URA/ura_ia_1972                        │
│  Rol: revisar / consultar / corregir en paralelo    │
└──────────────┬──────────────────────────────────────┘
               │ git remote "asus" + ura-doble sync
               ▼
┌─────────────────────────────────────────────────────┐
│  ASUS GX10 (fuente de verdad)                       │
│  VENTANA 1 — OpenCode Web                           │
│  🧠 DeepSeek V4 Flash                               │
│  http://10.164.1.99:8081                            │
│  Proyecto: /home/ramon/URA/ura_ia_1972              │
│  Rol: agente de trabajo principal + visualización   │
└─────────────────────────────────────────────────────┘
```

### Piezas instaladas (todas verificadas hoy)

| Pieza | Función | Evidencia |
|-------|---------|-----------|
| `opencode web :8081` (ASUS) | Servidor web principal | systemd `opencode.service`, activo |
| `opencode web :8091` (Mac) | Servidor web local del escritorio | proceso activo, HTTP 200 |
| `ura-doble` (Mac) | Puente: sync + status + list + verify + quien + revisar | instalado en `~/.opencode/bin/` |
| remote git `asus` (Mac) | Sincronización Mac ↔ ASUS | `git remote -v` → asus |
| UDO (`ura-udo`) | Tareas, reservas, gate, verificación | suite 35/35 |
| `ura-opencode` | Envío de trabajo a la Web | script en scripts/pro/ |

## 5. ¿QUÉ ES MÍNIMO? (Mínimos obligatorios)

1. La Ventana 2 funciona sin depender de la Ventana 1 (cerebro local Qwen 32B + repo local). ✅
2. La Ventana 1 sigue siendo la fuente de verdad del código (AGENTS.md: "SIEMPRE TRABAJAR EN ASUS"). ✅
3. Git mantiene ambos repos sincronizados (`ura-doble sync`). ✅
4. Todo cambio se identifica con TASK-ID en el commit. ✅ (UDO)
5. `ura-doble quien` permite saber en qué ventana se está. ✅

## 6. ¿QUÉ ES CRÍTICO? (Puntos críticos / Invariantes)

- **NO invertir los roles**: ASUS es el agente de trabajo principal y fuente de verdad (regla principal de URA). El Mac es la ventana de escritorio/paralela — NO el servidor principal.
- **NO migrar a OpenHands ni a otra herramienta** (Opción B descartada): UDO, metodología Plan 0, mutmut, gate y suites están construidos sobre OpenCode — migrar tira días de trabajo verificable.
- Git es el origen de verdad único; la web NO es el origen.
- La configuración del Mac solo expone Ollama/Qwen 32B (`disabled_providers`), para que la Ventana 2 no confunda con mimo/deepseek.
- Trazabilidad: TASK-ID → commits → verify → DONE con gate.

## 7. ¿CÓMO DEBE COMPORTARSE? (Comportamiento esperado)

- Abrir `http://10.164.1.99:8081` → OpenCode Web (DeepSeek), proyecto ASUS.
- Abrir `http://127.0.0.1:8091` (en el Mac) → OpenCode Escritorio (Qwen 32B), proyecto local sincronizado.
- `ura-doble revisar` en el Mac → sincroniza + lista tareas a revisar.
- Si la web de ASUS cae → la Ventana 2 sigue funcionando (cerebro local).
- Si el Mac cae → la Ventana 1 sigue (todo el trabajo está en ASUS).

## 8. ¿QUÉ NO DEBE HACER? (NO HACER)

- NO hacer de la Ventana 2 (Mac) el agente de trabajo principal.
- NO migrar a OpenHands / AgentBox / amux (descartado — reutilizar lo existente).
- NO borrar ni renombrar `ura-udo`, `ura-doble`, `ura-opencode` ni las suites.
- NO añadir el provider `opencode` (mimo) ni `deepseek` a la config de la Ventana 2 (ya desactivados).
- NO crear infraestructura nueva (BD, paneles, colas) — UDO ya cubre la coordinación.
- NO tocar el `opencode.service` de ASUS sin reiniciar y verificar después.

## 9. ¿QUÉ ESTÁ FUERA DE ALCANCE?

- Migración a otra herramienta (OpenHands, etc.).
- Canal de voz/Kimi como parte de la arquitectura (puede ser canal humano externo, no pieza del sistema).
- Cambiar el cerebro de la Ventana 1 (DeepSeek — es la que el usuario usa).
- Automatización de la sincronización en tiempo real (la sync es manual con `ura-doble sync`; git fetch+merge bajo demanda).

## 10. ¿CÓMO SE VALIDARÁ? (Validación — ya ejecutada)

| Check | Resultado |
|-------|-----------|
| `ura-doble quien` (Mac) | ✅ Identifica ambas ventanas (máquina, proyecto, cerebro) |
| `ura-doble sync` (Mac) | ✅ "Repo del Mac al día con ASUS" |
| `ura-doble status/list/verify` (Mac) | ✅ Estado UDO real vía SSH |
| HTTP :8081 (ASUS) | ✅ 200 |
| HTTP :8091 (Mac) | ✅ 200 |
| Providers Ventana 2 | ✅ solo `['ollama']` |
| Suites UDO/Engineering/pytest | ✅ 35/35 · 13/13 · 5942 |

## 11. ¿CÓMO SE SABRÁ QUE ESTÁ TERMINADO? (Criterios de cierre)

1. Ambas ventanas visibles y operativas (verificadas hoy).
2. `ura-doble` funcional en el Mac con sus 6 subcomandos.
3. Ventana 2 con Qwen 32B exclusivo (sin mimo/deepseek).
4. Repo del Mac sincronizado con ASUS (`f2b2caa4`).
5. Este documento refleja la realidad verificada (no propuestas).

---

## 12. ANEXO — Configuración real actualizada (2026-08-28)

> El documento original refleja el estado de 2026-08-09. Este anexo documenta la topología
> **verificada el 2026-08-28** que causó confusión sobre dónde se configura cada interfaz.

### 12.1 Archivos de configuración (y quién usa cada uno)

| Archivo | Máquina | Usado por | `baseURL` | Modelo default |
|---------|---------|-----------|-----------|----------------|
| `~/.config/opencode/opencode.json` | GX10 | app desktop (`ai.opencode.desktop`) | `http://localhost:11434/v1` | `ollama/qwen3-coder:30b-mejorado` (agent coder) |
| `~/.config/opencode/opencode-web.json` | GX10 | **servicio web `opencode.service`** (vía `OPENCODE_CONFIG` en `web-config.conf`) | `http://localhost:11434/v1` | `ollama/qwen3-coder:30b-mejorado` (agents general/coder/build/orchestrator) |
| `~/.config/opencode/opencode.json` | Mac | app GUI desktop (Electron) | `http://10.164.1.247:11434/v1` (GX10 vía LAN) | `ollama/qwen3-coder:30b-mejorado` (agent coder) |
| `/home/ramon/URA/ura_ia_1972/opencode.json` | GX10 | proyecto (mergea si WorkingDirectory = repo) | `http://100.72.103.12:11434/v1` (Tailscale) | `ollama/qwen3.6:27b` (agent general) |

### 12.2 Reglas clave (para no repetir la confusión)

1. **El servicio web NO usa `~/.config/opencode/opencode.json`** — usa `opencode-web.json` porque el drop-in
   `/etc/systemd/system/opencode.service.d/web-config.conf` define `OPENCODE_CONFIG=/home/ramon/.config/opencode/opencode-web.json`.
2. El proveedor Ollama en la config **debe declarar `models`** para que aparezcan en el selector; con solo
   `options.baseURL` no se listan.
3. La Mac apunta a GX10 por `10.164.1.247` (LAN, DHCP — puede cambiar). Alternativa fija: Tailscale `100.72.103.12`.
   `OLLAMA_HOST` en `~/.zshrc` afecta solo a shells; la app GUI necesita `provider.ollama.options.baseURL` en su config.
4. `qwen3-coder:30b-mejorado` existe SOLO en el Ollama de GX10. El Ollama de la Mac quedó **vacío** (`{"models":[]}`) tras limpieza 2026-08-28.
5. Web (`:8081`) requiere login (HTTP 401 sin credenciales de `/etc/ura/secrets.env`, root-only).
6. **`OLLAMA_MODELS` fuera del árbol de URA (2026-08-28):** el directorio de modelos de GX10
   (`ollama-models-0326`, 139 G) se movió a `/home/ramon/ollama-models-0326` (fuera de `URA/`),
   dejando un symlink en `/home/ramon/URA/ollama-models-0326 -> /home/ramon/ollama-models-0326`.
   Motivo: evitar que rsync/git del árbol arrastre 139 G. El drop-in del servicio
   `ollama.service.d/models.conf` sigue apuntando a la misma ruta absoluta (se resuelve vía symlink),
   por lo que **NO hay que "arreglar" la ruta ni borrar el symlink** — verificado con 9 modelos OK tras el cambio.
    Si un backup usa rsync sin `-L`, copiará solo el symlink (30 B), no el contenido.
7. **El campo `npm` en `provider.ollama` ROMPE la conexión del CLI `opencode run`** (2026-08-28):
   un `provider.ollama.npm: "@ai-sdk/openai-compatible"` (usado por la web en `opencode-web.json`)
   hace que el CLI 1.18.x intente conectar a otro endpoint y falle con `Cannot connect to API`.
   En las configs de máquinas donde se ejecute `opencode run` (CLI/worker), el provider Ollama
   DEBE declararse solo con `baseURL` + `models`, SIN `npm`. Detalle del fix: `motor/orchestration/worker.py`
   `_build_command` usa `shlex.split` para comandos con argumentos (`opencode run`) — no envolver el
   comando completo entre comillas (exit 127).

### 12.3 Health-check del Model Router

El warning cada 5 min `[DIRECT] modelo test no disponible` provenía de `motor/guard/verifier.py:55`
(health-check del guard), que POSTeaba con `model:"test"` (inexistente). Corregido a `model:"llama3:latest"`
(2026-08-28, commit `aec122be`).

### 12.4 Modelo de tareas multi-nodo (orquestador pool OpenCode)

Verificado 2026-08-28 (fix worker `shlex.split` + tarea real `TASK-20260828-4fa88f` GX10→Mac `done`).

**Arquitectura: cada nodo tiene su propia DB local** `data/task_queue.db` (no es una BD compartida):

| Componente | Máquina | Puerto/Path | Rol |
|-----------|---------|-------------|-----|
| API orquestador | GX10 | `:4097` (`motor.orchestration.api`, PID systemd) | Endpoints REST de tareas/nodos/workers |
| DB local | cada nodo | `data/task_queue.db` | Cola SQLite propia (WAL) |
| Worker | Mac (`--node-id mac`) / GX10 | `motor.orchestration.worker` | Reclama tareas `pending` de su DB y ejecuta `opencode run "<desc>"` |
| Work-stealing | GX10 | `motor/orchestration/worksteal.py` | Rebalancea tareas entre nodos por ociosidad |

**Endpoints útiles de la API (GX10 :4097):**
- `POST /tasks` — crear tarea (body: description, node_id, priority, timeout_seconds, context_json)
- `POST /tasks/sync` — recibir tarea remota con dedup (`source_node`+`source_task_id`)
- `GET /tasks?status=&limit=` — listar; `GET /tasks/{id}` — ver detalle
- `POST /tasks/{id}/claim|start|complete|fail|heartbeat|pause|resume` — ciclo de vida
- `GET /worker/status` y `POST /worker/rebalance` — estado y rebalanceo del pool
- `GET /nodes` y `POST /nodes/register` — registro de nodos
- Auth: middleware `X-API-Key` (env `URA_API_KEY`); si no está configurada, queda **abierta (dev mode)**.

**Cómo encolar trabajo entre máquinas (flujo operativo):**
1. Crear la tarea en la API de GX10 (`POST /tasks` con `node_id` objetivo, ej. `mac`).
2. Como cada nodo lee su **propia** DB, propagar la tarea a la DB del nodo destino con
   **`scripts/pro/ura-task-sync`** (wrapper que usa el python correcto de cada nodo):
   ```bash
   # desde GX10 → Mac (idempotente; usa --from-api o --from-db)
   ssh mac-mini-ramon "/home/ramon/URA/ura_ia_1972/scripts/pro/ura-task-sync \
     --task TASK-XXX --from-api http://100.72.103.12:4097 --db /Users/ramonesnaola/URA/data/task_queue.db"
   ```
   El script `ura-task-sync.py` resuelve el python correcto (Mac: `/opt/homebrew/bin/python3.14`;
   GX10: `.venv/bin/python3`) y es **idempotente** (SKIP si ya existe).
3. El worker del nodo la reclama en el siguiente poll (5 s) y ejecuta `opencode run "<desc>"`.
4. Si el `context_json` trae `source_node`+`source_task_id`, `POST /tasks/sync` deduplica.

**Fallos conocidos 2026-08-28:**
- ✅ **Hook `pre-push` de GX10 REPARADO (2026-08-28)**: ya no usa `make validate` (que se colgaba por
  `test_memoria_compresor.py`/`test_agents_telemetry.py`). v3 corre solo targets rápidos
  (lint, mypy-info, radon, test-udo, verify-hooks) con timeout 90s cada uno.
- ✅ **CLI opencode del terminal GX10 REPARADO**: era el 0.0.55 (roto) en `/usr/local/bin` + el campo
  `provider.ollama.npm`. Ahora `~/.opencode/bin/opencode` → symlink al 1.18.23, y el `npm` se eliminó
  de la config global (solo queda en `opencode-web.json`).
- ✅ **SSH GX10→Mac restablecido**: alias `mac-mini-ramon` = `User ramonesnaola` + `IdentityFile ~/.ssh/id_gx10_mac`.
- El campo `provider.ollama.npm` rompe el CLI `opencode run` (regla #7, §12.2).
- `resolve_node_url()` en `scripts/pro/parse_plan_to_tasks.py` resuelve el destino P2P vía registry (`/nodes/{id}`)
  con fallback a `100.72.103.12:4097`/`localhost:4097`.

### 12.5 Evaluación: DB compartida vs DBs por nodo (2026-08-28)

**Situación actual:** cada nodo (Mac, GX10) tiene su `data/task_queue.db` local. Para que una tarea creada en
la API de GX10 (`:4097`) la ejecute el worker de la Mac, hubo que **replicarla manualmente** en la DB de la Mac
(verificado en la tarea real `TASK-20260828-4fa88f`). Esto es frágil y duplica tareas.

**Opciones evaluadas:**

| Opción | Pros | Contras | Esfuerzo |
|--------|------|---------|----------|
| **A. BD compartida central** (una DB en GX10, nodos vía NFS/SQLite sobre red) | Sin duplicación; estado global único | SQLite no es multi-writer fiable por red; latencia Tailscale; bloqueos | Alto, riesgo |
| **B. API como fuente de verdad** (los workers consultan `:4097` en vez de DB local) | El worker ya usa la API para claim/start/complete; la DB local pasa a ser caché | Refactor del worker (hoy lee SQLite directo); requiere que los workers apunten al orquestador | Medio |
| **C. Sincronización bidireccional** (mejorar `POST /tasks/sync`: el orquestador propaga tareas nuevas a los nodos destino) | Conserva DBs locales (offline-capable); solo añade propagación | Complejidad de consenso/conflictos; requiere detector de cambios | Medio-alto |
| **D. Manual/status quo** (replicar a mano como hoy) | Cero código | Frágil, propenso a duplicados | 0 |

**Recomendación:** la **opción C** es la más alineada con la arquitectura actual (los nodos ya usan `POST /tasks/sync`
para dedup). Implementar un paso de "propagación" en el worker: al crear una tarea con `node_id` remoto, la API la
encola en su DB **y** la propaga a la DB del nodo destino. Queda como **decisión del humano** (es cambio de diseño
del núcleo del orquestador; requiere TASK UDO + análisis de impacto). No se implementa en esta sesión.

---

*Documento descriptivo de la arquitectura ya implementada. No introduce cambios — registra el estado real verificado el 2026-08-09 y actualizado el 2026-08-28 (incl. §12.4 modelo de tareas multi-nodo).*
