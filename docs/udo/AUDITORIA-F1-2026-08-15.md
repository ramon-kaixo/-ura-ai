# Auditoría F1 — Residual OpenClaw (2026-08-15)

**Agente:** [TERM] (ASUS) · **Fecha:** 2026-08-15 · **TASK:** TASK-20260815-007
**Contexto:** cierre de la auditoría F1 iniciada antes del retiro de OpenClaw
(`c6d60c8c`, impacto cero, 2026-08-08) — verificar que no quedan referencias
vivas al código retirado y resolver la degradación silenciosa detectada.

## 1. Método

1. `grep -rn -i 'openclaw' docs/udo/tasks/` — todas las menciones en expedientes.
2. `grep -rn -i 'openclaw' --include=*.py|*.sh|*.service|*.yml|*.yaml .` — código vivo
   (excluidos `.git/`, `mutants/`, `build/`, `backups/`, `.attic/`).
3. Verificación de cada referencia contra excepciones documentadas
   (TASK-20260808-002 §5) y contra el estado real del sistema
   (`systemctl`, `/etc/systemd/system/`, `data/`, `monitor/`).
4. `make validate` pré-auditoría: 5251 passed, 38 skipped, 135 deselected, 0 failures.
5. Git tree: `9c5630d4` limpio al inicio de la auditoría.

## 2. Hallazgos

| Referencia | Estado | Decisión |
|------------|--------|----------|
| `monitor/openclaw.py`, `tests/integration/test_openclaw.py`, `data/openclaw_stats.json` | ✅ Excepción documentada (brazo SNC emergencia) | Mantener |
| `core/model_router/cli.py:15` (`bypass_config.json`, auth arranque) | ✅ Excepción documentada | Mantener |
| `scripts/pro/openclaw-orquestador.sh` + `docs/udo/OPENCLAW-ORQUESTADOR.md` | ✅ Rol Orquestador nuevo (TASK-009, IN_PROGRESS) | Mantener (intencional) |
| **`scripts/pro/tuneladora/snapshot.py:27`** — import de `openclaw_firmador` (retirado) | 🔴 **Degradación silenciosa**: `except` → `None`, delta snapshots fallaban en cada ciclo del pipeline | **CORREGIDO en esta auditoría** (port local, ver §3) |
| `scripts/pro/mutmut_daily.py:73` — ignore de `test_guardian_openclaw.py` (renombrado a `test_guardian_acciones` en c6d60c8c) | 🟡 Obsoleto | **PENDIENTE** — bloqueado por reserva de TASK-20260815-003 (WEB, IN_PROGRESS); limpiar al cerrar esa tarea |
| `scripts/pro/ejecutor_api.py:172` — path `/api/openclaw/ejecutar` | ℹ️ Nombre heredado; ejecuta `opencode run-context` (no OpenClaw) | Sin acción (contrato API vivo) |
| `scripts/pro/cerrar_pendientes_sistema.sh` — token `OPENCLAW_GATEWAY_TOKEN` + wrapper retirado | ℹ️ Coherente con el retiro (`model_router/cli.py` lo consume, excepción) | Sin acción |
| `build/lib/*` (gitignored), `backups/systemd/`, `.attic/` | ℹ️ Artefactos/histórico | Fuera de alcance |
| `/etc/systemd/system/ura-go2rtc.service` — `ReadWritePaths=/home/ramon/.openclaw` (pendiente humano TASK-20260811-002) | ✅ **Resuelto** (grep sin rastro) | — |
| `scripts/pro/tuneladora/watch_daemon.sh` — manifiesto (pendiente humano TASK-20260811-002) | ✅ **Resuelto** (grep sin rastro) | — |
| `ura-openclaw.service` | ✅ No existe (verificado `systemctl` + `/etc/systemd/system/`) | — |

## 3. Corrección aplicada (TASK-20260815-007)

**Port local de `delta_snapshot` en `scripts/pro/tuneladora/snapshot.py`:**
- Se eliminó el import dinámico de `openclaw_firmador` (módulo retirado en c6d60c8c).
- `save()` ahora lee `{nervioso}/sistema_map.json` (ruta ya definida en
  `tuneladora/config.py:141`), filtra nodos `ESPEJO`/`ZOMBIE` y escribe
  `delta_snapshots/{label}.json` con blake2b/size/mtime — misma semántica que el
  original (`.attic/tools/scripts_pro/openclaw_firmador.py:306-330`).
- Degradación explícita: JSON corrupto → log `Delta snapshot falló` + `None`.
- API pública (`save`/`exists`/`clean`) sin cambios: `engine.py:114`,
  `pipeline_refactor.py:32` y `__init__.py` no se tocaron.
- Tests actualizados (`tests/integration/test_tuneladora_cola_sandbox_snapshot.py`):
  mock de `sys.modules["openclaw_firmador"]` reemplazado por casos reales
  (mapa con ESPEJO/ZOMBIE, sin mapa, mapa corrupto). Reserva de `tests/` en
  TASK-003 resuelta con autorización expresa de Ramón (`--force`, auditada).

## 4. Validación

| Check | Resultado |
|-------|-----------|
| `pytest tests/integration/test_tuneladora_cola_sandbox_snapshot.py` | 17 passed |
| `ruff check` snapshot.py + test | All checks passed |
| Smoke `SnapshotService.save()` con mapa real | Path escrito, payload correcto |
| `sistema_map.json` real (`.nervioso/`) | JSON válido (0 nodos, mapa vacío) |

## 5. Veredicto

**GO CON CAMBIOS** — la auditoría F1 se cierra sin referencias vivas a OpenClaw
fuera de las excepciones documentadas. La degradación silenciosa de los delta
snapshots queda corregida. Resta un pendiente menor (excluido por reserva):
limpiar el ignore obsoleto en `mutmut_daily.py:73` cuando cierre TASK-003.

## 6. Pendientes

- [ ] `scripts/pro/mutmut_daily.py:73` — quitar `test_guardian_openclaw.py` del ignore
      (bloqueado por TASK-20260815-003; hacerlo al cerrar esa tarea).
- [ ] Documentar hallazgo en `docs/udo/hallazgos-fondo.md` (degradación silenciosa
      corregida) — se registra con el cierre de esta TASK.