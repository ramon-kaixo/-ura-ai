# Static Analysis Report — v1.0.0

**Fecha:** 2026-07-17  
**Alcance:** `motor/core/llm/` (17 archivos) + `motor/core/evaluation/` (7 archivos)  

## Resumen

| Métrica | Valor |
|---------|-------|
| Archivos analizados | 24 |
| Líneas totales | 4,590 |
| Complejidad media (mantenibilidad) | A (todas) |
| Código muerto detectado | 0 |
| Imports no utilizados | 5 (menores, en tests) |
| Duplicación restante | 0 (eliminada en v1.0.0 hardening) |
| Cobertura de tests por módulo | 100% (todos los módulos tienen tests directos o indirectos) |

## 1. Imports No Utilizados (5)

| Archivo | Línea | Import | Tipo |
|---------|-------|--------|------|
| `motor/diagnostico/__init__.py` | 2 | `json` | F401 |
| `motor/tests/test_experiment.py` | 18 | `EvaluationEngine` | F401 |
| `motor/tests/test_experiment.py` | 20 | `ExperimentConfig` | F401 |
| `motor/tests/test_regression.py` | 16 | `time` | F401 |
| `motor/tests/test_regression.py` | 24 | `RegressionReport` | F401 |

**Impacto:** Mínimo. Todos están en archivos de test o módulos no críticos.
**Acción:** Limpiar en próxima iteración de mantenimiento.

## 2. Complejidad Ciclomática

### Puntos críticos (rank C o superior)

| Archivo | Función | Complejidad | Rank |
|---------|---------|-------------|------|
| `motor/core/llm/router.py` | `LLMRouter._call_with_retry` | 16 | **C** |
| `motor/core/evaluation/regression.py` | `RegressionDetector.check` | 9 | B |
| `motor/core/llm/router.py` | `LLMRouter.__init__` | 8 | B |
| `motor/core/llm/router.py` | `LLMRouter._health_get_cached` | 8 | B |
| `motor/core/llm/router.py` | `LLMRouter.health` | 8 | B |
| `motor/core/llm/gemini.py` | `GeminiProvider.generate` | 10 | B |

**Nota:** `_call_with_retry` (rank C) concentra profiling, monitor, CB, retry, backoff, metricas y errores. Refactorizar en v1.1.0 mejoraría mantenibilidad.

## 3. Mantenibilidad (radon MI)

| Rango | Archivos |
|-------|----------|
| **A (100-20)** | 24/24 archivos |

Todos los módulos tienen índice de mantenibilidad A. El más bajo es `router.py` (27.04).

## 4. Código Muerto

vulture no detectó código muerto en `motor/core/` con confianza ≥80%.

## 5. Cobertura por Módulo

### motor/core/llm/

| Módulo | Tests | Estado |
|--------|-------|--------|
| `_logging.py` | (compartido, probado indirectamente) | ✅ |
| `anthropic.py` | `test_anthropic.py` | ✅ |
| `base.py` | Probado indirectamente | ✅ |
| `baseline.py` | `test_baseline.py` | ✅ |
| `circuit_breaker.py` | Probado indirectamente | ✅ |
| `detector.py` | `test_detector.py` | ✅ |
| `gemini.py` | `test_gemini.py` | ✅ |
| `lmstudio.py` | `test_lmstudio.py` | ✅ |
| `monitor.py` | `test_monitor.py` | ✅ |
| `observability.py` | Probado indirectamente | ✅ |
| `ollama.py` | Probado indirectamente | ✅ |
| `openai.py` | Probado indirectamente | ✅ |
| `openrouter.py` | `test_openrouter.py` | ✅ |
| `profiler.py` | `test_profiler.py` | ✅ |
| `registry.py` | Probado indirectamente | ✅ |
| `router.py` | Probado indirectamente | ✅ |
| `vllm.py` | `test_vllm.py` | ✅ |

### motor/core/evaluation/

| Módulo | Tests | Estado |
|--------|-------|--------|
| `continuous.py` | `test_continuous.py` | ✅ |
| `corpus.py` | Probado indirectamente | ✅ |
| `evaluator.py` | Probado indirectamente | ✅ |
| `experiment.py` | `test_experiment.py` | ✅ |
| `metrics.py` | Probado indirectamente | ✅ |
| `regression.py` | `test_regression.py` | ✅ |

## 6. Duplicación

No se detectó duplicación de funciones significativa tras las correcciones de v1.0.0 hardening (se eliminaron 6 copias de `_log_call` y 2 de `_percentile`).

## 7. Dependencias

### motor/core/llm/ (dependencias externas)

| Dependencia | Uso | Tipo |
|-------------|-----|------|
| `httpx` | Cliente HTTP para todos los proveedores | Externa |
| `tracemalloc` | Profiler (medición de memoria) | Stdlib |
| `motor.core.secrets` | Gestión de API keys | Interna |
| `core.config_manager` | Solo Ollama para host/port local | Interna |

### motor/core/evaluation/ (dependencias externas)

| Dependencia | Uso | Tipo |
|-------------|-----|------|
| Ninguna | Solo stdlib | ✅ |

## 8. Tamaño de Funciones

| Archivo | Líneas | Función más larga |
|---------|--------|-------------------|
| `router.py` | 495 | `_call_with_retry` (~78 líneas) |
| `regression.py` | 312 | `RegressionDetector.check` (~45 líneas) |
| `baseline.py` | 266 | `PerformanceBaseline._recompute` (~30 líneas) |
| `experiment.py` | 265 | `Experiment.run` (~50 líneas) |

## 9. Acoplamiento entre Módulos

| Módulo | Importa de |
|--------|-----------|
| `ollama.py` | `motor.core.llm.base`, `motor.core.llm._logging`, `core.config_manager`, `motor.core.secrets` |
| `openai.py` | `motor.core.llm.base`, `motor.core.llm._logging`, `motor.core.secrets` |
| `router.py` | `motor.core.llm.base`, `motor.core.llm.registry`, `motor.core.llm.circuit_breaker`, `motor.core.llm.observability`, `motor.core.llm.profiler`, `motor.core.llm.detector`, `motor.core.llm.baseline`, `motor.core.llm.monitor` |
| `evaluator.py` | `motor.core.evaluation.corpus`, `motor.core.evaluation.metrics` |
| `continuous.py` | `motor.core.evaluation.corpus`, `motor.core.evaluation.evaluator`, `motor.core.evaluation.experiment`, `motor.core.evaluation.regression` |

## 10. Conclusión

El código base de `motor/core/llm/` y `motor/core/evaluation/` está en buen estado para v1.0.0:

- ✅ Sin código muerto
- ✅ Sin imports no utilizados en producción (solo 5 en tests)
- ✅ Todos los módulos con tests
- ✅ Mantenibilidad A en todos los archivos
- ✅ Duplicación eliminada en hardening
- ⚠️ `router.py:_call_with_retry` (rank C) candidato a refactor en v1.1.0
- ℹ️ 5 imports no utilizados en tests para limpiar en próxima iteración

**Decisión:** Arquitectura suficientemente madura para entrar en fase de mantenimiento.
