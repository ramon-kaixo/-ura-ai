# Línea Base URA — 2026-07-31

Captura del estado inicial del repositorio antes de la Fase 1 (auditoría).
Todas las mediciones se ejecutaron en GX10, commit `80fbe73`, main.

## Git
- HEAD: `80fbe73` (main)
- Commits: 1014 total, 65 ahead of origin/main (sin push)
- Working tree limpio (pendientes: ADR-082/083 ya commiteados)

## Inventario
| Paquete | Archivos .py | LOC |
|---------|-------------|-----|
| core | 139 | 16.549 |
| motor | 305 | 41.905 |
| knowledge | 90 | 15.928 |
| agents | 7 | 450 |
| scripts | 231 | 38.528 |
| tests | 146 | 36.973 |
| **Total repo** | **4421** | **409.739** |

Módulos LOC pesados (candidatos refactor Fase 5):
- `core/model_router.py` — 1292 líneas
- `motor/core/fusion/stages/entity_resolver.py` — 764
- `core/mochila/mochila_server.py` — 752
- `knowledge/engine/rules.py` — 712
- `core/ura_multi_agent.py` — 631

## Calidad
| Herramienta | Resultado |
|-------------|-----------|
| Ruff check | **37 errores**: 27 EXE002, 7 S101, 2 LOG015, 1 ASYNC240 |
| Ruff format | 1 archivo sin formato: `motor/core/fusion/fact_history.py` |
| Mypy | **No pasa** — 1 error de sintaxis real: `scripts/pro/inspectores.py:135` (paréntesis desbalanceados); `build/` artefacto en disco sin excluir en config |
| Pytest | **54 failed / 2945 passed / 58 skipped** en 586s (9:46) |
| Cobertura | **81%** global (48.984 stmts, 9.325 missing) |
| Bandit | 1627 hallazgos: 42 MEDIUM+HIGH, 1585 LOW. Top: 17 hardcoded_tmp_directory, 16 blacklist, 4 huggingface_unsafe_download, 3 hardcoded_sql, 2 bind_all_interfaces |
| Complejidad | 0 funciones con ciclomática ≥ 20 (radon) |
| Ciclos | 0 dependencias circulares (core→motor→knowledge, unidireccional) |

## Fallos de pytest (54) — clasificación
| Grupo | Archivo | Nº | Tipo |
|-------|---------|-----|------|
| Pending | `tests/pending/test_audit_conversation.py` | 7 | Concurrencia + lógica (tests marcados pending) |
| Auth | `tests/unit/test_auth_middleware.py` | 6 | Auth middleware (¿comportamiento o test?) |
| Concurrencia | `tests/unit/test_message_store.py` | 1 | test_concurrent_appends |
| **Total contabilizado en log** | | 14 | Resto (40) sin capturar por truncado del log |

> Nota: el log truncado no capturó los 54 FAILED completos; la lista íntegra se obtendrá en Fase 1 con `--tb=no -rN`.

## Módulos con cobertura < 20% (objetivo Fase 4)
- 10% `core/model_router/handler.py`
- 11% `core/model_router/dashboard.py`
- 11% `motor/observability/exporter.py`
- 15% `mantenimiento/ura_maintenance.py`
- 16% `motor/core/llm/base.py`
- 17% `monitor/health_check.py`
- 18% `motor/core/web/cleaner/deduplication.py`
- 19% `knowledge/engine/ontology/schema_org.py`
- 19% `motor/assistant/metrics.py`

68 módulos con cobertura < 50%. 0 módulos al 0% exacto en el report
(los nunca importados ni aparecen — detectarlos con vulture en Fase 1).

## Vulture (código muerto potencial — Fase 1/2)
- 543 usos "unused" en core+motor+knowledge (confianza 60%)
- Top sospechosos: `score_evidence` (4), `check_available` (4), `to_envelope` (3), `shutdown` (3), `wait_if_needed` (2), `valid_transitions` (2), `serialize` (2), `run_one` (2), `replan` (2)

## Hallazgos (no corregidos — registrados)
1. **Hang post-suite**: pytest no termina tras el último test (añade ~12 min al proceso; primera pasada 20m reales para 7:47 de tests). Sospecha: thread no-daemon o fixture teardown. Investigar en Fase 1.
2. **`scripts/pro/inspectores.py:135`**: error de sintaxis real (pre-existente) — bloquea mypy global.
3. **`build/` en disco**: artefacto instalación (5,6MB, gitignored) que mypy escanea; config mypy sin `exclude`.
4. **Ruff**: `EXE002` (27) = ejecutables sin shebang en scripts; `S101` (7) = assert en producción; `LOG015` (2); `ASYNC240` (1).
5. **Bandit 42 MEDIUM/HIGH**: concentrados en `cleanup.py` (7), `model_router.py` (4), `reranker.py` (4) — verificar si son código vivo en Fase 1.
6. **5 fallos pre-existentes** en `test_audit_intent.py` (TestMultiline, TestEmptyAndWhitespace, TestClassificationBoundaries) — fuera de regresión, documentados.
7. **Cobertura global 81%** — objetivo plan maestro ≥90%.

## Herramientas disponibles
ruff 0.15.14, mypy 1.18.2, bandit 1.9.4, coverage 7.14.1 (pytest-cov 7.1.0),
vulture 2.16, radon 6.0.1, hypothesis 6.153.2, pytest 9.0.3.
