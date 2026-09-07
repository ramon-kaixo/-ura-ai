# INFORME — INVESTIGACIÓN PROFUNDA DEL ECOSISTEMA OPENCODE URA

**Fecha:** 2026-08-28
**Nodos auditados:** GX10 (este host, NVIDIA DGX Spark; "ASUS" en scripts) · Mac (Mini-de-RAMON). **No existe un nodo Windows en URA**: las referencias a "caja0/ASUS Windows" eran un residuo de un POS legacy (ver §5).
**Objetivo:** dibujar la "foto" completa de todas las instancias de OpenCode, el orquestador, el "modo oculto", la generación de código simultánea, y unificar los agentes de todas las instancias (TASK-20260828-unificacion-agentes).

---

## 1. FOTO DEL ECOSISTEMA (estado a 2026-08-28 ~20:20)

| Nodo | Instancia | Version | Config | Forma de arranque | Estado |
|---|---|---|---|---|---|
| GX10 | Desktop `ai.opencode.desktop` (tty2) | 1.18.21 | `~/.config/opencode/opencode.json` + proyecto | manual (Xorg :0) | ✅ activo (PID 2591706) |
| GX10 | **Web headless ("modo oculto")** `opencode web --port 8081` | 1.18.23 | `~/.config/opencode/opencode-web.json` (override `OPENCODE_CONFIG`) | systemd `opencode.service` | ✅ activo (PID 3947635), auth 401 |
| GX10 | CLI `opencode` en PATH | 0.0.55 | — | — | custom |
| Mac | Desktop `OpenCode.app` (Apple Silicon) | 1.18.22 | `~/Library/Application Support/opencode/opencode.json` + proyecto `~/URA/opencode.json` | lanzamiento manual | ✅ activo (PID 84441) |
| Mac | Web headless `opencode web --port 8091` (TERM) | 1.18.23 | global + proyecto `~/URA/opencode.json`, cwd `~/URA` | launchd `com.ura.opencode-term` (KeepAlive) | ✅ activo (PID 84277), HTTP 200 |
| Mac | CLI `~/.opencode/bin/opencode` | 1.18.23 | — | — | OK |

> **Resuelto (TASK-20260828):** no hay nodo Windows. "caja0/ASUS Windows" era una referencia heredada de un agente POS legacy que quedó fuera de URA. Ver §5.

**Orquestador API (cola de tareas):** `URA_ORCHESTRATOR_URL` = `http://localhost:4097` (GX10) / `http://100.72.103.12:4097` (Mac). Núcleo en `motor/orchestration/` (api.py, worker, failover, task_queue).

---

## 2. EL "MODO OCULTO" (headless) — RESUELTO

Lo que el usuario recordaba como "modo oculto que no se ve" = **OpenCode web headless corriendo en segundo plano como servicio**:

- **GX10:** unit `opencode.service` → `ExecStart=... opencode web --port 8081 --hostname 0.0.0.0` + `EnvironmentFile=/etc/ura/secrets.env` + override `OPENCODE_CONFIG=/home/ramon/.config/opencode/opencode-web.json` (`/etc/systemd/system/opencode.service.d/web-config.conf`). Autenticado (HTTP 401 sin credenciales). Same concepto en `deploy/opencode.service`.
- **Mac:** launchd `com.ura.opencode-term` → `opencode web --port 8091`, KeepAlive, logs en `/tmp/opencode-term.{out,err}`. Este es el "TERM".
- **Modo fondo automático:** `deploy/engineering/AGENTS.md.global` documenta el protocolo `[WEB]` (OpenCode Web en ASUS) / `[TERM]` (OpenCode Web/desktop en Mac) + despertador `deploy/mac/despertador-fondo.sh` que cada 30 min (`launchd com.ura.fondo-wake`) envía "MODO FONDO" vía `opencode run --attach` y usa el agente `revisor-fondo` con write/edit DESHABILITADOS por configuración (v1.8).
- **Impulsor CLI:** `scripts/pro/ura-opencode` lanza `opencode run --attach http://100.72.103.12:8081 --username ramon --password $OPENCODE_WEB_PASS -m ...` tras crear la tarea UDO e inyectarle el contexto.

**Conclusión:** el "modo oculto" existe y son las instancias web headless de GX10 (:8081) y Mac (:8091). Ambas usan configs globales por nodo y pueden escribir código (permisos allow-all expeditos en las configs web/global).

