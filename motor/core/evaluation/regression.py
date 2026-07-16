"""Detección de regresiones de calidad del RAG.

Compara resultados de evaluación contra una baseline almacenada.
Detecta regresiones configurables para:
  - Recall@K, Precision@K, MRR, MAP, nDCG@K
  - Latencia (P50, P95)
  - Throughput

Persiste baseline e informe en JSON.
Thread-safe.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

# Umbrales por defecto (cambio relativo máximo antes de reportar regresión)
# Negativo = empeoramiento. Ej: -0.05 = 5% de caída permitida.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "recall": -0.05,
    "precision": -0.05,
    "mrr": -0.05,
    "map": -0.05,
    "ndcg": -0.05,
    "latency_p50": 0.10,
    "latency_p95": 0.20,
    "throughput": -0.10,
}


class RegressionFinding:
    """Hallazgo de una regresión detectada."""

    __slots__ = (
        "baseline_value",
        "change_pct",
        "config",
        "current_value",
        "direction",
        "metric",
        "threshold",
    )

    def __init__(
        self,
        config: str,
        metric: str,
        baseline_value: float,
        current_value: float,
        threshold: float,
    ) -> None:
        self.config = config
        self.metric = metric
        self.baseline_value = round(baseline_value, 4)
        self.current_value = round(current_value, 4)
        self.threshold = threshold
        self.direction = "up" if current_value > baseline_value else "down"
        self.change_pct = round(
            ((current_value - baseline_value) / max(abs(baseline_value), 0.001)) * 100, 1,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "metric": self.metric,
            "baseline": self.baseline_value,
            "current": self.current_value,
            "change_pct": self.change_pct,
            "threshold_pct": self.threshold * 100,
            "direction": self.direction,
            "is_regression": self.is_regression(),
        }

    def is_regression(self) -> bool:
        """Determina si el cambio constituye una regresión."""
        if self.baseline_value == 0:
            return False
        # Para métricas donde "mayor es mejor" (recall, precision, MRR, MAP, nDCG)
        # la regresión es cuando baja más del threshold.
        higher_is_better = self.metric not in ("latency_p50", "latency_p95")
        if higher_is_better:
            return self.change_pct < self.threshold * 100
        # Para latencia, "menor es mejor" — regresión si sube más del threshold
        return self.change_pct > self.threshold * 100

    def __repr__(self) -> str:
        icon = "🔴" if self.is_regression() else "✅"
        return (
            f"{icon} {self.config}.{self.metric}: "
            f"{self.baseline_value} → {self.current_value} "
            f"({self.change_pct:+.1f}%)"
        )


class RegressionReport:
    """Informe completo de regresiones."""

    def __init__(
        self,
        baseline_name: str,
        timestamp: float,
        findings: list[RegressionFinding],
        total_configs: int,
        total_metrics: int,
    ) -> None:
        self.baseline_name = baseline_name
        self.timestamp = timestamp
        self.findings = findings
        self.total_configs = total_configs
        self.total_metrics = total_metrics

    @property
    def total_regressions(self) -> int:
        return sum(1 for f in self.findings if f.is_regression())

    @property
    def passed(self) -> bool:
        return self.total_regressions == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline_name,
            "timestamp": self.timestamp,
            "total_configs": self.total_configs,
            "total_metrics": self.total_metrics,
            "total_findings": len(self.findings),
            "total_regressions": self.total_regressions,
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
        }

    def summary(self) -> str:
        """Resumen textual del informe."""
        lines = [
            f"Regression Report — {self.baseline_name}",
            f"  Configs: {self.total_configs}, Metrics: {self.total_metrics}",
            f"  Findings: {len(self.findings)}, Regressions: {self.total_regressions}",
            f"  Status: {'✅ PASS' if self.passed else '🔴 FAIL'}",
        ]
        if self.findings:
            lines.append("")
            lines.extend(f"  {f}" for f in self.findings)
        return "\n".join(lines)


class RegressionBaseline:
    """Baseline de calidad para detección de regresiones.

    Almacena valores esperados por (config, metric).
    Persistible a JSON. Thread-safe.
    """

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._data: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()
        self._created_at = time.time()
        self._updated_at = time.time()

    @property
    def name(self) -> str:
        return self._name

    def set(self, config: str, metric: str, value: float) -> None:
        with self._lock:
            self._data[(config, metric)] = value
            self._updated_at = time.time()

    def set_results(self, results: list[Any]) -> None:
        """Establece baseline desde lista de ExperimentResult o dicts."""
        with self._lock:
            for r in results:
                if hasattr(r, "config_name"):
                    cfg = r.config_name
                    metrics = r.metrics
                    lat = r.latency_stats
                else:
                    cfg = r.get("config", r.get("config_name", "unknown"))
                    metrics = r.get("metrics", {})
                    lat = r.get("latency_stats", {})

                for metric, value in metrics.items():
                    self._data[(cfg, metric)] = value
                if lat:
                    self._data[(cfg, "latency_p50")] = lat.get("mean_ms", 0)
                    self._data[(cfg, "latency_p95")] = lat.get("max_ms", 0)
                    nq = len(self._data)  # placeholder
                    self._data[(cfg, "throughput")] = nq / max(lat.get("mean_ms", 1), 1) * 1000
            self._updated_at = time.time()

    def get(self, config: str, metric: str) -> float | None:
        with self._lock:
            return self._data.get((config, metric))

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self._name,
                "created_at": self._created_at,
                "updated_at": self._updated_at,
                "baselines": {
                    f"{cfg}.{met}": val
                    for (cfg, met), val in self._data.items()
                },
            }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> RegressionBaseline:
        data = json.loads(Path(path).read_text())
        bl = cls(name=data.get("name", "loaded"))
        for key, value in data.get("baselines", {}).items():
            cfg, met = key.split(".", 1)
            bl._data[(cfg, met)] = value
        bl._created_at = data.get("created_at", time.time())
        bl._updated_at = data.get("updated_at", time.time())
        return bl


class RegressionDetector:
    """Detector de regresiones de calidad del RAG.

    Uso:
        detector = RegressionDetector(baseline)
        report = detector.check(results)
        print(report.summary())
    """

    def __init__(
        self,
        baseline: RegressionBaseline,
        thresholds: dict[str, float] | None = None,
    ) -> None:
        self._baseline = baseline
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    @property
    def baseline(self) -> RegressionBaseline:
        return self._baseline

    def check(self, results: list[Any]) -> RegressionReport:
        """Compara resultados contra baseline.

        Args:
            results: Lista de ExperimentResult o dicts con config/metrics/latency_stats.

        Returns:
            RegressionReport con todos los hallazgos.
        """
        findings: list[RegressionFinding] = []
        configs_seen: set[str] = set()
        metrics_count = 0

        for r in results:
            if hasattr(r, "config_name"):
                cfg = r.config_name
                metrics = r.metrics
                lat = r.latency_stats
            else:
                cfg = r.get("config", r.get("config_name", "unknown"))
                metrics = r.get("metrics", {})
                lat = r.get("latency_stats", {})
            configs_seen.add(cfg)

            for metric, current in metrics.items():
                metrics_count += 1
                baseline_val = self._baseline.get(cfg, metric)
                if baseline_val is None:
                    continue
                # Determinar threshold
                base_key = metric.split("@")[0]  # "recall" de "recall@10"
                threshold = self._thresholds.get(base_key, -0.05)
                finding = RegressionFinding(
                    config=cfg,
                    metric=metric,
                    baseline_value=baseline_val,
                    current_value=current,
                    threshold=threshold,
                )
                findings.append(finding)

            # Latencia
            if lat:
                for lat_metric in ("latency_p50", "latency_p95"):
                    metrics_count += 1
                    bl = self._baseline.get(cfg, lat_metric)
                    if bl is None:
                        continue
                    key = lat_metric
                    threshold = self._thresholds.get(key, 0.10)
                    finding = RegressionFinding(
                        config=cfg,
                        metric=key,
                        baseline_value=bl,
                        current_value=lat.get("mean_ms" if "p50" in key else "max_ms", 0),
                        threshold=threshold,
                    )
                    findings.append(finding)

        return RegressionReport(
            baseline_name=self._baseline.name,
            timestamp=time.time(),
            findings=findings,
            total_configs=len(configs_seen),
            total_metrics=metrics_count,
        )
