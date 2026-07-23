"""Exporta métricas de URA en formato Prometheus text."""

import time

from motor.assistant.metrics import errors_total, request_latency, requests_total, tokens_total


def _counter_value(counter, **labels) -> int:
    key = "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
    if key in counter._counters:
        return counter._counters[key].snapshot()["value"]
    for key, c in counter._counters.items():
        if all(f"{k}={v}" in key for k, v in labels.items()):
            return c.snapshot()["value"]
    return 0


def _counter_lines(counter, name: str, description: str) -> list[str]:
    lines = [f"# HELP {name} {description}", f"# TYPE {name} counter"]
    for key, c in counter._counters.items():
        labels = c.snapshot().get("labels", {})
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            lines.append(f"{name}{{{label_str}}} {c.snapshot()['value']}")
        else:
            lines.append(f"{name} {c.snapshot()['value']}")
    return lines


def _histogram_lines(hist, name: str, description: str) -> list[str]:
    lines = [f"# HELP {name} {description}", f"# TYPE {name} histogram"]
    for key, h in hist._histograms.items():
        snap = h.snapshot()
        labels = snap.get("labels", {})
        label_str = ",".join(f'{k}="{v}"' for k, v in labels.items()) if labels else ""
        prefix = f"{name}{{{label_str},}}" if label_str else name
        lines.append(f"{prefix}_count {snap['count']}")
        lines.append(f"{prefix}_sum {snap.get('sum', 0)}")
    return lines


def export_metrics() -> str:
    lines: list[str] = []
    lines.append(f"# URA metrics generated at {time.time():.0f}")
    lines.extend(_counter_lines(requests_total, "ura_requests_total", "Total requests by mode and status"))
    lines.extend(_histogram_lines(request_latency, "ura_request_latency_seconds", "Request latency by mode"))
    lines.extend(_counter_lines(tokens_total, "ura_tokens_total", "Tokens generated per provider"))
    lines.extend(_counter_lines(errors_total, "ura_errors_total", "Total errors by type and component"))
    return "\n".join(lines) + "\n"