---

## 3. EL ORQUESTADOR / "AGENTE DE PROYECTO" QUE CONECTA LOS OPENCODE — RESUELTO

El "agente de proyecto para consultar todos los OpenCode" es el **agente `orchestrator`**, creado/evolucionado el 27-ago (commits en `main`):

- `0a2222aa` — orchestrator agent + `configure_single_node.sh` + `setup_orchestrator_mode.sh` (para 3 nodos).
- `32236856` — `parse_plan_to_tasks.py` + comando `/orchestrate` + orchestrator v2.
- `0f4d4894` — distribución P2P (`POST /tasks/sync`), detección automática PLAN vs ORDEN LOCAL, node registry, `--distribute`.
- `a5fe8e4a` / `06beaf85` — `docs/udo/coordination.json` (agentes TERM/WEB, colas, modo secuencial/paralelo).

**Flujo real:**
1. Usuario escribe `/orchestrate plan.md` (o el agente orchestrator detecta un PLAN por `##`/`- [ ]`/listas numeradas).
2. `parse_plan_to_tasks.py` convierte el plan en tareas vía API `POST /tasks`.
3. El orquestador reparte por nodo (`Nodo: gx10|mac`), reclamadas por los workers (`ura-taskqueue.service` en GX10, `com.ura.taskqueue` en Mac).
4. `ura-opencode`/`ura-doble`/`ura-udo` puentean: crean expediente UDO en git, inyectan contexto, lanzan `opencode run --attach` al WEB/TERM, y pasan a REVIEW.

**Lógica del agente `orchestrator` (`.opencode/agents/orchestrator.md`):**
- Decide PLAN (se distribuye) vs ORDEN LOCAL (se ejecuta aquí).
- `model: ollama/qwen3.6:27b`, `permission: edit deny, bash: curl/git/python3 allow, * ask`.
- Excepciones `!local COMANDO` y `!shell`.

**¿Todos los OpenCode pueden generar código? SÍ:**
- Configs globales/web/proyecto: `permission` allow-all con `edit/write/bash/task` permitidos.
- `general`, `coder` y `build` tienen write/edit. El único sin escritura es `orchestrator` (a propósito: crea tareas, no toca código). `revisor-fondo` es solo-lectura por configuración (v1.8).

---

## 4. AGENTES POR NODO — COMPARATIVA (ESTADO FINAL TRAS TASK-20260828)

Los agentes viven en dos sitios: `agent:` dentro de los `.json` de config (global/proyecto) y archivos `.md` en `.opencode/agents/` (proyecto, via git → idénticos en GX10 y Mac).

### Conjunto canónico (idéntico en las 4 instancias)
| Agente | Modo | Modelo | Escritura |
|---|---|---|---|
| `general` | primary | `ollama/qwen3-coder:30b-mejorado` | sí (all tools) |
| `coder` | primary | `ollama/qwen3-coder:30b-mejorado` | sí (all tools) |
| `orchestrator` | primary | `ollama/qwen3-coder:30b-mejorado` | **no** (edit/webfetch/websearch deny) |
| `build` | primary | `ollama/qwen3-coder:30b-mejorado` | sí (all tools) |
| `revisor` | subagent | hereda | — |
| `calidad-cobertura` | subagent | hereda | — |
| `revisor-fondo` | subagent | `ollama/qwen3.6:27b` | **no** (write/edit/bash deny; solo git/cat/curl) |

+ builtins `plan`, `compaction`, `explore`, `summary`, `title` en todas las instancias.

### Verificación (2026-08-28, `opencode agent list` v1.18.23)
- **GX10** (desktop + proyecto): `build, calidad-cobertura, coder, general, orchestrator, revisor, revisor-fondo` + builtins.
- **Mac** (desktop + proyecto, ~/URA): **idéntico** — misma lista exacta, mismas reglas (orchestrator: edit/webfetch/websearch deny; revisor-fondo: write/edit/bash deny; coder: sin denies).
- **Configs alineadas:** global GX10 (`~/.config/opencode/opencode.json`), web GX10 (`opencode-web.json`), global Mac (`~/.config/opencode/opencode.json` **y** `~/Library/Application Support/opencode/opencode.json`), y `opencode.json` proyecto (default_agent → `general`).

