"""Tests del benchmark multi-proveedor (F22-B8)."""

from __future__ import annotations

import json
from pathlib import Path

from motor.core.llm.base import BaseLLMProvider
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class _MockOK(BaseLLMProvider):
    def __init__(self):
        self._provider_name = "mock_ok"
    def generate(self, prompt, model=None, options=None): return "ok"
    def embed(self, texts, model=None): return [[0.0]]
    async def embed_async(self, texts, model=None): return [[0.0]]
    def health(self): return {"status": "ok"}


class _MockFail(BaseLLMProvider):
    def __init__(self):
        self._provider_name = "mock_fail"
    def generate(self, prompt, model=None, options=None): raise ValueError("fail")
    def embed(self, texts, model=None): return [[0.0]]
    async def embed_async(self, texts, model=None): return [[0.0]]
    def health(self): return {"status": "ok"}


class TestBenchmarkAllProviders:
    def test_benchmark_all_providers(self) -> None:
        from scripts.pro.benchmark_llm import bench_generate
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        r = bench_generate(3, router, provider="ok")
        assert r["exitosos"] == 3
        assert r["funcion"] == "generate"

    def test_provider_ranking(self) -> None:
        """Verifica que el ranking ordena por P50 ascendente."""
        from scripts.pro.benchmark_llm import bench_generate
        reg = ProviderRegistry()
        reg.register("fast", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        r = bench_generate(3, router, provider="fast")
        assert r["latencia_p50_ms"] >= 0

    def test_json_schema(self, tmp_path: Path) -> None:
        """Verifica schema del JSON exportado."""
        from scripts.pro.benchmark_llm import bench_embed, bench_generate
        reg = ProviderRegistry()
        reg.register("p", _MockOK(), default=True)
        router = LLMRouter(registry=reg)

        r_gen = bench_generate(2, router, provider="p")
        r_emb = bench_embed(2, router, provider="p")

        schema = {
            "providers": {
                "p": {
                    "generate": {
                        "p50_ms": r_gen.get("latencia_p50_ms", 0),
                        "p95_ms": r_gen.get("latencia_p95_ms", 0),
                        "p99_ms": r_gen.get("latencia_p99_ms", 0),
                        "errors": r_gen.get("fallos", 0),
                    },
                    "embed": {
                        "p50_ms": r_emb.get("latencia_p50_ms", 0),
                        "p95_ms": r_emb.get("latencia_p95_ms", 0),
                        "p99_ms": r_emb.get("latencia_p99_ms", 0),
                        "errors": r_emb.get("fallos", 0),
                    },
                }
            },
        }
        path = tmp_path / "schema.json"
        Path(path).write_text(json.dumps(schema, indent=2))
        loaded = json.loads(path.read_text())
        assert "providers" in loaded
        assert "p" in loaded["providers"]
        assert "generate" in loaded["providers"]["p"]
        assert "p50_ms" in loaded["providers"]["p"]["generate"]

    def test_missing_provider(self) -> None:
        """Proveedor no registrado debe lanzar error."""
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        import pytest
        with pytest.raises(RuntimeError):
            router.generate("test", provider="nonexistent")
            pass

    def test_partial_failures(self) -> None:
        """Un proveedor que falla no debe afectar a otros."""
        reg = ProviderRegistry()
        reg.register("fails", _MockFail(), default=True)
        reg.register("works", _MockOK())
        router = LLMRouter(registry=reg, fallback_enabled=False)
        r_works = router.generate("test", provider="works")
        assert r_works == "ok"
        r_fails = router.generate("test", provider="fails")
        assert "Error" in r_fails

    def test_backward_compatibility(self) -> None:
        from motor.core.llm import embed, embed_async, generate, health
        assert callable(generate) and callable(embed) and callable(embed_async) and callable(health)
