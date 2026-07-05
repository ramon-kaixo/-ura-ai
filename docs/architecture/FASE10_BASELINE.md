# Fase 10 — Baseline

> **Generado:** 2026-07-05
> **Commit:** `e04b584` (`plan-refinado`)
> **Tag:** `v0.9.0-roadmap-f10-f13`
> **Fase anterior:** Fase 9 (`v0.8.0-fase9`)

---

## Hardware

| Componente | Valor |
|------------|-------|
| CPU | 20 núcleos ARM (NVIDIA Grace) |
| GPU | NVIDIA Blackwell (FP4/FP8, memoria unificada 128 GB) |
| RAM | 128 GB (121 GiB disponibles) |
| Almacenamiento | NVMe |

## Sistema Operativo

| Componente | Valor |
|------------|-------|
| Distribución | Ubuntu 24.04 LTS |
| Kernel | 6.17.0-1021-nvidia |
| Arquitectura | aarch64 |

## Python y Entorno

| Componente | Valor |
|------------|-------|
| Versión | 3.12.3 |
| Intérprete | `/usr/bin/python3` |
| Entorno | Sistema (no virtualenv) |

### Dependencias Clave

| Paquete | Versión |
|---------|---------|
| pytest | 9.0.3 |
| ruff | 0.15.14 |
| qdrant-client | 1.18.0 |
| chromadb | 1.5.9 |
| hypothesis | 6.153.2 |
| httpx | 0.28.1 |
| fastapi | 0.136.1 |
| uvicorn | 0.46.0 |
| pydantic | 2.13.4 |

## Repositorio

| Métrica | Valor |
|---------|-------|
| Working tree | Limpio (0 cambios sin commit) |
| Commits desde baseline anterior | 5 |
| Archivos totales | ~1.200 |

## Tests (`pytest`)

| Métrica | Valor |
|---------|-------|
| Pasados | 449 |
| Fallidos | 19 |
| Omitidos | 0 |
| Tiempo | 29.32s |
| Comando | `pytest -o "addopts=-q --tb=line" --ignore=tests/test_unit.py --ignore=tests/test_openclaw.py --ignore=tests/test_vram_guard.py --ignore=tests/test_sda.py --ignore=tests/test_snc_anomalias.py tests/ motor/tests/` |

### Tests excluidos intencionalmente

| Archivo | Razón |
|---------|-------|
| `test_unit.py` | Contiene `__import__("core.model_router")` que dispara `sys.exit(78)` |
| `test_openclaw.py` | Sintaxis inválida: `pass` sin indent tras `except` |
| `test_vram_guard.py` | Importa `model_router` → `sys.exit(78)` |
| `test_sda.py` | Importa `guardian_logger.py` (syntax error) |
| `test_snc_anomalias.py` | Dependencia de `motor/scanner/` no disponible |

### Fallos conocidos (19)

| Archivo | Failures | Causa raíz |
|---------|----------|------------|
| `tests/test_knowledge_engine.py` | 10 | FTS5 schema verifier detecta tablas extrañas de otros componentes |
| `motor/tests/test_cli.py` | 9 | `ModuleNotFoundError: No module named 'ml'` |

## Lint (`ruff`)

| Métrica | Valor |
|---------|-------|
| Errores totales | 2.315 (ruff all rules) |
| Comando | `ruff check .` |

Nota: ~80 errores relevantes para Fase 10 (C901, S603/S607, PTH123, DTZ005).
El resto son reglas de tipo estricto (ANN, ARG, etc.) no priorizadas.

## Cobertura

| Área | Cobertura |
|------|-----------|
| **Total** (core + motor + monitor) | **10%** |
| core | 8688 líneas, 7790 sin cubrir |

## Rendimiento Base

| Operación | Tiempo |
|-----------|--------|
| `pytest` completo | 29.32s |
| CLI `ura.py help` | < 100ms |
| CLI `ura.py doctor` | < 500ms |
| PluginRegistry.scan() | < 200ms |

## Incidencias Conocidas (Orden de Prioridad)

| ID | Prioridad | Descripción | Archivo |
|----|-----------|-------------|---------|
| F10-01 | 🔴 Crítica | `sys.exit(78)` en import bloquea colección de pytest | `core/model_router.py:78` |
| F10-02 | 🔴 Crítica | Syntax error: `pass` sin body bajo `except` | `core/logs/guardian_logger.py:22` |
| F10-03 | 🟡 Alta | 10 tests de KE fallan por tablas extrañas FTS5 | `tests/test_knowledge_engine.py` |
| F10-04 | 🟡 Alta | 9 tests CLI fallan por `ModuleNotFoundError: ml` | `motor/tests/test_cli.py` |
| F10-05 | 🟡 Alta | Subprocess dispersos sin `SubprocessExecutor` | Múltiples archivos |
| F10-06 | 🟢 Media | Baja cobertura en DegradedMode, PluginRegistry, Executor | — |
| F10-07 | 🟢 Media | Deuda lint crítica (C901, S603/S607, PTH123, DTZ005) | Múltiples archivos |