### Qué cambió (deltas detectados y corregidos)
| Antes | Después |
|---|---|
| GX10 desktop: `coder` sin task/webfetch/websearch | coder con all tools (verificado) |
| GX10 desktop: `orchestrator` con write/edit true | orchestrator write/edit false |
| GX10 desktop: `default_agent: coder` | `default_agent: general` |
| `build` solo en `opencode-web.json` | `build.md` en proyecto + bloque en globales GX10/Mac |
| Mac: dos configs globales en conflicto (`~/.config` vieja con `default coder` y `~/Library/…` con agentes) | ambas configuración canónica |
| Mac: sin `revisor-fondo` ni `build` | creados (`revisor-fondo.md`, `build.md`) y copiados al worktree Mac |
| `orchestrator.md` modelo `qwen3.6:27b` | `ollama/qwen3-coder:30b-mejorado` |

Comandos (`.opencode/commands/`): `alarma, audit, cobertura, orchestrate, parallel-status, status, sync, test`.
Planes (`.opencode/plans/`): roadmap F29+F35, ASSISTANT_IMPROVEMENTS, ROADMAP_F29_F35, motor_conocimiento, etc.

---

## 5. NODO "ASUS WINDOWS" (caja0) — RESUELTO: NO ES UN NODO URA

El "tercer nodo" no existe: **URA tiene solo dos nodos OpenCode (GX10 y Mac)**. La IP `100.127.217.113` ("caja0", etiquetada "Windows POS") era una referencia heredada de un antiguo agente de telemetría POS (`ura-telemetry-pos.ps1`) que quedó fuera del ecosistema. Nunca se configuró como nodo OpenCode (`configure_single_node.sh` / `setup_orchestrator_mode.sh` solo soportan `gx10|mac`).

**Actuación (TASK-20260828, Parte 3):** eliminadas o neutralizadas las referencias a caja0/ASUS-Windows:
| Archivo | Cambio |
|---|---|
| `AGENTS.md` | `ura-telemetry-pos.ps1` descrito como legacy desactivado (sin caja0) |
| `scripts/pro/maquinas.sh` | bloque caja0 eliminado |
| `scripts/pro/tailscale-acls.json` | regla `tag:pos → master:8002`, `tagOwners.pos`, hosts `pos` eliminados |
| `docs/architecture/REFERENCIA_GX10.md` | flujo de datos genérico ("agente POS externo"), sin caja0/MagicDNS |
| `scripts/pro/ura-telemetry-pos.ps1` | header normalizado a "nodo externo (legacy)"; funcionalidad intacta |
| `INFORME_INVESTIGACION_OPENCODE_20260828.md` | este documento regenerado |
| `config/dispositivos.json` | ⛔ **BLOQUEADO**: archivo `chattr +i` (inmutable, commit `755dc7f8`). Requiere `sudo chattr -i config/dispositivos.json` para eliminar la entrada → pendiente humano |

**Restos intencionadamente conservados (históricos/auto-regenerados):** `.attic/.../deploy_copilotos.sh` (archivo en el ático) y `.nervioso/auditoria_router.json` (snapshot runtime de ura-router, se regenera). `AGENTS.md.v0.30.0` es una copia versionada histórica (no se edita).

**Normalización de nomenclatura:** "ASUS" = el GX10 en todos los scripts (`ura-doble`, `transition_contraste.sh`, `REFERENCIA_GX10.md`). No hay ambigüedad con ningún dispositivo Windows.

---

## 6. BUG CODWIKI EN MAC — DIAGNÓSTICO Y ARREGLO APLICADO ✅

**Diagnóstico (doble causa):**
1. `opencode.json` del **proyecto** (archivo compartido por git, presente en GX10 y Mac) hardcodeaba `mcp.codewiki.command = ["/home/ramon/.npm-global/bin/codewiki-mcp"]` → ruta solo válida en GX10.
2. En el Mac **el binario no existía** ni en la ruta del config global (`/Users/ramonesnaola/.npm-global/bin/codewiki-mcp` no estaba). El MCP fallaba siempre, por dos configs distintas.

