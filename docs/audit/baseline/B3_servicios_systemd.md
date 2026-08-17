# B3 — Inventario formal de servicios systemd URA (GX10)

- **Fecha**: 2026-08-17
- **Modo**: auditoría READ-ONLY (sin stop/disable/borrados)
- **TASK**: TASK-20260817-017 (B3)
- **Método**: `systemctl list-units --all --type=service` filtrado por `ura|ollama|qdrant|model-router|llama-vision|snc|swarm|go2rtc|ssh-guard|ufw|watch|metrics|heartbeat` + `is-active`/`is-enabled`/`show {Description,Restart,TimeoutStopUSec}` por servicio.
- **Nota**: todas las acciones son **PROPUESTAS** — ninguna autorizada. Decisión humana por ítem (regla B2/B3).

## Resumen ejecutivo

| Clasificación | Cantidad |
|---|---|
| ACTIVO y necesario | 24 |
| ACTIVO y dudoso | 2 |
| INACTIVO y legacy | 14 |
| FAILED | 7 (+1 resuelto: ura-revisiones) |

> Total: 47 servicios clasificados + ura-revisiones (resuelto) = 48 unidades únicas detectadas.

### Nota: `ure-al.service` (UNKNOWN / NO VERIFICADO)

En una auditoría previa apareció un nombre "ure-al", pero **no se encuentra en systemd ni en el repo**: no existe en `systemctl list-unit-files`, ni en `/etc/systemd/system/`, ni como referencia en `docs/`, `scripts/` o el árbol git. Se registra como **UNKNOWN / NO VERIFICADO** — no se incluye como fallo ni como servicio existente hasta que Ramón aclare el origen del nombre.

## Tabla de inventario

### ACTIVO y necesario (24)

| Servicio | Estado | Enabled | Ejecutado | Función | Acción propuesta | Prioridad |
|---|---|---|---|---|---|---|
| ollama | active | enabled | siempre | Runtime LLM local | Mantener | — |
| qdrant | active | enabled | siempre | Vector DB URA | Mantener | — |
| model-router | active | enabled | siempre | Enrutado de modelos (inteligente) | Mantener | — |
| snc | active | enabled | siempre | Sistema Nervioso Central | Mantener | — |
| swarm-discovery | active | enabled | siempre | Auto-descubrimiento swarm | Mantener | — |
| ura-api | active | enabled | siempre | API GX10 + audit gate post-crash | Mantener | — |
| ura-assistant | active | enabled | siempre | Asistente conversacional FastAPI | Mantener | — |
| ura-audit-api | active | enabled | siempre | Audit API (FastAPI) | Mantener | — |
| ura-contraste | active | enabled | siempre | Proxy de contraste (Uvicorn) | Mantener | — |
| ura-detector | active | enabled | siempre | YOLOv8 Detector + ByteTrack | Mantener | — |
| ura-mochila | active | enabled | siempre | Router Mochila (FastAPI) | Mantener | — |
| ura-metrics | active | enabled | siempre | Metrics Server (8888) | Mantener | — |
| ura-heartbeat | active | enabled | siempre | Reinicio auto si /health falla | Mantener | — |
| ura-ssh-guard | active | enabled | siempre | Protección SSH | Mantener | — |
| ura-ufw-rules | active | enabled | una vez boot | Reglas UFW Tailscale | Mantener | — |
| ura-voice | active | enabled | siempre | Voice Pipeline (Whisper+Piper) | Mantener | — |
| ura-watcher | active | enabled | siempre | Indexación sectorizada en tiempo real | Mantener | — |
| ura-watch-daemon | active | enabled | siempre | Pipeline al detectar cambios | Mantener | — |
| ura-watchdog-buffer | active | enabled | siempre | Watchdog buffer 30GB | Mantener | — |
| ura-mkdocs | active | enabled | siempre | Base de conocimiento (docs) | Mantener | — |
| ura-go2rtc | active | enabled | siempre | Proxy streams cámaras Dahua | Mantener (dudoso si cámaras en desuso) | Baja |
| ura-xvfb | active | enabled | siempre | Display virtual (para RPA/vision) | Mantener (verificar dependencia) | Baja |
| ufw | active | enabled | siempre | Firewall del sistema | Mantener | — |
| systemd-networkd | active | disabled | siempre | Red del sistema | Mantener | — |

### ACTIVO y dudoso (2)

| Servicio | Estado | Enabled | Ejecutado | Función | Acción propuesta | Prioridad |
|---|---|---|---|---|---|---|
| llama-vision | active | disabled | siempre | Modelo de visión (arrancado manualmente) | Decidir: enable (si se usa) o stop+disable | Baja |
| ura-executor | active | disabled | siempre | Executor API — arrancado sin enable | Decidir: enable permanente o retirar | Media |

