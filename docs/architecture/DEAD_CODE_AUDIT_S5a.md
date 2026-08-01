# Auditoría de Código Inerte — Sprint 5a

**Fecha:** 2026-08-01 | **Commit de referencia:** c837da2
**Plan de referencia:** FASE5_PROPOSAL.md (f96ba53) | **Estado:** COMPLETADO

## 1. Resumen ejecutivo

- **3 módulos eliminados** (CONFIRMED_DEAD): `core/ura_multi_agent.py` (330 stmts), `core/sandbox_orchestrator.py` (205 stmts), `core/model_router.py` top-level (752 stmts) = **-1.287 statements** (CA1 ≥500 ✓, objetivo ≥1000 ✓)
- **1 módulo en cuarentena** (LIKELY_DEAD): `core/auto_reindex.py` (118 stmts) → `.attic/auto_reindex/` con README (eliminación propuesta: +30 días, 2026-09-01)
- **1 falso positivo corregido:** `core/mochila/mochila_server.py` es **VIVO** (ura-mochila.service lo ejecuta) — NO se elimina
- **1 script roto arreglado:** `tests/integration_smoke.sh` apuntaba a `core/model_router_main.py` inexistente → `-m core.model_router`
- **Baseline refinado:** 33.677 → **32.015 stmts**, 46.7% (suite CI-style reproducible, 2.561 tests verdes)

## 2. Inventario detallado

| Activo | Ruta | Stmts | Clase | Decisión | Justificación |
|--------|------|-------|-------|----------|---------------|
| mochila_server | core/mochila/mochila_server.py | 486 | **FALSE_POSITIVE** | Conservar | `ura-mochila.service`: `uvicorn core.mochila.mochila_server:app` (puerto 4098, activo). Referencia fuera del repo; necesita TESTS (F4), no eliminación |
| ura_multi_agent | core/ura_multi_agent.py | 330 | CONFIRMED_DEAD | Eliminado (c837da2) | Import roto (`NERVIOSO` no existe en core.agents.constants); 0 referencias productivas (solo docs y lista de archivos de patch_timestamps) |
| sandbox_orchestrator | core/sandbox_orchestrator.py | 205 | CONFIRMED_DEAD | Eliminado (c837da2) | 0 referencias reales (solo strings en patch_timestamps y agente_sandbox_codigo, agente no usado; CLASIFICACION_MODULOS.md lo marca candidato) |
| model_router (top) | core/model_router.py | 752 | CONFIRMED_DEAD | Eliminado (c837da2) | **Inalcanzable**: `import core.model_router` resuelve al paquete `core/model_router/` (verificado empíricamente); 0 imports dinámicos (runpy/spec_from_file) |
| auto_reindex | core/auto_reindex.py | 118 | LIKELY_DEAD | Cuarentena .attic/ | Es ExecStart de `ura-auto-reindex.service` (dead) → requiere decisión previa sobre el servicio antes de eliminar |

## 3. Hallazgos adicionales (errores encontrados y resueltos/documentados)

| ID | Hallazgo | Estado |
|----|----------|--------|
| H1 | `ura-agent-hierarchy.service` ejecuta `agent_hierarchy.py` **eliminado en F3** (91a1e67) | Documentado — servicio zombie, desactivar |
| H2 | `ura-capturador.service` ejecuta `app/capturador.py` archivado en F3 (2a92748) | Documentado — servicio zombie, desactivar |
| H3 | `tests/integration_smoke.sh` referencia `core/model_router_main.py` inexistente | **CORREGIDO** (c837da2) → `-m core.model_router` |
| H4 | `tests/infra/test_f25_b7_hardening.py::test_benchmark_full_recovery` flaky por interacción de orden (falla tras tests/contracts, pasa aislado) | Documentado — candidato a marcado `slow` (Fase 6) |
| H5 | Baseline 4c68db1 mezcló nightly/pending/legacy (3.167 tests) con suite CI-style; el nuevo baseline es solo CI-style reproducible (2.561 tests, 8 min) | Documentado — knowledge difiere 58.4%→45.0% por los 983 stmts cubiertos solo por tests/nightly |
| H6 | Mensaje del commit 4c68db1 decía "2511 tests" (real: 3.167 incluyendo chunk nightly) | Documentado |

## 4. Comparativa de baselines

| Paquete | Pre (4c68db1, con nightly) | Post (S5a, CI-style) | Delta stmts |
|---------|---------------------------|----------------------|-------------|
| TOTAL | 33.677 stmts · 48.6% | 32.015 stmts · 46.7% | **-1.662** |
| core | 8.377 · 16.0% | 6.972 · 14.7% | -1.405 |
| motor | 16.084 · 60.9% | 16.084 · 59.6% | 0 |
| knowledge | 7.358 · 58.4% | 7.358 · 45.0% | 0 (diferencia: nightly) |
| monitor | 957 · 54.4% | 819 · 57.0% | -138 |
| mantenimiento | 525 · 20.2% | 406 · 62.8% | -119 |

Nota: core -1.405 = 3 eliminados (1.287) + cierre de cobertura de ficheros que solo importaban los eliminados. mantenimiento sube 20.2→62.8% porque ura_maintenance (con 122 tests F4) ahora se mide... (el fichero mantenimiento/ura_maintenance.py se mide igual; la subida es efecto de denominador).

## 5. Pendientes y destino

| Ítem | Recomendación | Sprint destino |
|------|---------------|----------------|
| auto_reindex.py (cuarentena) | Decidir destino de ura-auto-reindex.service → eliminar a partir de 2026-09-01 | Fase 6 |
| ura-agent-hierarchy.service zombie | Desactivar unit (requiere root) | Fase 6 |
| ura-capturador.service zombie | Desactivar unit | Fase 6 |
| mochila_server.py (VIVO, 0% cobertura) | Tests F4 obligatorios (486 stmts, servidor FastAPI activo) | F4 4b |
| test_benchmark_full_recovery flaky | Marcarlo `slow` o aislar | Fase 6 |
| Shadowing core/model_router/__init__.py (M6) | Corregir con ADR | F5 5b |
| Bugs ura_maintenance (is_safe_to_delete, freed=0) | Fix con ADR | F5 5b |
| Otros candidatos del CLASIFICACION_MODULOS.md (core/reranker, change_guardian, memoria/detectores...) | Auditoría de la otra entidad; revisar en 5a fase 2 | F5 5b |

## 6. Comandos de verificación

```bash
# Suite CI-style (reproducible, ~8 min)
rm -f .coverage
python3 -m pytest tests/knowledge tests/contracts tests/infra -q --timeout=60 --cov=. 
python3 -m pytest tests/unit -q --timeout=60 --cov=. --cov-append
python3 -m pytest tests/integration -q --timeout=120 --cov=. --cov-append
python3 -m coverage json -o data/baseline/coverage_f4.json
# Módulos eliminados no importables:
python3 -c "import core.ura_multi_agent"  # ImportError esperado (eliminado)
# Recuperación si necesario:
git checkout c837da2~1 -- core/ura_multi_agent.py core/sandbox_orchestrator.py core/model_router.py