**Arreglos aplicados (2026-08-28 ~20:00–20:15):**
| Archivo | Cambio |
|---|---|
| `opencode.json` (proyecto GX10) | eliminado bloque `mcp` (config del proyecto vuelve a ser neutra por nodo) |
| `~/URA/opencode.json` (proyecto Mac) | idem: `mcp` eliminado |
| Mac | instalado `codewiki-mcp@1.1.2` en `~/.npm-global` (vía `/opt/homebrew/bin/npm`, node 25.9.0) → ruta del config global del Mac ahora existe |
| `~/.config/opencode/opencode.json` (global GX10) | añadido `mcp.codewiki` → ruta GX10 (el desktop de GX10 no pierde el MCP) |
| `scripts/pro/sync-opencode-config.sh` | ahora escribe el MCP con ruta correcta **por nodo** (Mac Desktop y GX10 Desktop) para que futuras sincronizaciones no lo borren |

**Verificación:** JSON válido en los 3 configs tocados; `bash -n` OK en el script; en Mac handshake MCP stdio completo (initialize → `serverInfo codewiki-mcp 1.1.2`, `tools/list` → `codewiki_search_repos`, `codewiki_fetch_repo`, …).

---

## 7. HALLAZGO ADICIONAL — CWD ROTA DEL TERM (Mac) ⟶ ARREGLADA ✅

El launchd `com.ura.opencode-term.plist` tenía `WorkingDirectory = /Users/ramonesnaola/URA/ura_ia_1972`, un directorio **vacío y NO repo** (con restos `config/`, `core/`, `docs/`, `mantenimiento/` creados hoy 17:32–17:40 por sesiones del TERM operando en el sitio equivocado). El repo real del Mac está en `~/URA`.

**Arreglo:** `plutil -replace WorkingDirectory -string /Users/ramonesnaola/URA ...` y reinicio vía `launchctl kickstart -k gui/$(id -u)/com.ura.opencode-term`. PIDs: 1849 → 84277. HTTP 200 ✓.
**Nota:** el scaffolding vacío `~/URA/ura_ia_1972/{config,core,docs,mantenimiento}` queda sin borrar (decisión del usuario).

---

## 8. REINICIOS APLICADOS PARA CARGAR CONFIGS

| Instancia | Antes | Después | Verificación |
|---|---|---|---|
| Mac web TERM :8091 | PID 1849 (config vieja, cwd rota) | PID 84277 | curl → 200; cwd = `~/URA` |
| Mac desktop OpenCode.app 1.18.22 | PID viejo | PID 84441 | proceso vivo |
| GX10 desktop 1.18.21 | PID 4111409 | PID 2591706 | proceso vivo |
| GX10 web headless :8081 | — | sin cambio (config sin tocar) | active, auth 401 |

---

## 9. OTROS HALLAZGOS ANOTADOS EN LA AUDITORÍA PREVIA (no tocados)

- Mac: Ollama **local** no corre (`http://127.0.0.1:11434` no responde); el Mac usa el endpoint remoto de GX10 (`100.72.103.12:11434` / `10.164.1.247:11434`) que sí funciona.
- `opencode.json` del proyecto GX10 señala Ollama a `http://10.164.1.247:11434/v1` (IP wifi LAN del GX10); funciona en LAN pero no es la IP estable Tailscale exportada en las configs globales.
- `.opencode/project.json` en GX10 dice `"path": "/Users/ramonesnaola/URA/ura_ia_1972"` (ruta del Mac en una máquina Linux) — heredado de la sincronización; opencode lo usa como hint de proyecto.
- `ura-revisiones.service` (GX10) estaba **FAILED**.
- Historial en `data/task_queue.db`: 19 tareas, 17 en `failed`, WAL 1.38 MB sin checkpoint.
- Histórico de errores de conexión del OpenCode.app del Mac (322× `AI_APICallError … AggregateError`) se debía a config vieja en memoria (arranque 02:45, config corregida 03:07); tras reinicio queda resuelto.
- Provider `deepseek` con `Insufficient Balance` en una config previa (ya no se usa; todo Ollama local).

---

## 10. RECOMENDACIONES

