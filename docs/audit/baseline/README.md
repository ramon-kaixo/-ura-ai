# BLOQUE A — Baseline y Auditoría Real de URA v2.1 — Resumen Ejecutivo

**TASK**: TASK-20260817-014 · **Fecha**: 2026-08-17 · **Modo**: auditoría READ-ONLY
**Ejecutor**: TERM · **Revisor**: WEB · **Aprobador humano**: Ramón
**Referencia**: `docs/planes/PROTOCOLO_ARRANQUE_BLOQUE_A.md` · `docs/planes/PLAN_EJECUCION_TECNICO_v2.md`

## Baseline capturado (evidencia en findings.md)

| Dimensión | Valor real |
|-----------|-----------|
| Repositorio | `/home/ramon/URA/ura_ia_1972`, rama `main`, limpio al inicio (HEAD `e331c18f`), tag backup `backup_audit_20260817` |
| Sistema | Linux 6.17.0-1026-nvidia aarch64, 20 cores, RAM 121Gi (82Gi disponibles), disco 1.8T al 57% |
| GPU | NVIDIA GB10 (94% de utilización en ocioso, 48°C — a validar en Bloque B) |
| Python | 3.12.3 + pip 24.0 (sistema); `.venv` ausente tras F4 (gates degradados) |
| Servicios | 19 activos URA + 8 de soporte (ollama 0.32.7 con 13 modelos, qdrant, model-router OK, SNC, swarm); ~22 inactivos |
| Código | 9.995 archivos .py (7.405 en `.tuneladora/` — artefactos), 8.630 .json, 770 .md, 125 .sh |
| Secretos | 0 valores hardcodeados en producción; `shell=True` 0 usos reales; `eval/exec` 0 usos reales |
| Tests | `pytest tests/unit/test_protocol_coordination.py` → 7 passed (python del sistema) |

## Hallazgos (resumen)

- **P0**: ninguno detectado.
- **P1**: P1-01 `.env` 755 con API keys · P1-02 `ura-revisiones.service` 203/EXEC (script sin +x) · P1-03 `.venv` ausente (gates locales degradados) · P1-04 artefactos F4 en `/var/tmp` (volátil).
- **P2**: P2-01 `.tuneladora/` 493MB · P2-02 ~22 servicios inactivos · P2-03 `configs/` duplicado (pendiente fusión F4) · P2-04 `build/ dist/ ura.egg-info/ mutants/` en árbol · P2-05 ruido de notificaciones de revisiones.
- **P3**: GPU 94% en ocioso · unidades `systemd/` locales sin aplicar.

## Acciones realizadas (autorizadas por Ramón en A2.5)

| ID | Acción | Estado |
|----|--------|--------|
| P1-01 | `chmod 600 .env` | ✅ Aplicado y verificado (`-rw-------`) |
| P1-02 | `chmod +x scripts/pro/detectar_revisiones.sh` | ✅ Aplicado; servicio re-arrancado por el timer: 10:50:49 `0/SUCCESS` + notificación emitida |

Commit: `7beb49ca` — `fix(security): [TASK-20260817-014][WEB] corregir permisos .env y script ura-revisiones (P1 auditoría)`.

## Falsos positivos descartados

1. `shell=True` en `adr_generator.py:20` — patrón regex de auditoría, no uso real (0 usos reales).
2. `eval` en `knowledge/engine/rules.py:217` — docstring ("sin usar eval()").
3. Matches de secretos en `motor/core/secrets.py` y `audit_secrets.py` — gestor/auditor legítimos.
4. `.env.secret` 0B en `/etc/ura` — placeholder vacío.

## Plan Bloque B (hardening) — propuesto

B1 Instrumentación (regenerar `.venv`, gates completos) → B2 Superficie de archivos (`tuneladora`/build/dist/egg-info) → B3 Servicios (baja/reactivación documentada) → B4 Secretos (regla `.env` 600 en AGENTS.md) → B5 Validación y closeout.
Regla: cada sub-bloque certificable con veredicto WEB + aprobación Ramón; no abrir el siguiente sin veredicto.