### INACTIVO y legacy (14)

| Servicio | Estado | Enabled | Ejecutado | Función | Acción propuesta | Prioridad |
|---|---|---|---|---|---|---|
| netplan-ovs-cleanup | inactive | enabled-runtime | no | OpenVSwitch cleanup | Retirar (OVS no se usa) | Baja |
| nvidia-raid-config | inactive | enabled | no | RAID NVIDIA (hardware ausente) | Disable | Baja |
| nvidia-redfish-config | inactive | enabled | no | Redfish NVIDIA (hardware ausente) | Disable | Baja |
| ura-maintenance | inactive | enabled | no | Limpieza automatizada (superseded) | Disable + legacy (reemplazado por v2) | Media |
| ura-network | inactive | enabled | no | Network scanner (en desuso) | Disable | Media |
| ura-auditd-watchdog | inactive | static | no | Watchdog auditd | Solo si hay auditd | Baja |
| ura-auto-reindex | inactive | static | no | Reindex auto cada 6h | Desusado (timer?) | Baja |
| ura-chaos | inactive | static | no | Chaos engineering | No usar en prod | Baja |
| ura-cleanup | inactive | static | no | Limpieza stale files | Legacy (probablemente en tuneladora) | Baja |
| ura-cleanup-auto | inactive | static | no | Limpieza asistente | Legacy | Baja |
| ura-memory-watchdog | inactive | static | no | Watchdog presión memoria | Verificar si se usa | Baja |
| ura-mochila-guard | inactive | static | no | Restaura archivos borrados | Desusado (mochila propia?) | Baja |
| ura-pipeline | inactive | static | no | Motor de conocimiento pipeline | Legacy (tuneladora) | Baja |
| ura-watchdog | inactive | static | no | Watchdog genérico | Legacy | Baja |

### FAILED (7)

| Servicio | Estado | Enabled | Ejecutado | Función | Causa probable | Acción propuesta | Prioridad |
|---|---|---|---|---|---|---|---|
| ura-audit-extra | failed | static | 04:00 | Auditoría paralela | exit-code (04:00) | Auditar + reparar o retirar | Media |
| ura-backup | failed | static | 04:00 | Backup del repo | exit-code (04:00) | Auditar + reparar (backup es crítico) | **Alta** |
| ura-consolidate | failed | static | 04:00 | Consolidación de código | exit-code | Auditar + reparar o retirar | Media |
| ura-harden | failed | static | 04:00 | Auditoría hardening | exit-code | Auditar + reparar o retirar | Media |
| ura-maintenance-v2 | failed | static | 06:00 | Tuneladora unificada (mantenimiento) | exit-code (06:00) | **Reparar** (v2 es el pipeline activo) | **Alta** |
| ura-mutmut-daily | failed | static | 04:00 | Mutation testing diario | exit-code | Auditar + reparar o retirar | Baja |
| ura-reindex | failed | static | 05:00 | Reindexado vectorial | exit-code (05:00) | Auditar + reparar (KE depende) | Media |

> **Nota**: ura-revisiones pasó de FAILED → inactive (fixed en TASK-008/012, arranque 10:50:49 SUCCESS).

### Causa común probable

Los 7 failed son servicios oneshot `static` con fallo `exit-code` en horas programadas (04:00-06:00). Sospecha: ExecStart a scripts con problemas de entorno (rootfs RO, PATH, flags de tuneladora). Verificación completa → TASK-018 propuesta (diagnóstico B3.5) — **no ejecutada**.

## Decisiones pendientes (para Ramón, por ítem)

1. **ura-backup y ura-maintenance-v2 (FAILED)** → reparar: alta prioridad (backup diario y tuneladora de mantenimiento).
2. **5 failed restantes** → auditar o retirar definitivamente (mask).
3. **14 inactivos legacy** → disable/mask por ítem (nvidia-*, netplan-ovs, ura-maintenance, ura-network...).
4. **llama-vision / ura-executor (active+disabled)** → decidir enable o retirar.
5. **ura-go2rtc / ura-xvfb** → verificar dependencia real antes de tocar.

## Referencias
- Inventario A1 (docs/audit/baseline/README.md) — pre-refactor systemd
- Estado previo A2 — 45 unidades detectadas, 1 FAILED (ura-revisiones, resuelto)
- Evidence: `/tmp/opencode/b3_data.txt`, `/tmp/opencode/b3_rt.txt` (salidas crudas systemctl)
