# API Audit v1.0 RC

**Documento:** `docs/architecture/API_AUDIT_v1_RC.md`  
**Fecha:** 2026-07-16  
**Estado:** ✅ Completado

## Resumen

| Módulo | Símbolos exportados (`__all__`) | Símbolos no exportados (namespace leak) | Estado |
|--------|-------------------------------|----------------------------------------|--------|
| `motor.core.llm` | 4 | 16 | ⚠️ |
| `motor.core.evaluation` | 19 | 6 | ✅ |

## 1. `motor.core.llm` — API Pública

### Exportados oficialmente (`__all__`)

| Símbolo | Tipo | Origen | Estabilidad |
|---------|------|--------|-------------|
| `generate` | función | `OllamaProvider.generate` | ✅ Congelado (A1) |
| `embed` | función | `OllamaProvider.embed` | ✅ Congelado (A1) |
| `embed_async` | función | `OllamaProvider.embed_async` | ✅ Congelado (A1) |
| `health` | función | `OllamaProvider.health` | ✅ Congelado (A1) |

### No exportados pero visibles (namespace leak)

Estos símbolos aparecen en `dir(motor.core.llm)` pero no están en `__all__`.
Son el resultado de imports internos de Python (submodules). No forman parte
de la API pública y no deben usarse directamente.

| Símbolo | Tipo | Origen |
|---------|------|--------|
| `Any` | tipo | `typing.Any` (import en `__init__.py`) |
| `CONFIG` | dict | `core.config_manager.CONFIG` |
| `OllamaProvider` | clase | `motor.core.llm.ollama` |
| `anthropic` | módulo | Submodule |
| `base` | módulo | Submodule |
| `cls` | variable | Variable en `_get_optional_providers` |
| `gemini` | módulo | Submodule |
| `lmstudio` | módulo | Submodule |
| `log` | logger | `logging.getLogger(__name__)` |
| `logging` | módulo | `import logging` |
| `name` | variable | Variable en `_get_optional_providers` |
| `ollama` | módulo | Submodule |
| `openai` | módulo | Submodule |
| `openrouter` | módulo | Submodule |
| `provider_name` | str | Configuración de proveedor activo |
| `registry` | instancia | `ProviderRegistry` singleton |
| `vllm` | módulo | Submodule |

### Recomendación

Los submodules leaking son normales en Python. La API oficial son los 4
símbolos en `__all__`. Para RC, se podría limpiar con:

```python
# En __init__.py, después de todos los imports:
delattr(sys.modules[__name__], 'module_name')  # por cada submódulo
```

Sin embargo, esto no es necesario: `__all__` es el contrato oficial.
La recomendación es documentar que solo `__all__` constituye API pública.

## 2. `motor.core.evaluation` — API Pública

### Exportados oficialmente (`__all__`) — 19 símbolos

| Categoría | Símbolos |
|-----------|----------|
| Clases de datos | `EvaluationCorpus`, `EvaluationQuery`, `EvaluationRun`, `RetrievalResult` |
| Motor | `EvaluationEngine` |
| Experimentos | `Experiment`, `ExperimentConfig`, `ExperimentResult` |
| Regresiones | `RegressionBaseline`, `RegressionDetector`, `RegressionFinding`, `RegressionReport` |
| Evaluación Continua | `ContinuousEvaluationResult`, `ContinuousEvaluator` |
| Métricas | `recall_at_k`, `precision_at_k`, `mrr`, `map_at_k`, `ndcg_at_k` |

### Submodules leaking (6)

`continuous`, `corpus`, `evaluator`, `experiment`, `metrics`, `regression`

## 3. Circular Imports

| Módulo | Estado |
|--------|--------|
| `motor.core.llm` | ✅ Sin circular |
| `motor.core.evaluation` | ✅ Sin circular (fix en F21-B6) |

## 4. Dependencias Internas Expuestas

| Dependencia | Expuesta en | Riesgo |
|-------------|-------------|--------|
| `httpx` | `ollama.py`, `openai.py`, etc. | Bajo — es un provider detail |
| `tracemalloc` | `profiler.py` | Bajo — es interno |
| `core.config_manager.CONFIG` | `__init__.py` | Medio — expone config interna |

## 5. Tests de Contrato (A1)

Los 51 tests de contrato verifican la API pública congelada. Todos pasan.

## Conclusión

La API de `motor.core.llm` está correctamente congelada con 4 símbolos en
`__all__`. `motor.core.evaluation` tiene 19 símbolos. No hay regresiones.

El namespace leak de submodules es normal en Python y no afecta al contrato.
La guía `PROVIDER_EXTENSION_GUIDE.md` documenta cómo extender el sistema.
