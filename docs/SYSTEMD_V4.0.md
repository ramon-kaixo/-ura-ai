# SYSTEMD — Estado Real y Plan de Acción (Fase 7 v4.0)

**Fecha:** 2026-08-06
**Fase:** 7 del Plan v4.0 (`docs/ARQUITECTURA_v4.0_PLAN.md`)
**Código:** este documento es DIAGNÓSTICO — ningún comando systemd fue ejecutado
**Ejecutor de comandos:** Ramón (acceso sudo/rootfs RO)

## 1. Servicios FAILED reales (2026-08-06, verificado en vivo)

| Servicio | Estado | Causa raíz verificada | Decisión sugerida |
|---|---|---|---|
| `ura-consolidate.service` | ❌ failed (exit 1) | `ModuleNotFoundError: No module named 'scripts.pro.reuse.quality_gates'` — import roto a submódulo purgado | **F6.2**: arreglar import en `scripts/pro/consolidacion.py` o eliminar el timer si consolidación está descontinuada |
| `ura-fix.service` | ❌ failed | `FileNotFoundError: 'ruff'` — PATH de servicio no incluye el ruff (venv/bin no visible en unit) | Fix: añadir `Environment=PATH=...` con el venv o usar `python -m ruff`. Comando de sistema |
| `ura-hetzner-tunnel.service` | ❌ failed (exit 255) | SSH tunnel roto desde 2026-08-01 (4 días) | Revisar clave SSH/tailscale del nodo Hetzner; si ya no se usa, deshabilitar |
| `ura-openclaw.service` | ❌ failed (core-dump, SIGQUIT) | Core dump del proceso OpenClaw 2026-08-05 | Reiniciar (`systemctl restart`) tras diagnóstico; si sigue dump, revisar memoria/hardening |
| `ura-voice.service` | ❌ failed (exit 2) | Pipeline voicing 2026-08-04 — error de arranque (Whisper/Piper) | Debug de dependencias de audio |

## 2. Servicios con dependencias de código archivado (verificados)

| Servicio | Problema |
|---|---|
| `ura-mcp.service` (`deploy/ura-mcp.service`) | Ejecuta `mcp_mochila.py` archivado — NO está instalado; servicio parece no estar en systemd (no listado) |
| `model-router.service` (sistema + user) | **INACTIVE** (AGENTS.md dice activo :11435 — DESACTUALIZADO). El despliegue real v2 está en `/home/ramon/URA/core/model_router.py` (fuera del repo) — ver `docs/ROUTERS.md` |
| `ura-maintenance-v2.timer` | ✅ ACTIVO (6h — corrige AGENTS.md) → `ura-maintenance-v2.service` ejecuta la tuneladora |

## 3. Timer reales activos (16) — completar AGENTS.md

AÑADIR los no documentados antes:
- `ura-pipeline.timer` → `ura-pipeline.service` (`/usr/local/bin/ura-motor pipeline`)
- `ura-auditd-watchdog.timer` → ura-auditd-watchdog.service
- `ura-memory-watchdog.timer` → ura-memory-watchdog.service
- `ura-mochila-guard.timer` → ura-mochila-guard.service
- `ura-watchdog.timer` → ura-watchdog.service
- `ura-backup.timer`, `ura-audit-extra.timer`, `ura-harden.timer`, `ura-cleanup.timer`,
  `ura-consolidate.timer`, `ura-fix.timer`

**Ya documentados** (verificados): `ura-maintenance-v2.timer` (6h), etc.

## 4. SECRETOS hardcodeados — `deploy/opencode.service`

```ini
[Service]
Environment="OPENCODE_GATEWAY_URL=ws://10.164.1.99:18789"
Environment="OPENCODE_GATEWAY_TOKEN=gw_live_7f8d...b106"     # SECRETO
Environment="OPENCODE_SERVER_USERNAME=ramon"
Environment="OPENCODE_SERVER_PASSWORD=c_pass_d3...a01"        # SECRETO
```

**Riesgo:** token gateway + contraseña servidor en texto plano en el repo (filtran a cualquier
clon/PR). **Acción sugerida (Ramón):**
1. Rotar token/password.
2. Mover a `EnvironmentFile=/etc/ura/opencode-secrets.env` (06:40 root, ramon lee, git ignorado).
3. Manotar: `scripts/pro/check_secrets.py` puede validarlo si se añade patrón.

## 5. Timers del plan que NO existen / pendientes

| Timer | Estado |
|---|---|
| `tuneladora-mantenimiento.timer` | NO existe (plan viejo) — el real es `ura-maintenance-v2.timer` |
| `ura-auto-reindex.timer` | NO existe (ya purgado en fases previas) |
| `deploy/timers/ura-mutmut.{service,timer}` | EXISTEN en repo pero NO integrados en `manage_timers.py` (no listados) ni instalados → decisión: integrar en manage_timers o retirar |
| `ura-consolidate.timer` + `ura-fix.timer` | Enabled pero sus servicios FAILED → falso servicio |

## 6. Plan de comandos para Ramón (en orden)

```bash
# 1. Auth ziración certeza (solo diagnóstico)
systemctl --failed --no-pager

# 2. ura-fix — ruff no encontrado (arreglar PATH)
sudo systemctl edit ura-fix.service
#   [Service]
#   Environment="PATH=/home/ramon/.local/bin:/usr/local/bin:/usr/bin:/bin"

# 3. ura-consolidate — módulo roto (requiere F6.2 primero; o deshabilitar)
sudo systemctl disable --now ura-consolidate.timer   # si se descontinúa

# 4. ura-hetzner-tunnel — comprobar si sigue en uso; si no:
sudo systemctl disable --now ura-hetzner-tunnel.service

# 5. ura-openclaw — reiniciar
sudo systemctl restart ura-openclaw.service; systemctl status ura-openclaw --no-pager

# 6. ura-voice — debug audio
sudo journalctl -u ura-voice -n 30 --no-pager

# 7. Secretos opencode.service
sudo systemctl edit opencode.service   # mover a EnvironmentFile /etc/ura/opencode-secrets.env
# rotar token y password en console de OpenClaw

# 8. ura-mutmut — integrar o retirar
#    si se integra: añadir a scripts/pro/manage_timers.py FREQUENCIAS
#    si se retira: git rm deploy/timers/ura-mutmut.*

# 9. AGENTS.md — actualizar estado de servicios/timers listados (mi trabajo de docs F8)
```

## 6. Conclusión F7

- ✅ Diagnóstico documentado (5 failed con causas, secretos, timers no documentados).
- 🎯 CERO comandos ejecutados por el agente (regla Ramón: agente solo diagnostica).
- Ramón ejecuta el bloque de comandots de la sección 5.