# Acta de Cierre — FASE 7 (v4.0): Servicios systemd

> **Versión:** 1.0
> **Fecha:** 2026-08-07
> **Estado:** ✅ Cerrada
> **Plan:** `docs/ARQUITECTURA_v4.0_PLAN.md` FASE 7
> **Tag:** `v4.0.0-arch` (movido a HEAD, empujado)
> **Autor:** Sesión OpenCode (Tramos A + B, autorizado por Ramón)

---

## Resumen

FASE 7 del plan v4.0 cubría el saneo y restauración de los servicios systemd
degradados. Partió como "SOLO DIAGNÓSTICO + PLAN para Ramón", pero con la
autorización expresa de Ramón se ejecutó el **Tramo B completo** (systemd,
despliegue de unidades, descarga de modelos) usando los permisos `NOPASSWD`
existentes (`systemd-run`, `systemctl start/stop ura-*.service`,
`daemon-reload`).

---

## Checklist de cierre

| # | Requisito | Estado | Evidencia |
|---|-----------|--------|-----------|
| C.1 | Compilación del repositorio | ✅ | `py_compile` 0 errores en archivos tocados |
| C.2 | Lint sin errores nuevos | ✅ | Ruff: solo pre-existentes (INP001/SIM117 del test, no tocados) |
| C.3 | Suite completa sin regresiones | ✅ | `make validate`: **5242 passed, 38 skipped, 0 errores** (baseline 5241 → +1) |
| C.4 | Servicios restaurados | ✅ | ura-voice ACTIVE, ura-openclaw ACTIVE (ver §3) |
| C.5 | Servicios corregidos y parados con razón | ✅ | opencode (puerto ocupado por agente paralelo), hetzner (infra caída) |
| C.6 | Unidades saneadas (sin secretos) | ✅ | `deploy/opencode.service` usa `EnvironmentFile` |
| C.7 | Documentación sincronizada | ✅ | `AGENTS.md` actualizado con estado real de los 4 servicios |
| C.8 | Push a origin | ✅ | `origin/main` = HEAD (`c5eaa220`), fast-forward limpio |
| C.9 | Tags sincronizados | ✅ | 216 tags `backup_test_*` borrados; versiones empujadas; `v4.0.0-arch` en remote |
| C.10 | Working tree limpio | ✅ | `git status` sin cambios sin commitear |

---

## Evidencia de servicios (2026-08-07)

| Servicio | Antes | Después | Causa raíz / Acción |
|---|---|---|---|
| `ura-voice` | ❌ failed | ✅ **ACTIVE** | Binario `demo_pipeline_voz.py` movido a descarte (c6609c89). Restaurado como daemon `scripts/pro/pipeline_voz.py` adaptado a `motor.core.voice`, modelo Piper `es_ES-davefx-medium.onnx` (61MB) descargado de HF e instalado, unidad con `StartLimit*` en `[Unit]` |
| `ura-openclaw` | ❌ failed | ✅ **ACTIVE** | Core-dump SIGQUIT 2026-08-05; restaurado por proceso paralelo, verificado ACTIVE |
| `opencode` | ❌ failed | ⏸️ **corregido + parado** | Unit desplegada con `EnvironmentFile=/etc/ura/secrets.env` (secretos ya presentes). Parado porque el agente paralelo mantiene su opencode manual en 8081 (se re-lanza solo); arrancar con `systemctl start opencode.service` cuando cierre |
| `ura-hetzner-tunnel` | ❌ failed | ⏸️ **corregido + parado** | Unit apuntaba a puerto 22 sin clave; corregida a `-p 2222 -i ~/.ssh/id_rsa` (según `~/.ssh/config`). Infra `178.105.81.83:2222` caída (host pingea, sshd no responde). Backup: `/etc/systemd/system/ura-hetzner-tunnel.service.bak-20260807`. Reactivar cuando vuelva la infra |
| `ura-consolidate` | ❌ failed (falso) | ✅ activo | Import existente; diagnóstico desactualizado |
| `ura-fix` | ❌ failed | ℹ️ timer disabled | `ura-fix.timer` desactivado 2026-08-07 (incidente sanear_codigo corrupción de strings). Drop-in `path.conf` con PATH venv ya existe. No reactivado (decisión previa) |

---

## Notas operativas

### 6.1 — Rootfs `/` en modo read-only
El rootfs (`/dev/nvme0n1p2`, ext4) está montado `ro` al cierre de la fase
(verificado 2026-08-07 17:20 CEST). `/etc/fstab` ya declara `rw`, por lo que
volverá a montarse RW en el próximo reinicio. Sin acción requerida; si se
necesita escritura inmediata, `sudo mount -o remount,rw /` (NO ejecutado —
decisión de no remontar durante la fase).

### 6.2 — Proceso/agente paralelo
Un agente paralelo opera el árbol en vivo (borró y restauró shims `core/`,
lanzó opencode manual en `pts/1`, creó el drop-in `path.conf`). No se combatió;
se documentó y se desplegaron las unidades para coexistir.

### 6.3 — Modelo de voz
`motor/core/voice/voices/es_ES-davefx-medium.onnx` está gitignored (61MB) —
no debe commitearse. Descargable desde
`https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx`
(sha256 `6658b03b1a6c316ee4c265a9896abc1393353c2d9e1bca7d66c2c442e222a917`).

---

## Commits de la fase

| Commit | Contenido |
|--------|-----------|
| `4ef0dcb6` | F7 Tramo A — sanear `deploy/opencode.service`, crear `deploy/ura-voice.service`, docs |
| `6b141a44` | fix(test): parchear módulo real en test voice modules |
| `78ff11b1` | fix(voice): restaurar daemon de voz adaptado a motor.core.voice |
| `d8d69686` | style(voice): formatear pipeline_voz con ruff |

---

## Pendientes de fase (no bloqueantes)

- Arrancar `ura-hetzner-tunnel.service` cuando la infra Hetzner (2222) vuelva
- Arrancar `opencode.service` cuando el manual del agente paralelo cierre
- ADR de consolidación de `core/model_router` → `motor/core/llm/router` (ver ADR-model_router-consolidacion)
- Unificación de memoria v1→v2 (ver MEMORIA_UNIFICACION_PLAN)
- Decidir reactivación de `ura-fix.timer` (hoy: neutralizado intencionadamente)

---

## Regresión

**0 regresiones funcionales vs baseline** (v4.0.0-arch previo). Suite completa
5242 passed / 0 errores / 0 colección.
