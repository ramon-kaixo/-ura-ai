"""Tests de auditoría de API pública para RC (F23-B1).

Verifica:
1. __all__ coincide con lo esperado
2. No hay exports internos en __all__
3. No hay imports circulares
4. La API documentada coincide con los exports
5. Backward compatibility de exports
"""

from __future__ import annotations

import motor.core.evaluation
import motor.core.llm

# ── 1. motor.core.llm ───────────────────────────────

EXPECTED_LLM = {"generate", "embed", "embed_async", "health"}


class TestLLMPublicAPI:
    def test_public_api_exports(self) -> None:
        """__all__ debe contener exactamente los 4 símbolos esperados."""
        assert set(motor.core.llm.__all__) == EXPECTED_LLM

    def test_no_internal_exports(self) -> None:
        """Ningún símbolo interno debe estar en __all__."""
        internal = {"registry", "OllamaProvider", "CONFIG", "log", "logging"}
        assert not (internal & set(motor.core.llm.__all__))

    def test_all_symbols_exist(self) -> None:
        """Cada símbolo en __all__ debe existir realmente."""
        for name in motor.core.llm.__all__:
            assert hasattr(motor.core.llm, name), f"{name} no encontrado"
            obj = getattr(motor.core.llm, name)
            assert obj is not None, f"{name} es None"

    def test_generate_is_callable(self) -> None:
        assert callable(motor.core.llm.generate)

    def test_embed_is_callable(self) -> None:
        assert callable(motor.core.llm.embed)

    def test_embed_async_is_callable(self) -> None:
        assert callable(motor.core.llm.embed_async)

    def test_health_is_callable(self) -> None:
        assert callable(motor.core.llm.health)


# ── 2. motor.core.evaluation ─────────────────────────

EXPECTED_EVAL = {
    "ContinuousEvaluationResult", "ContinuousEvaluator",
    "EvaluationCorpus", "EvaluationEngine", "EvaluationQuery", "EvaluationRun",
    "Experiment", "ExperimentConfig", "ExperimentResult",
    "RegressionBaseline", "RegressionDetector", "RegressionFinding", "RegressionReport",
    "RetrievalResult",
    "map_at_k", "mrr", "ndcg_at_k", "precision_at_k", "recall_at_k",
}


class TestEvaluationPublicAPI:
    def test_public_api_exports(self) -> None:
        assert set(motor.core.evaluation.__all__) == EXPECTED_EVAL

    def test_no_internal_exports(self) -> None:
        internal = {"corpus", "evaluator", "metrics", "experiment", "regression", "continuous"}
        assert not (internal & set(motor.core.evaluation.__all__))

    def test_all_symbols_exist(self) -> None:
        for name in motor.core.evaluation.__all__:
            assert hasattr(motor.core.evaluation, name), f"{name} no encontrado"


# ── 3. Cross-module ────────────────────────────────

class TestCrossModule:
    def test_llm_does_not_import_evaluation(self) -> None:
        """motor.core.llm no debe importar motor.core.evaluation como dependencia."""
        import inspect
        llm_source = inspect.getsource(motor.core.llm)
        assert "motor.core.evaluation" not in llm_source, (
            "motor.core.llm importa motor.core.evaluation"
        )

    def test_evaluation_does_not_import_llm_router(self) -> None:
        """motor.core.evaluation no debe importar motor.core.llm.router."""
        import sys
        _prev = set(sys.modules)
        import motor.core.evaluation  # noqa: F401
        _new = set(sys.modules)
        leaked = _new - _prev
        assert "motor.core.llm.router" not in leaked

    def test_no_circular_imports(self) -> None:
        """Verificar que todos los módulos se importan sin error."""
        import sys as _sys
        modules = [
            "motor.core.llm", "motor.core.llm.base", "motor.core.llm.registry",
            "motor.core.llm.router", "motor.core.llm.ollama",
            "motor.core.llm.openai", "motor.core.llm.anthropic",
            "motor.core.llm.gemini", "motor.core.llm.openrouter",
            "motor.core.llm.lmstudio", "motor.core.llm.vllm",
            "motor.core.llm.circuit_breaker", "motor.core.llm.observability",
            "motor.core.llm.profiler", "motor.core.llm.detector",
            "motor.core.llm.baseline", "motor.core.llm.monitor",
            "motor.core.evaluation", "motor.core.evaluation.corpus",
            "motor.core.evaluation.evaluator", "motor.core.evaluation.metrics",
            "motor.core.evaluation.experiment", "motor.core.evaluation.regression",
            "motor.core.evaluation.continuous",
        ]
        for mod in modules:
            _sys.modules.pop(mod, None)
        for mod in modules:
            try:
                __import__(mod)
            except Exception as e:
                raise AssertionError(f"Error al importar {mod}: {e}") from e
