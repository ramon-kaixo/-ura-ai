"""MetricsCollector — recolección de métricas con formato Prometheus."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any


class MetricsCollector:
    def __init__(self) -> None:
        self.metrics: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(int))
        self.metrics_history: dict[str, list[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def increment(self, metric: str, labels: dict[str, str] | None = None) -> None:
        with self.lock:
            key = self._make_key(metric, labels)
            self.metrics[key]["count"] += 1
            self.metrics[key]["last_updated"] = time.time()

    def record_latency(self, metric: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self.lock:
            key = self._make_key(metric, labels)
            self.metrics[key]["latency_sum"] += value
            self.metrics[key]["latency_count"] += 1
            self.metrics[key]["latency_avg"] = self.metrics[key]["latency_sum"] / self.metrics[key]["latency_count"]
            self.metrics_history[key].append(value)
            if len(self.metrics_history[key]) > 1000:
                self.metrics_history[key].pop(0)

    def record_error(self, metric: str, error_type: str, labels: dict[str, str] | None = None) -> None:
        with self.lock:
            key = self._make_key(metric, labels)
            self.metrics[key]["errors"] = self.metrics[key].get("errors", {})
            self.metrics[key]["errors"][error_type] = self.metrics[key]["errors"].get(error_type, 0) + 1

    def _make_key(self, metric: str, labels: dict[str, str] | None = None) -> str:
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f"{metric}{{{label_str}}}"
        return metric

    def get_prometheus_format(self) -> str:
        lines: list[str] = []
        with self.lock:
            for key, data in self.metrics.items():
                if "count" in data:
                    lines.append(f"{key}_count {data['count']}")
                if "latency_avg" in data:
                    lines.append(f"{key}_latency_avg {data['latency_avg']:.3f}")
                if "errors" in data:
                    for error_type, count in data["errors"].items():
                        lines.append(f"{key}_error_{error_type} {count}")
        return "\n".join(lines)


metrics = MetricsCollector()