1. **Desbloquear `config/dispositivos.json`** (pendiente humano): `sudo chattr -i config/dispositivos.json` y eliminar la entrada `caja0` para completar la Parte 3.
2. **Reiniciar el web headless de GX10** (pendiente humano, necesita sudo/root): `sudo systemctl restart opencode.service` para que cargue `opencode-web.json` alineado (orchestrator sin webfetch/websearch). El TERM del Mac ya quedó alineado (config global).
3. **Reiniciar el OpenCode.app del Mac** cuando convenga: la GUI activa mantiene la config vieja en memoria (solo se aplicará en sesiones nuevas).
4. **Unificar baseURL de Ollama** por nodo usando IPs Tailscale (`100.72.103.12:11434`) en lugar de `10.164.1.247` (LAN) en `opencode.json` de proyecto.
5. **Corregir `.opencode/project.json`** por nodo (o dejarlo fuera del control de versiones): apunta a una ruta del Mac en una máquina Linux.
6. Checkpoint del WAL de `data/task_queue.db` y revisión del historial de tareas `failed` (ruido E2E del 27-ago; purga opcional pendiente de aprobación).

---

## 11. HISTORIAL DE MODIFICACIONES (auditoría Parte 1 — TASK-20260828)

### `opencode.json` del proyecto (git)
| Commit | Fecha | Cambio |
|---|---|---|
| `d8328526`/`aaf3d158` | 26-08 | fijado modelo default `ollama/qwen3-coder:30b-mejorado` (tras revert piloto) |
| `411992c3`/`a0b91255` | 26-08 | revert del cambio de modelo default |
| `7ad16984` | 26-08 | configuración completa: commands, features, provider, references, permisos |
| `eebfabed` | 27-08 | pause/resume/steal/park del orquestador |
| `ada80252` | 28-08 | mypy lint orchestration + config alineada a localhost/codewiki neutro |
| `294bdf29` | 28-08 | fix ruff/fmt |
| (worktree) | 28-08 | default_agent `coder`→`general`; mcp codewiki retirado del proyecto (→global) |

### `.opencode/agents/` (git)
| Commit | Qué añadió |
|---|---|
| `ad631f1e` | agente `calidad-cobertura` + gate CI (cobertura 100×100, 17 tests) |
| `08f996c4` | testing cobertura + ramas muertas eliminadas |
| `2783b898` | repoint de dependencias a modelos nuevos (migración Ollama) |
| `0a2222aa` | agente `orchestrator` + scripts de setup para 3 nodos (gx10/mac) |
| `32236856` | ecosistema orchestrator v2: `parse_plan_to_tasks`, `/orchestrate` |
| `0f4d4894` | distribución P2P + detección PLAN vs ORDEN LOCAL + node registry |
| (worktree) | `build.md`, `revisor-fondo.md` nuevos; `orchestrator.md` modelo→`qwen3-coder:30b-mejorado` |

### `docs/udo/coordination.json` (git)
Evolución: `362dc8f4` (Fase B mypy) → `9cd0c132` (mejoras post-Fase B) → `2783b898`/`b68e30e2` (migración modelos, TERM) → `3233807b` (veredicto APROBADA) → `6e30463f` ... → `d81ac914` (despertador) → `06beaf85` (3 agentes, modo paralelo, Sprint 0) → `7f26fda5` (merge conflict resuelto, 28-08).

### `config/dispositivos.json` (git)
Historico corto: `eb000831` (activación servicios resiliencia) y `aa27da57` (Tailscale race conditions + auto-reparación). Archivo ahora **inmutable** (`chattr +i`) por política de inventario; los cambios manuales requieren `sudo chattr -i`.

### `.gitignore`
`.opencode/*.db-wal`, `.opencode/*.db-shm`, `.opencode/.current-node-id`, `.opencode/init`, `.attic/`, `opencode.json.bak.*` — los agentes `.md` SÍ están versionados; solo se ignoran artefactos runtime.

### Configs globales por nodo (fuera de git)
- GX10 global: `model qwen3-coder:30b-mejorado`, mcp `codewiki` local, agentes canónicos (28-08).
- GX10 web (`opencode-web.json`): override `OPENCODE_CONFIG` del systemd; agentes canónicos (28-08).
- Mac: dos ficheros globales (`~/.config/opencode/opencode.json` y `~/Library/Application Support/opencode/opencode.json`) alineados ambos al canónico (28-08); codewiki-mcp 1.1.2 instalado localmente.
- `ROLES_OPENCODE.md` (docs/udo/, 25-08): ASUS Desktop (GX10)=REVISOR, Mac Desktop=GENERADOR, GX10 Web=GENERADOR — sigue como referencia de roles; no quedó reflejado como config y ya no hay divergencias por instancia.