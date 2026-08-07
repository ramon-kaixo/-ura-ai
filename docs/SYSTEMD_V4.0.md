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

## 7. Estado verificado (F7)

**Fecha:** 2026-08-06
**Método:** `systemctl status --user <svc>` (fallback) → no encontrados en user units;
re-verificado en unidades de sistema con `systemctl status <svc> --no-pager` (solo lectura, sin sudo).

| Servicio | Estado verificado | Output exacto (resumen) |
|---|---|---|
| `ura-voice.service` | ❌ **FAILED** — sigue caído | `Active: failed (Result: exit-code) since Tue 2026-08-04 12:44:19 CEST; 2 days ago`, `Main PID: 2767833 (code=exited, status=2)`, Loaded: enabled, Drop-In: hardening.conf + restart-fix.conf. Warning systemd: `Unknown key name 'StartLimitIntervalSec' in section 'Service', ignoring.` (línea 8 del unit) |
| `ura-cleanup-auto.service` | ✅ **OK** — no failed | `Active: inactive (dead) since Wed 2026-08-05 15:00:00 CEST; 1 day 8h ago`, TriggeredBy: `ura-cleanup-auto.timer`, último run `status=0/SUCCESS` ("Limpieza completada: 0 mensajes antiguos eliminados") |
| `ura-mcp.service` | ⚠️ **NO existe** en systemd | `Unit ura-mcp.service could not be found.` — coincide con diagnóstico §2 (ejecutaba `mcp_mochila.py` archivado; unit del repo retirado en F6.2) |
| `ura-mutmut.timer` | ⚠️ **NO existe** en systemd | `Unit ura-mutmut.timer could not be found.` — unit del repo (`deploy/timers/ura-mutmut.*`) nunca instalado |
| `ura-mutmut.service` | ⚠️ **NO existe** en systemd | `Unit ura-mutmut.service could not be found.` — idem |

**Conclusiones F7-Preparación (2026-08-06):**
1. De los 5 objetivo, solo 1 está realmente failed: `ura-voice.service` (exit 2, 2 días caído, warning `StartLimitIntervalSec` en unit).
2. `ura-cleanup-auto.service` está sano (timer-disparado, último run SUCCESS).
3. `ura-mcp.service`, `ura-mutmut.timer`, `ura-mutmut.service` NO están instalados en systemd — el archivo `ura-mutmut.*` del repo se retira o integra (decisión §5).
4. Los 3 no-encontrados no requieren acción sudo; el diagnóstico §1 sigue válido para `ura-consolidate`, `ura-fix`, `ura-hetzner-tunnel`, `ura-openclaw`, `ura-voice` (estos sí requieren sudo para arrancar/editar).

## 8. Re-verificación del Tramo A (2026-08-07) — ejecutado por el agente

**Método:** `systemctl --failed`, `journalctl -u <svc> -n 6` (solo lectura), sin sudo.

| Servicio | Estado (2026-08-07) | Causa/info |
|---|---|---|
| `ura-consolidate` | ✅ **SUCCESS** | último run OK; `scripts/pro/reuse/quality_gates.py` existe — diagnóstico §1 desactualizado (causa de import era transitoria) |
| `opencode` | ❌ **FAILED** (restart loop, exit 1) | `EnvironmentFile=/etc/ura/secrets.env` NO tiene las vars `OPENCODE_GATEWAY_*` ni `OPENCODE_SERVER_*` → ServeError. Unit sanitizado en repo (`deploy/opencode.service`) |
| `ura-fix` | ❌ **FAILED** | `FileNotFoundError: 'ruff'` — PATH del unit sin venv. Confirmado §1 (4:00 UTC run) |
| `ura-hezner-tunnel` | ❌ **FAILED** (exit 255) | "No entries" en journal (rotto desde 2026-08-01) |
| `ura-openclaw` | ❌ **FAILED** (core-dump) | SIGQUIT, 4.2s CPU, 167M peak en última ejecución (2026-08-05 15:04) |
| `ura-voice` | ❌ **FAILED** (exit 2) | Warning `StartLimitIntervalSec` en línea 8 [Service] — debe moverse a [Unit] (FIX en `deploy/ura-voice.service`) |
| `ura-mcp.service` | ⚠️ no existe | idem §7 |
| `ura-mutmut.*` | ⚠️ no existen | idem §7 |

**Cambios del tramo A (committed al repo):**
1. `deploy/opencode.service` → sanitizado: sin token/password hardcoded, `EnvironmentFile=/etc/ura/secrets.env` (igual al unit instalado en `/etc/systemd/system/`), con comment de vars requeridas. Cierra la deuda son secretos §4 del repo.
2. `deploy/ura-voice.service` → **NUEVO** (unit corregido: `StartLimitIntervalSec/Burst` movidas a `[Unit]` como exige systemd).
3. `AGENTS.md` → sección Servicios reales actualizada (estado real de `opencode`, `ura-voice`, `ura-consolidate`).

