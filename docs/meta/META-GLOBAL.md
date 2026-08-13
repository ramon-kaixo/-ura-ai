# META GLOBAL — Inventario maestro del sistema URA (2026-08-13)

Un vistazo a TODO el sistema: modelos, carpetas, servicios, datos y memoria.
Fuente: mediciones reales del 2026-08-13 (comandos verificados).

## Modelos de Ollama (13 modelos — 189 GB en /home/ramon/URA/ollama-models-0326)

| Modelo | Tamaño | Uso típico |
|--------|--------|-----------|
| qwen3-coder:30b | 18,6 GB | Código pesado/TERM (el que satura cuando la tuneladora genera sin parar) |
| qwen2.5-coder:14b | 9,0 GB | **Código estándar — Web y TERM actual** |
| deepseek-r1:14b | 9,0 GB | Razonamiento / orquestador |
| codestral:22b | 12,6 GB | Código (alternativa) |
| llama3.3:70b | 42,5 GB | Modelo grande general (RAM alta) |
| qwen3:32b-q8_0 | 34,8 GB | General 32b |
| qwen2.5-coder:32b | 19,9 GB | Código 32b |
| qwen2.5-coder:q8_0 | 34,8 GB | Código q8 |
| llama3:latest | 4,7 GB | General ligero |
| llama3.2-vision:11b | 7,8 GB | Visión |
| qwen2.5:7b | 4,7 GB | Ligero |
| deepseek-coder:6.7b | 3,8 GB | Código ligero |
| nomic-embed-text | 0,3 GB | Embeddings |

## Carpetas y su función
(índice detallado: ver tabla en el chat 2026-08-13 / AGENTS.md Arquitectura)
`core/` dominio · `motor/` framework · `knowledge/` memoria LTM · `tests/` 1394 · `docs/` 699 · `scripts/` 366 · `deploy/` 112 · `data/` BD runtime · `monitor/` SNC

## Servicios activos (systemd, 2026-08-13) y qué tocan
| Servicio | Toca |
|----------|------|
| ollama.service | Motor de modelos (11434) |
| model-router.service | Enrutador 11435 (script detector, SOLO loopback) |
| qdrant.service | Vectores |
| ura-api/ura-assistant/ura-audit-api/ura-executor/ura-metrics/ura-mochila/ura-contraste/ura-detector/ura-go2rtc/ura-voice/ura-heartbeat/ura-watchdog-buffer/ura-watcher/ura-watch-daemon/ura-ssh-guard/ura-xvfb | API, asistente, auditoría, mochila (4098), contraste, detector YOLO, cámara, voz, health |
| snc.service + swarm-discovery | Consciencia/emergencia |
| opencode.service | Servidor Web (8081) |
| ura-mkdocs | Docs web |
| llama-vision | Visión |

## Timers/cron que ejecutan cosas solas
| Timer/cron | Ejecuta | Frecuencia |
|-----------|---------|-----------|
| ura-revisiones.timer | `detectar_revisiones.sh --notify` (REVIEW sin revisor) | 5 min |
| ura-pipeline.timer | pipeline (tuneladora) | 5 min |
| ura-watchdog.timer / ura-mochila-guard.timer / ura-memory-watchdog.timer | watchdogs GPU/memoria | 5 min |
| ura-auditd-watchdog.timer | auditoría | 5 min |
| cron gpu_health | gpu_health.py + gpu_recovery | 30 min |
| (propuesta pendiente cron) | `enviar_revision_web.sh` — envío directo de revisiones al Web | 15 min, requiere sudo |

## Memoria y conocimiento (BD, registros reales)
| BD | Contenido | Registros |
|----|-----------|-----------|
| knowledge/knowledge.db | concepts=3477, relations=1336 (grafo conceptual) | kg_nodes VACÍO (KE2.0 sin poblar) |
| knowledge/knowledge.db | pending_fixes=5505, tuneladora_runs=5693 | — |
| knowledge/episodic.db | episodic (memoria episódica) | **8.453 episodios** |
| knowledge/ltm.db | ltm_store (memoria a largo plazo) | **7.234 entradas** |
| data/changes.db | changes (cambios) | 1.100 |
| ~/.ura | memoria/telemetría conciencia | 401 MB |
| opencode (BD sesiones) | conversaciones de agentes | 338 sesiones / 146M tokens (build 20 ses = 127,6M) |

## Hallazgo para la conciencia/búsqueda
- El **grafo KG del Knowledge Engine 2.0 está vacío** (kg_nodes=0): la búsqueda indexada por vectores usa otro mecanismo; el grafo conceptual vive en concepts/relations. Revisar si el KE2.0 debe poblar kg_nodes o si concepts/relations es el camino real (pendiente de análisis, no accionado).
## Estado auditoría 2026-08-13 (arreglos aplicados)
| # | Problema | Estado |
|---|----------|--------|
| 2 | ura-revisiones: falso positivo (corre cada 5 min OK) + bug git del detector | CORREGIDO (cd REPO, verificado) |
| 3 | Saturación ollama (runner 30b runaway) | DESBLOQUEADO (runner parado, 14b responde); prevención 11437 pendiente sudo |
| 1 | audit-extra 16 huerfanos | CORREGIDO (checker ampliado a deploy/.github → 13, verificado) |
| 1 | mutmut-daily colección rota | CORREGIDO (test ignorado) |
| 9 | 5,3 GB conversaciones | PODADO 5,27GB → 673MB (backup /tmp/opencode) |
| 4 | kg_nodes vacío | DIAGNOSTICADO, sin tocar (motor, ADR-007) |
| 6 | router loopback | NO TOCADO (zona detector) |
| 7 | rootfs RO / cron | Requiere sudo humano (comando preparado) |
| 8 | fases sin cerrar | Pendiente decisión |
