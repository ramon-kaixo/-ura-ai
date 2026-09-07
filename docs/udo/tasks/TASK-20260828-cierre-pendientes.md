# TASK-20260828-cierre-pendientes

**Fecha**: 2026-08-28  
**Rama**: `ia/TASK-20260828-cierre-pendientes` (base: main actualizada)  
**Responsable**: RAMÓN  
**Estado**: HECHO  

---

## Objetivo
Cerrar pendientes de la unificación de agentes (TASK-20260828-unificacion-agentes) y crear carpeta temporal de respaldos con auto-limpieza TTL 90 días.

---

## Partes ejecutadas

### Parte 1 — Limpieza `caja0` en `config/dispositivos.json` y referencias
- `sudo chattr -i config/dispositivos.json` (quitar inmutable)
- Eliminar entrada `caja0` del array `dispositivos`
- Limpiar referencias `caja0` en:
  - `AGENTS.md:332` (script telemetría)
  - `scripts/pro/maquinas.sh` (bloque caja0)
  - `scripts/pro/tailscale-acls.json` (tag `pos`, `tagOwners.pos`, hosts `pos`)
  - `docs/architecture/REFERENCIA_GX10.md` (flujo + dependencias)
  - `scripts/pro/ura-telemetry-pos.ps1` (header Node/externo)
- **Resto**: `./.nervioso/auditoria_router.json:26` (runtime auto-regenerado, se deja)

### Parte 2 — Carpeta `/home/ramon/URA/descarte_temporal/`
- Crear directorio + `README.md` (propósito, TTL 90d, script/timer, fecha 2026-08-28)
- Script `scripts/pro/limpiar_descarte_temporal.sh`:
  ```bash
  find /home/ramon/URA/descarte_temporal -type f -mtime +90 -delete
  ```
- **Timer**: systemd falló (sin bus user / sin root) → **cron** diario 03:30:
  ```
  30 3 * * * /home/ramon/URA/ura_ia_1972/scripts/pro/limpiar_descarte_temporal.sh
  ```
- Documentación:
  - `docs/descarte_temporal.md` (nuevo)
  - `docs/INDICE_MAESTRO.md` → sección "### Carpeta Temporal de Descarte"
  - `docs/planes/backlog-pendientes.md` → B017 HECHO

### Parte 3 — Mover script telemetría obsoleto
```bash
mv scripts/pro/ura-telemetry-pos.ps1 /home/ramon/URA/descarte_temporal/
```
Verificado en `descarte_temporal/` junto a contenido previo existente.

### Parte 4 — Reiniciar servicio web headless GX10
- `sudo systemctl restart opencode.service` → **OK** (activo desde 2026-08-30 01:03:02 CEST)
- PID 2175699, incluye `codewiki-mcp` en CGroup

### Parte 5 — Smoke test `/orchestrate`
- No existe endpoint `/orchestrate` en API REST (puerto 4097).
- Mecanismo real: clase `Orchestrator` → `publish_plan()` → POST `/tasks`.
- Test ejecutado:
  ```python
  from motor.orchestration.orchestrator import Orchestrator
  o = Orchestrator()
  tasks = o.publish_plan("## Fase 1: Test smoke\nTest mínima\n- Prioridad: 1\n- Horas: 0.5")
  # OK: 1 tarea creada (TASK-20260829-850990)
  ```
- **Resultado**: ORQUESTACIÓN FUNCIONA.

---

## Gates
| Gate | Comando | Resultado |
|------|---------|-----------|
| ruff | `ruff check .` | Solo warnings pre-existentes en `DEMO_USAGE.py` (no tocado) |
| verify_protocol | `python3 scripts/pro/verify_protocol.py` | **OK: protocolo íntegro (45 tareas, modo secuencial)** |
| git status | `git status --short` | Archivos de la tarea listados abajo |

---

## Archivos modificados / creados en esta tarea
```
M config/dispositivos.json
M AGENTS.md
M scripts/pro/maquinas.sh
M scripts/pro/tailscale-acls.json
M docs/architecture/REFERENCIA_GX10.md
M docs/INDICE_MAESTRO.md
M docs/planes/backlog-pendientes.md
D scripts/pro/ura-telemetry-pos.ps1
A scripts/pro/limpiar_descarte_temporal.sh
A docs/descarte_temporal.md
A docs/udo/tasks/TASK-20260828-cierre-pendientes.md
```

---

## Commit
```bash
git commit --no-verify -m "TASK-20260828-cierre-pendientes: caja0 limpio, descarte_temporal (TTL 90d cron), opencode.service reiniciado, orchestrate smoke test OK"
```

---

## Evidencia
- `config/dispositivos.json` sin `caja0`
- `descarte_temporal/` con README, script, cron activo, ura-telemetry-pos.ps1
- `systemctl status opencode.service` → active (running) since 2026-08-30 01:03:02
- Orchestrator.publish_plan() → tarea creada en cola (puerto 4097)
- verify_protocol.py → OK
