# Closeout — PLAN mutmut + hypothesis (v5): barrido diario progresivo

**Fecha**: 2026-08-09
**Tarea**: TASK-20260809-002
**Plan**: v5 (aprobado por Ramón con correcciones F1-F9 del análisis)
**Estado**: IMPLEMENTADO — pendiente de activación del timer (sudo Ramón)

---

## 1. Resumen

Implementada la revisión de calidad de tests con **mutmut (mutation testing)** y **hypothesis (property-based)**:
- **Barrido diario progresivo** a las 06:00 (lotes equilibrados, un lote por día, ~5 días/ciclo) → reportes + TASK UDO para revisión de Terminal.
- **Feedback local <10s**: hook pre-commit `pytest-delta` que valida solo los tests relacionados con lo tocado.
- **Sin fricción**: mutmut NO está en pre-commit; rollback solo systemd (no toca git).

## 2. Fases implementadas

| Fase | Contenido | Evidencia |
|------|-----------|-----------|
| **F0** | Retirados tests huérfanos de `scripts.pro.mcp_mochila` (módulo archivado en purga `38b7921c`): `motor/tests/test_mcp_server.py` eliminado + 2 tests MCP de `test_e2e.py` retirados con nota | `pytest --collect-only` → **6378 tests, 0 errores** (antes: 1 error) |
| **F1** | `[tool.mutmut]` con `source_paths` (clave válida 3.7; `paths_to_mutate` deprecada) + perfiles hypothesis `dev`/`ci` en `tests/conftest.py` con `load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))` | `Config.get().source_paths` OK; ambos perfiles pasan (5+5) |
| **F2** | `scripts/pro/mutmut_daily.py` (lotes equilibrados por día de semana, reporte markdown, **TASK UDO creada** con estado BLOCKED si falla) + `deploy/timers/ura-mutmut-daily.{service,timer}` (06:00 diario) | dry-run OK; units validadas con systemd-analyze; mutmut real generó mutantes en core/ |
| **F3** | Hook pre-commit `pytest-delta` (`scripts/pro/pytest_delta.sh`) con **mapeo archivo→tests** (no pasa código a pytest — evita exit 5) | `pre-commit run pytest-delta --files motor/core/llm/_state.py` → Passed; 12 passed en 0.49s |
| **F4** | `docs/engineering/MUTMUT.md` (arquitectura, comandos, rollback no destructivo, umbral 80% informativo) | documento creado |

## 3. Correcciones aplicadas (de las 9 del análisis)

F1 ✅ (decisión: retirar tests huérfanos — herramienta archivada sin consumidores) · F2 ✅ (`source_paths`) · F3 ✅ (mapeo archivo→tests, verificado con pytest 0-items evitado) · F4 ✅ (TASK UDO creada por el script) · F5 ✅ (`load_profile` por env) · F6 ✅ (`scripts/pro/`) · F7 ✅ (sin clave `runner` inventada) · F8 ✅ (lotes equilibrados 5 grupos) · F9 ✅ (exit code → TASK BLOCKED)

## 4. Validación

| Comprobación | Resultado |
|--------------|-----------|
| `pytest --collect-only` (todo) | 6378 tests, 0 errores ✅ |
| `tests/udo/test_udo.sh` | 35 OK, 0 FAIL ✅ |
| `tests/engineering/test_engineering.sh` | 13 OK, 0 FAIL ✅ |
| pytest tocado (e2e + hypothesis + properties) | 13 passed ✅ |
| `mutmut run core/model_router` (prueba real) | generó mutantes, exit 0 ✅ |
| `mutmut results` | funciona (cache) ✅ |
| perfiles hypothesis dev/ci | ambos pasan ✅ |
| hook pytest-delta (código + test) | Passed, <1s ✅ |
| `systemd-analyze verify` (units propias) | sin errores ✅ |
| ruff (script nuevo) | 0 errores ✅ |

## 5. Pendientes (requieren sudo Ramón)

```bash
# 1. Activar el timer diario (barrido automático desde mañana 06:00)
sudo cp deploy/timers/ura-mutmut-daily.service deploy/timers/ura-mutmut-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ura-mutmut-daily.timer

# 2. Verificar que el timer quedó activo
systemctl list-timers | grep mutmut
```

## 6. Riesgos residuales

- El primer ciclo completo tardará ~5 días (un lote/día); los lotes grandes (motor/core, core) pueden tardar horas en la madrugada — por diseño (asíncrono, sin penalizar jornada).
- El umbral ≥80% es **aspiracional e informativo** el primer mes (no bloquea nada); se revisa al completar el primer ciclo.
- Si un lote falla, el script crea la TASK como BLOCKED con el exit code (no finge éxito).

## 7. Reversibilidad

```bash
sudo systemctl disable --now ura-mutmut-daily.timer
sudo rm /etc/systemd/system/ura-mutmut-daily.* && sudo systemctl daemon-reload
# + quitar pytest-delta de .pre-commit-config.yaml si se desea
```

---

*Closeout por TERM (TASK-20260809-002). Revisión: pendiente de lote review-pending (AUTO-REVISIÓN honesta).*
