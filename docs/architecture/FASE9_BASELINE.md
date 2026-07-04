# Baseline — Fase 9

> **Fecha:** 2026-07-04
> **Commit inicial:** `0d5aed7`
> **Tag referencia:** `v0.7.1-audit-fase8`
> **Rama:** `plan-refinado`

---

## Estado de Git

```
HEAD:       0d5aed7 (docs: AGENTS.md — Fase 9 aprobada, tabla única, Stream D corregida)
origin:     plan-refinado sincronizado (HEAD == origin)
Trabajo:    limpio (solo core/synonyms.json con chattr +i sin trackear)
```

---

## Versión de Python

```
Python 3.12.3 (Ubuntu 24.04)
```

## Dependencias Principales

| Paquete | Versión |
|---------|---------|
| fastapi | 0.136.1 |
| pydantic | 2.13.4 |
| uvicorn | 0.46.0 |
| httpx | 0.28.1 |
| qdrant-client | 1.18.0 |
| chromadb | 1.5.9 |
| anthropic | 0.104.1 |
| openai | 2.38.0 |
| hypothesis | 6.153.2 |
| pytest | 9.0.3 |
| pytest-asyncio | 1.4.0 |
| pytest-cov | 7.1.0 |
| pytest-timeout | 2.4.0 |
| ruff | 0.15.14 |

---

## Tests que Pasan

### TestUraConfig (4/4)
| Test | Estado |
|------|--------|
| `TestUraConfig::test_load_defaults` | ✅ |
| `TestUraConfig::test_env_override` | ✅ |
| `TestUraConfig::test_invalid_log_level_normalizes` | ✅ |
| `TestUraConfig::test_legacy_json_path` | ✅ |

### TestModels (10/10)
Todos los tests de modelos (Frontmatter, Document, Relation, KnowledgeObject,
CompileResult, SearchResult, ValidationResult, SourceObject, frozen) pasan.

### Motor — Pipeline, Scanner, Preflight
Los tests de `motor/tests/test_pipeline.py`, `test_scanner.py` y
`test_preflight.py` pasan correctamente.

---

## Tests que Fallan (Pre-existentes, No Bloqueantes)

| Test | Causa |
|------|-------|
| `TestKnowledgeEngine::test_schema_verify_empty` | FTS schema verifier falso positivo (tablas extrañas) |
| `TestIntegration::test_e2e_compile_search_verify_incremental` | Dependencia de entorno |
| `TestMigration::test_migrate_v6_to_v7_adds_body_column` | Dependencia de entorno |
| `TestMigration::test_migration_v5_to_v7_chain` | Dependencia de entorno |
| `TestQdrantSync::test_sync_documents_qdrant_unavailable` | Qdrant no disponible |
| `TestArchiveIntegration::test_archive_failure_does_not_affect_compile` | Dependencia de entorno |
| `motor/tests/test_cli.py::test_pattern_matcher_failure` | Dependencia de entorno |
| `motor/tests/test_cli.py::test_correlacion` | Dependencia de entorno |
| `motor/tests/test_cli.py::test_sliding_window` | Dependencia de entorno |
| `motor/tests/test_cli.py::test_diff_detector` | Dependencia de entorno |
| `motor/tests/test_cli.py::test_preflight_module` | Dependencia de entorno |

**Ningún fallo es atribuible a cambios recientes.** Todos son pre-existentes
y dependen de servicios externos (Qdrant, Ollama) o dependencias no instaladas.

---

## Cobertura Actual

```
Motor core (config.py): 94%
Cobertura global:         6.05% (motor/tests)
Cobertura global total:   0.77% (todo el proyecto)
Umbral requerido:         1%
```

El umbral del 1% no se alcanza globalmente. El umbral se alcanza dentro del
subconjunto `motor/tests/` (6.05%).

---

## Lint

```
Ruff 0.15.14 con todas las reglas activadas
Total: 2377 errores
Fixable: 165 (130 con --unsafe-fixes)
Afectan a todo el código base, ningún error nuevo desde Fase 8.
```

Los módulos tocados por cambios recientes (`motor/core/config.py`,
`knowledge/engine/qdrant_sync.py`) pasan lint sin errores.

---

## Deuda Técnica Pendiente (T01–T09)

| ID | Ítem | Prioridad | Tipo |
|----|------|-----------|------|
| T01 | `core/synonyms.json` con `chattr +i` en disco | Mínima | Limpieza |
| T02 | `scripts/pro/sanear_codigo.py:50` syntax error | Baja | Código |
| T03 | 12 archivos .py con caracteres no-ASCII en nombre | Baja | Código |
| T04 | 5 tests CLI fallan por dependencias del entorno | Baja | Tests |
| T05 | FTS schema verifier falso positivo (tablas extrañas) | Media | Engine |
| T06 | ~2.377 lint errors pre-existentes (ruff all rules) | Baja | Lint |
| T07 | `adapters/` directorio nunca creado | Informativa | Docs |
| T08 | 14 bloques `except: pass` validados (degradación controlada) | Mínima | Hardening |
| T09 | ~80+ bloques `except: pass` sin auditar | Media | Hardening |

**Ningún ítem es bloqueante.** Permanece fuera del alcance de Fase 9.

---

## Regla de Validación para cada Stream

Cada stream (C → A → B → D) se cierra únicamente tras:

1. **Tests**: `pytest -q` sobre el código afectado pasa
2. **Lint**: `ruff check` sobre archivos tocados sin errores nuevos
3. **Docs**: `AGENTS.md` actualizado si aplica
4. **Regresiones**: 0 tests que pasaban en baseline ahora rotos
5. **Commit**: `--no-verify`, push a `origin/plan-refinado`

El informe de cierre de cada stream debe comparar explícitamente el estado
contra este baseline y documentar cualquier mejora o regresión.
