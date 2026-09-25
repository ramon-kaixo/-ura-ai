# Propuesta — Fase 10: Estabilización

> **Versión:** 2.0 (revisada)
> **Fecha:** 2026-07-05
> **Estado:** 📋 Propuesta
> **Fase anterior:** Fase 9 (`v0.8.0-fase9`)
> **Objetivo:** Convertir la nueva arquitectura en una plataforma fiable

---

## Prerrequisitos para Iniciar (Go/No-Go)

| # | Requisito | Criterio |
|---|-----------|----------|
| G.1 | Fase 9 cerrada | `v0.8.0-fase9` tag existente en el repositorio |
| G.2 | Closeout aprobado | `docs/architecture/FASE9_CLOSEOUT.md` existe y refleja el estado real |
| G.3 | Baseline generado | Commit `f748fe0` (tag `v0.8.0-fase9`) documentado como baseline de Fase 10 |
| G.4 | Sin incidencias críticas abiertas | No hay issues bloqueantes de Fase 9 sin resolver |

**Decisión:** Go ✅ / No-Go ❌

---

## Principio Rector

Fase 10 cierra el ciclo de saneamiento arquitectónico iniciado en Fase 8.
A partir de aquí, el proyecto cambia de naturaleza: de refactorización
constante a desarrollo de capacidad de producto.

**No es Fase 10:**
- Construir nuevas funcionalidades (→ Fase 11+)
- Mejorar algoritmos de IA (→ Fase 12)
- Preparar para producción (→ Fase 13)

---

## Regla Global de No Regresión

Ninguna fase podrá degradar rendimiento, calidad o funcionalidad respecto al
baseline de la fase anterior sin documentarlo **y justificarlo** en el Closeout.

| Dimensión | Qué no puede degradarse |
|-----------|------------------------|
| Rendimiento | Tiempos de respuesta CLI, latencia de búsqueda, throughput de ingestión |
| Calidad | Tests pasando, precisión de recuperación, cobertura de código |
| Funcionalidad | Comandos CLI existentes, endpoints API, plugins cargables |

Si una fase introduce una mejora que **inherentemente** degrada una métrica
(por ejemplo, un reranker más preciso pero más lento), debe:
1. Documentar la degradación esperada en la propuesta de fase
2. Justificar por qué el trade-off es aceptable
3. Verificar en el Closeout que la degradación real está dentro de lo estimado

---

## Regla Transversal (Fases 10–13)

No abrir una fase nueva sin haber cerrado la anterior mediante:

| Paso | Requisito |
|------|-----------|
| Validación completa | Checklist de cierre (compilación, lint, tests, smoke) |
| Actualización de documentación | AGENTS.md + propuesta de fase reflejan estado real |
| Comparación con baseline | 0 regresiones funcionales vs commit/tag de inicio |
| Tag de versión | `git tag -a vX.Y.Z-faseN` |
| Acta de cierre | `docs/architecture/FASEN_CLOSEOUT.md` actual |

---

## Definición de Baseline

El baseline de cada fase es el **commit etiquetado** de la fase anterior e
incluye el estado completo del repositorio en ese punto. Para garantizar
reproducibilidad, el baseline documenta:

| Componente | Detalle |
|------------|---------|
| Hardware | CPU, GPU, RAM, almacenamiento |
| Sistema operativo | Distribución, kernel, versión |
| Python | `python --version`, entorno virtual usado |
| Modelo de embeddings | Nombre, tamaño, provider (Ollama/Qdrant) |
| Modelo LLM | Nombres, tamaños, cuantización, provider |
| Tamaño del corpus | Nº de documentos, Nº de fragmentos indexados |
| Configuración del índice | Dimensión de vectors, distancia, chunk size, overlap |
| Conjunto de evaluación | Consultas de referencia (mín. 200) con respuestas anotadas |
| Versión del repositorio | Tag git + `git rev-parse HEAD` |
| Métricas de referencia | Tests pasando/fallando, lint errors, tiempos CLI, cobertura |

Cada fase genera su propio baseline al cerrarse, que sirve como punto de
comparación para la fase siguiente.

---

## Criterios de Entrada

| # | Criterio | Estado |
|---|----------|--------|
| E.1 | Arquitectura de Fase 9 cerrada y etiquetada (`v0.8.0-fase9`) | ✅ |
| E.2 | Sin regresiones respecto al baseline (`v0.7.1-audit-fase8`) | ✅ |

---

## Objetivos

| ID | Objetivo | Descripción | Esfuerzo |
|----|----------|-------------|----------|
| 10.1 | Resolver 19 fallos conocidos | 10 en `test_knowledge_engine.py` (DB schema), 9 en `motor/tests/test_cli.py` (missing ml/) | 6-10h |
| 10.2 | Eliminar `sys.exit(78)` en imports | `core/model_router.py:78` bloquea colección de pytest para `test_unit.py` | 1-2h |
| 10.3 | Corregir `guardian_logger.py` | Syntax error: `pass` sin body bajo `except` en línea 22 | 0.5-1h |
| 10.4 | Unificar patrones de ejecución | Sustituir últimos usos dispersos de `subprocess` por `SubprocessExecutor` | 2-4h |
| 10.5 | Incrementar cobertura real | Tests nuevos para áreas críticas sin cubrir (no solo subir umbral) | 6-10h |
| 10.6 | Reducir deuda crítica de lint | Errores que afectan mantenimiento (C901, S603/S607, PTH123, DTZ005) | 3-6h |

