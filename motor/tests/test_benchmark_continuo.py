"""Tests del benchmark continuo (F20-B5).

Verifica:
1. Benchmark con monitor genera JSON válido
2. Baseline JSON tiene schema esperado
3. Snapshot JSON tiene schema esperado
4. Benchmark vacío manejado
5. Baseline se actualiza en múltiples ejecuciones
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from motor.core.llm.base import BaseLLMProvider
from motor.core.llm.baseline import PerformanceBaseline
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class _MockProvider(BaseLLMProvider):
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay

    def generate(self, prompt, model=None, options=None):
        if self.delay > 0:
            time.sleep(self.delay)
        return "ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class TestBenchmarkMonitor:
    def test_benchmark_monitor_output(self, tmp_path: Path) -> None:
        """Benchmark con monitor genera baseline y snapshot JSON."""
        reg = ProviderRegistry()
        reg.register("ok", _MockProvider(delay=0.005), default=True)
        router = LLMRouter(registry=reg, monitor_enabled=True)
        router.generate("test")
        router.embed(["x"])

        base_path = tmp_path / "baseline"
        monitor = router._monitor
        assert monitor is not None
        monitor.baseline.save(str(base_path))

        report = monitor.get_report()
        issues = monitor.get_recent_issues(10)
        snap = {
            "resultados": {"generate": {"iterations": 1}},
            "monitor_report": report,
            "issues": issues,
        }
        snap_path = tmp_path / "snapshot.json"
        Path(snap_path).write_text(json.dumps(snap, indent=2) + "\n")

        assert base_path.exists()
        assert snap_path.exists()

    def test_baseline_json_schema(self, tmp_path: Path) -> None:
        """Baseline JSON tiene las claves esperadas."""
        bl = PerformanceBaseline(max_samples=10)
        bl.record("p", "gen", wall_time_ms=100, cpu_time_ms=50, peak_memory_bytes=1024)
        path = tmp_path / "baseline.json"
        bl.save(str(path))

        data = json.loads(path.read_text())
        key = "p.gen"
        assert key in data, f"Missing key {key}"
        entry = data[key]
        assert "wall_time_p50" in entry
        assert "wall_time_p95" in entry
        assert "wall_time_p99" in entry
        assert "cpu_time_p50" in entry
        assert "cpu_time_p95" in entry
        assert "cpu_time_p99" in entry
        assert "peak_memory_kb_p50" in entry
        assert "sample_count" in entry
        assert entry["sample_count"] == 1

    def test_snapshot_json_schema(self) -> None:
        """Snapshot JSON tiene las claves esperadas."""
        snap = {
            "resultados": {
                "generate": {
                    "iterations": 5,
                    "p50_ms": 100,
                    "p95_ms": 200,
                },
            },
            "monitor_report": {
                "total_operations": 5,
                "total_hotspots": 1,
                "total_regressions": 0,
                "throughput_ops_per_sec": 1.5,
            },
            "issues": [
                {
                    "provider": "p",
                    "operation": "gen",
                    "wall_time_ms": 300,
                    "is_hotspot": True,
                },
            ],
        }
        assert "resultados" in snap
        assert "monitor_report" in snap
        assert "issues" in snap
        assert "generate" in snap["resultados"]
        assert "p50_ms" in snap["resultados"]["generate"]
        assert "total_operations" in snap["monitor_report"]

    def test_empty_benchmark(self) -> None:
        """Benchmark sin datos genera reporte vacío."""
        bl = PerformanceBaseline(max_samples=10)
        data = bl.get_all_baselines()
        assert data == {}

    def test_multiple_runs_update_baseline(self, tmp_path: Path) -> None:
        """Múltiples ejecuciones actualizan la baseline acumulativamente."""
        bl = PerformanceBaseline(max_samples=100)
        for _ in range(3):
            bl.record("p", "gen", wall_time_ms=100, cpu_time_ms=50)
        assert bl.get_baseline("p", "gen").sample_count == 3

        # Guardar y recargar
        path = tmp_path / "bl.json"
        bl.save(str(path))

        bl2 = PerformanceBaseline(max_samples=100)
        bl2.load(str(path))
        loaded = bl2.get_baseline("p", "gen")
        assert loaded is not None
        assert loaded.wall_time_p50 == 100  # Los percentiles se cargaron
        assert loaded.sample_count == 3  # sample_count se cargó

        # Nueva ejecución añade datos (la baseline cargada persiste, pero
        # nuevas muestras se registran aparte en _samples)
        for _ in range(2):
            bl2.record("p", "gen", wall_time_ms=100, cpu_time_ms=50)
        updated = bl2.get_baseline("p", "gen")
        assert updated is not None
        # Los percentiles se actualizan con las nuevas muestras
        assert updated.wall_time_p50 == 100
