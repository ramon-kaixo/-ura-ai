"""Tests para motor/cli/public_api.py y motor/core/evaluation/__init__.py — re-exports."""
from __future__ import annotations


class TestPublicApi:
    def test_imports_core(self) -> None:
        from motor.cli.public_api import (
            DegradedMode,
            QdrantClient,
            SubprocessExecutor,
            UraConfig,
            get_secret,
            has_secret,
            require_secret,
        )

        assert UraConfig is not None
        assert QdrantClient is not None
        assert SubprocessExecutor is not None
        assert DegradedMode is not None
        assert callable(get_secret)
        assert callable(has_secret)
        assert callable(require_secret)

    def test_imports_events(self) -> None:
        from motor.cli.public_api import SYSTEM_STARTED, EventBus

        assert EventBus is not None
        assert isinstance(SYSTEM_STARTED, str)

    def test_imports_memory(self) -> None:
        from motor.cli.public_api import Episode, EpisodeStore, EpisodeStoreConfig

        assert Episode is not None
        assert EpisodeStore is not None
        assert EpisodeStoreConfig is not None

    def test_imports_retrieval(self) -> None:
        from motor.cli.public_api import HybridRetriever, LexicalRetriever, VectorRetriever

        assert HybridRetriever is not None
        assert LexicalRetriever is not None
        assert VectorRetriever is not None

    def test_imports_observability(self) -> None:
        from motor.cli.public_api import HealthRegistry, MetricsRegistry, format_prometheus

        assert HealthRegistry is not None
        assert MetricsRegistry is not None
        assert callable(format_prometheus)

    def test_all_completo(self) -> None:
        import motor.cli.public_api as api

        for name in api.__all__:
            assert hasattr(api, name), f"__all__ incluye {name} pero no existe"


class TestEvaluationInit:
    def test_exports(self) -> None:
        import motor.core.evaluation as ev

        for name in ev.__all__:
            assert hasattr(ev, name), f"__all__ incluye {name} pero no existe"

    def test_clases_importables(self) -> None:
        from motor.core.evaluation import (
            ContinuousEvaluator,
            EvaluationEngine,
            Experiment,
            RegressionDetector,
            map_at_k,
            mrr,
        )

        assert all(x is not None for x in [ContinuousEvaluator, EvaluationEngine, Experiment, RegressionDetector])
        assert callable(mrr)
        assert callable(map_at_k)