---

## Criterios de Cierre Obligatorios

CI completamente verde, sin regresiones y sin incidencias críticas conocidas.

| # | Criterio | Detalle |
|---|----------|---------|
| C.1 | `pytest` 0 failures | En el entorno soportado |
| C.2 | Sin errores de compilación | `py_compile` 0 errores en todos los módulos |
| C.3 | Sin regresiones funcionales | Mismo comportamiento que baseline en todos los comandos CLI y endpoints |
| C.4 | CI completamente verde | Todos los hooks de pre-commit pasan (ruff, bandit, shellcheck, pytest, semgrep) |
| C.5 | Benchmark sin degradación | CLI `help/status/doctor` ≤ 2s, plugins `scan()`, DegradedMode init/restore — todos ≤ baseline +10% |
| C.6 | Sin incidencias críticas | `sys.exit(78)` eliminado, `guardian_logger.py` corregido, subprocess migrados |
| C.7 | Validación transversa | Acta de cierre, tag, baseline comparado, docs actualizados |

---

## Problemas Conocidos a Resolver

### 10.1 — 19 tests fallidos

**10 de `test_knowledge_engine.py`:**
- Causa raíz: FTS5 schema verifier detecta tablas extrañas creadas por otros tests/componentes
- Solución propuesta: Aislar tests de Knowledge Engine con fixture que limpie/verifique el schema exacto esperado
- Alternativa: Relajar el verifier para ignorar tablas con prefijo conocido (`_fts_`, `_content`, `_segments_`)

**9 de `motor/tests/test_cli.py`:**
- Causa raíz: `ModuleNotFoundError: No module named 'ml'` — dependencia faltante o no instalada
- Solución propuesta: Verificar si `ml/` es un módulo interno eliminado o externo no documentado; si es interno y no existe, corregir los imports en los tests

### 10.2 — `core/model_router.py:78`

```python
sys.exit(78)  # preflight check: detiene el proceso si algo falla
```

Esto impide que pytest coleccione cualquier archivo que importe `model_router`.
Solución: Convertir en `raise RuntimeError(...)` o almacenar el error para
consulta posterior en lugar de matar el proceso.

### 10.3 — `core/logs/guardian_logger.py:22`

```python
except:
    pass
```

El `pass` no tiene indentación válida.
Solución: `logger.exception(...)` o `pass` indentado correctamente.

### 10.4 — Últimos `subprocess` dispersos

Revisar y migrar a `SubprocessExecutor`:
- `scripts/pro/` — llamadas a `subprocess.run()` directas
- `motor/cli/cmd_ura.py` — algunas llamadas aún usan `subprocess.run` crudo
- Cualquier `os.system()` o `subprocess.Popen()` sin el wrapper

### 10.5 — Cobertura

Áreas prioritarias para nuevos tests:

| Área | Cobertura actual estimada | Prioridad |
|------|--------------------------|-----------|
| DegradedMode | ~40% | Alta |
| PluginRegistry | ~30% | Alta |
| SubprocessExecutor | ~20% | Alta |
| CLI commands (cmd_ura) | ~10% | Media |
| Knowledge Engine ingest | ~25% | Media |
| Providers (mochila) | ~15% | Media |

### 10.6 — Deuda crítica de lint

Priorizar errores que afectan mantenimiento real:

| Regla | Impacto | Archivos afectados |
|-------|---------|--------------------|
| C901 (complejidad) | Mantenibilidad | `core/`, `knowledge/engine/` |
| S603/S607 (subprocess) | Seguridad | `motor/cli/cmd_ura.py` |
| PTH123 (`open()` sin `Path`) | Consistencia | `motor/`, `scripts/` |
| DTZ005 (datetime sin timezone) | Corrección | `knowledge/`, `core/` |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Arreglar 19 tests revela bugs reales | Media | Alto | Tests primero, fix después. No estabilizar sobre roturas ocultas |
| `sys.exit(78)` es intencional (preflight duro) | Baja | Medio | Verificar con autor; si es deliberado, documentar y excluir de colección |
| Subexecutor introduce regresiones | Baja | Medio | Test de integración para cada comando migrado |
| Cobertura no mejora significativamente | Alta | Bajo | No bloquear Fase 10 por cobertura — el criterio es CI verde, no % |

---

## Línea Base

- **Commit:** `f748fe0` (tag `v0.8.0-fase9`)
- **Tests:** 449 passed, 19 failed
- **Ruff:** 80 errores (todos pre-existentes T09 backlog)
- **Plugins:** 73 descubiertos
- **CLI commands:** 37 (17 URA + 20 Knowledge Engine)
