# Servicios systemd — Referencia LIVE v4.0

**Fecha:** 2026-08-06 (verificado en vivo)
**Fase:** 8 del Plan v4.0
**Fuente:** `docs/SYSTEMD_V4.0.md` (diagnóstico + plan de comandos para Ramón)

## Servicios ACTIVOS (verificado 2026-08-06)

| Servicio | Estado | Nota |
|---|---|---|
| `qdrant.service` | ✅ active | Base vectorial |
| `llama-vision.service` | ✅ active | Visión |
| `snc.service` | ✅ active | Sistema Nervioso Central |
| `swarm-discovery.service` | ✅ active | Caracter `ura-watchdog`? |
| `ura-api.service` | ✅ active | API GX10 |
| `ura-assistant.service` | ✅ active | Asistente FastAPI |
| `ura-audit-api.service` | ✅ active | Audit API |
| `ura-contraste.service` | ✅ active | Proxy :8002 |
| `ura-detector.service` | ✅ active | YOLOv8 |
| `ura-go2rtc.service` | ✅ active | Cámaras |
| `ura-heartbeat.service` | ✅ active | Reinicia mochila |
| `ura-metrics.service` | ✅ active | :8888 |
| `ura-mkdocs.service` | ✅ active | Docs |
| `ura-mochila.service` | ✅ active | **PROD :4098** |
| `ura-ssh-guard.service` | ✅ active | |
| `ura-ufw-rules.service` | ✅ active |
| `ura-watchdog/timer` | ✅ | ura-watchdog.timer 5min |
| `ura-mochila-guard.timer` | ✅ | 5min |
| `ura-memory-watchdog.timer` | ✅ | 5min |
| `ura-pipeline.timer` | ✅ | `/usr/local/bin/ura-motor pipeline` |
| `ura-auditd-watchdog.timer` | ✅ | |
| `ura-maintenance-v2.timer` | ✅ | 6h |
| `ura-backup.timer` | ✅ | diario 04:00 |
| `ura-fix.timer` | ✅ (service failed) | |
| `ura-cleanup.timer` | ✅ |
| `ura-audit-extra.timer` | ✅ |
| `ura-consolidate.timer` | ❌ service failed |
| `ura-harden.timer` | ✅ |

## Servicios FAILED (5)

| Servicio | Causa | Ver |
|---|---|---|
| `ura-consolidate.service` | `scripts.pro.reuse.quality_gates` módulo no existe | F6.2 |
| `ura-fix.service` | `ruff` no encontrado (PATH) | SYSTEMD_V4.0 #2 |
| `ura-hetzner-tunnel.service` | SSH exit 255 (4 días) | SYSTEMD_V4.0 #3 |
| `ura-openclaw.service` | core-dump SIGQUIT | SYSTEMD_V4.0 #4 |
| `ura-voice.service` | exit 2 (audio) | SYSTEMD_V4.0 #6 |

## Servicios documentados en AGENTS.md pero DESACTUALIZADOS

| Servicio | AGENTS.md dice | Real |
|---|---|---|
| `model-router` (user) | activo :11435 | **INACTIVE** |
| `backend@qwen2.5-coder-32b`, `backend@qwen2.5-coder-q8_0` | activos user | **no listados** |
| `ollama` | activo 11434 | ✅ (sistema base, no verificado en este catálogo) |

*Nota: AGENTS.md se actualizará en el closeout (F8/cierre).*