## 9. Plan Tramo B (Ramón, sudo) — comandos listos

```bash
# 0. Diagnóstico certero
systemctl --failed --no-pager

# 1. opencode — añadir vars de gateway y rotar secretos
sudo nano /etc/ura/secrets.env       # o usar el helper de rotate_secrets.sh
#   Añadir: OPENCODE_GATEWAY_URL, OPENCODE_GATEWAY_TOKEN (NUEVO), OPENCODE_SERVER_USERNAME, OPENCODE_SERVER_PASSWORD (NUEVO)
# La rotación debe hacerse primero en la consola de OpenClaw, luego actualizar secrets.env.
sudo systemctl daemon-reload && sudo systemctl restart opencode.service

# 2. ura-voice — deploy unit corregido y debug de audio
sudo cp deploy/ura-voice.service /etc/systemd/system/ura-voice.service
sudo systemctl daemon-reload
sudo journalctl -u ura-voice -n 30 --no-pager     # causa exit 2 (Whisper/Piper)
sudo systemctl restart ura-voice

# 3. ura-fix — PATH sin ruff
sudo systemctl edit ura-fix.service
#   [Service]
#   Environment="PATH=/home/ramon/.local/bin:/usr/local/bin:/usr/bin:/bin"
cd ~/URA/ura_ia_1972 && sudo systemctl restart ura-fix 2>/dev/null

# 4. ura-openclaw — reiniciar (si reaparece core-dump, revisar memoria/hardening)
sudo systemctl restart ura-openclaw; systemctl status ura-openclaw --no-pager

# 5. ura-hetzner-tunnel — si ya no se usa:
sudo systemctl disable --now ura-hetzner-tunnel.service
```

**Impacto estimado (Tramo B):**
- reinicios de `opencode`, `ura-openclaw`, `ura-voice`, `ura-fix` — corto (~s), servicios supervisados por systemd Restart.
- Cambio de token gateway/password sin coordinación con consolas OpenClaw dejaría opencode/service con auth falsa → ROLLBACK guardado: guardar token anterior en secrets.env `_OLD`.
- Disable hetzner-tunnel es reversible con `systemctl enable --now`.

## Nota de seguridad (2026-08-07)
El repo repositorio `deploy/opencode.service` contenía `OPENCODE_GATEWAY_TOKEN` y `OPENCODE_SERVER_PASSWORD` en claro. **La token/password deben rotarse igualmente** aunque el unit del sistema ya no las necesite en el repo (el secret seguía circulando en git history). El `EnvironmentFile` debe contener las vars nuevas.
---
## §10 Estado post-fix (2026-08-07, re-verificado 12:15 CEST)

| Servicio | Estado verificado | Fix aplicado / pendiente |
|----------|--------|-------------|
| ura-openclaw | ⚠️ **activating** (no active) | reiniciado tras core-dump; pendiente confirmar que quede stable |
| ura-voice | ❌ **failed** | unit corregido en repo (`deploy/ura-voice.service`); pendiente deploy + debug audio |
| ura-fix | ✅ inactive (success) | Drop-in PATH al venv aplicado; timer desactivado (incidente sanear_codigo, ver §11) |
| opencode | ❌ failed | Pendiente: valores reales de OPENCODE_* en /etc/ura/secrets.env |
| ura-hetzner-tunnel | ❌ disabled | Infra externa caída, desactivado hasta nuevo aviso |
| snap-brave | ❌ failed | No es URA |

## §11 Incidente corrupción masiva — sanear_codigo.py (2026-08-07)

**Síntoma:** `make validate` con 51 errores de colección; 18 archivos con SyntaxError (strings rotas: `;` reemplazado por `\n`).

**Causa raíz:** `scripts/pro/sanear_codigo.py::fix_multiline_statements` reemplazaba `;` por newline mecánicamente, rompiendo strings Python (docstrings, CSS, URLs, test data).

**Neutralización (Ramón):**
- `ura-fix.timer` desactivado (`systemctl disable ura-fix.timer`)
- `sanear_codigo.py` corregido: ahora tokeniza para no tocar `;` dentro de strings (commit `e83dbd4f`)

**Reparación del working tree (agente):** 18 archivos corruptos restaurados desde HEAD (`git checkout --`); suite verde 5241 passed / 0 failed.

**Regla permanente:** no ejecutar scripts de sanear/reformateo/systemd sin preguntar. Reportar, no actuar.

