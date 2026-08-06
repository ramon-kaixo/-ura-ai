# Módulos Canónicos — Referencia v4.0

**Fecha:** 2026-08-06
**Fase:** 8 del Plan v4.0
**Estado:** Lista VERIFICADA de componentes canónicos/vivos (2026-08-06)

## Núcleo (`core/`)

| Módulo | Estado | Evidencia |
|---|---|---|
| `core/mochila/` (incl. providers, router, mochila_server) | 🟢 VIVO PROD :4098 | Servicio `ura-mochila.service` ACTIVE |
| `core/memoria/` (9 módulos) | 🟢 VIVO PROD | Importado por mochila_server; 9 tests |
| `core/qdrant_client.py` | 🟢 CANÓNICO (proxy regenerable) | Re-export de motor.core.qdrant_client |
| `core/debate/debate_engine.py` | 🟢 CANÓNICO | Fase 15 migrado HTTP |
| `core/ura_multi_agent.py` | 🟢 CANÓNICO | Fase 15 migrado HTTP |
| `core/agents/*` (incl. cli.py) | 🟢 CANÓNICO | 3 consumidores + systemd |
| `core/agents/conciencia.py` | 🟢 VIVO | También en build/lib y scripts/pro |
| `core/sandbox.py` | 🔴 MUERTO | 0 importadores; su propio test lo declara muerto |
| `core/model_router/` (11 módulos) | 🟡 TRANSICIÓN | 0 consumidores vivos, 6 tests; ver ROUTERS.md |
| `core/memoria/bridge.py` | 🟢 VIVO | Puente memoria |

## Motor (`motor/`)

| Módulo | Estado | Evidencia |
|---|---|---|
| `motor/core/config.py` | 🟢 FUENTE DE VERDAD | UraConfig único |
| `motor/core/secrets.py` | 🟢 CANÓNICO | F17.5 |
| `motor/core/llm/` (incl. router, providers) | 🟢 VIVO | 10+ importadores core |
| `motor/memory/` (7 módulos) | 🟢 CANÓNICO v2 | F26 Historical Memory |
| `motor/intelligence/memory/` (12 módulos) | 🟢 CANÓNICO v2 | F12 Context Memory |
| `motor/agents/` | 🟢 CANÓNICO | F27 (109 tests) |
| `motor/platform/` | 🟢 CANÓNICO | F28 protocols |
| `motor/cli/` | 🟢 CANÓNICO | Fase 9 CLI (`cmd_ura.py` refs rotas a model_router_main — F6.2) |

## Agentes (`agents/`)

| Módulo | Estado | Evidencia |
|---|---|---|
| `agents/` (dominios) | 🟢 VIVO | Organizado por subdirectorios |

## Conocimiento (`knowledge/`)

| Módulo | Estado | Evidencia |
|---|---|---|
| `knowledge/engine/` (F0-7) | 🟢 VIVO | FTS5, edges, lineage |
| `knowledge/engine/notify.py` | 🟢 VIVO | Slack/Email |

## Pipeline (`scripts/pro/`)

| Script | Estado | Evidencia |
|---|---|---|
| `tuneladora/tuneladora_mantenimiento.py` | 🟢 CANÓNICO root (protegido, no-touch) | Timer activo |
| `tuneladora_mejora.py` | 🟢 | Motor engine |
| `pipeline_refactor.py` | 🟢 sano | Invocada por tuneladora_mejora |
| `pipeline_supremo.py` | 🟡 degradado (7 refs purgadas) | Invocado por ingestador_red |
| `manage_timers.py` | 🟢 | fix raíz `*:0/6` commitado |
| `watchdog_buffer.sh` | 🟢 PROD | ura-watchdog-buffer.service |
| `chaos_test.py` | 🟢 | Makefile + manage_timers |
| `plugin_registry.py` | 🟢 | Motor de fases |
| `lock_manager.py`, `gpu_health.py`, `gpu_recovery.sh` | 🟢 | GPU/crontab |
| `ura-query.py` | 🟢 | Consulta vectorial |

## Deploy

| Unit | Estado |
|---|---|
| `deploy/ura-openclaw.service` | 🟡 FAILED (core-dump) |
| `deploy/opencode.service` | ⚠️ secretos hardcodeados — F7 saneo |
| `deploy/timers/ura-mutmut.*` | 🟡 no integrado en manage_timers |
| `deploy/ura.service`, `ura-maintenance-v2.{service,timer}` | 🟢 activos |

Ver `docs/SYSTEMD_V4.0.md` para el detalle por servicio.