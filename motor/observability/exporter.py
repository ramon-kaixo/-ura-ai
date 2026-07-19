"""OpenMetrics export — serializa métricas a formato Prometheus text/plain."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.observability.metrics import MetricsRegistry


def format_prometheus(registry: MetricsRegistry) -> str:
    lines: list[str] = []
    snapshot = registry.snapshot()

    for counter in snapshot.get("counters", []):
        name = _sanitize(counter["name"])
        help_text = counter.get("description", "")
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} counter")
        labels = _format_labels(counter.get("labels", {}))
        lines.append(f"{name}{labels} {counter['value']}")

    for gauge in snapshot.get("gauges", []):
        name = _sanitize(gauge["name"])
        help_text = gauge.get("description", "")
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        labels = _format_labels(gauge.get("labels", {}))
        lines.append(f"{name}{labels} {gauge['value']}")

    for hist in snapshot.get("histograms", []):
        name = _sanitize(hist["name"])
        help_text = hist.get("description", "")
        if help_text:
            lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} histogram")
        lines.append(f"{name}_count {hist['count']}")
        lines.append(f"{name}_sum {hist['sum']}")
        for bucket, count in hist.get("buckets", {}).items():
            lines.append(f'{name}_bucket{{le="{bucket}"}} {count}')

    for timer in snapshot.get("timers", []):
        name = _sanitize(timer["name"])
        lines.append(f"# HELP {name} {timer.get('description', '')}")
        lines.append(f"# TYPE {name} histogram")
        lines.append(f"{name}_count {timer['count']}")
        lines.append(f"{name}_sum {timer['sum']}")
        for bucket, count in timer.get("buckets", {}).items():
            lines.append(f'{name}_bucket{{le="{bucket}"}} {count}')

    return "\n".join(lines) + "\n"


def _sanitize(name: str) -> str:
    return name.replace("-", "_").replace(" ", "_").replace(".", "_")


def _format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
    return "{" + ",".join(parts) + "}"
