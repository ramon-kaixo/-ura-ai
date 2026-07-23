"""Exporta metricas de URA en formato Prometheus text.

NOTA: Accede a ._histograms y ._counters (atributos privados de
LabeledCounter/LabeledHistogram). Esto es intencional para el exportador.
Si LabeledCounter cambia su implementacion interna, este modulo fallara.
"""

from motor.assistant.metrics import errors_total, request_latency, requests_total, tokens_total


def _counter_lines(counter, name: str, desc: str) -> list[str]:
    lines = [f"# HELP {name} {desc}", f"# TYPE {name} counter"]
    for c in counter._counters.values():
        snap = c.snapshot()
        labels = snap.get("labels", {})
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            lines.append(f"{name}{{{label_str}}} {snap['value']}")
        else:
            lines.append(f"{name} {snap['value']}")
    return lines


def _histogram_lines(hist, name: str, desc: str) -> list[str]:
    lines = [f"# HELP {name} {desc}", f"# TYPE {name} histogram"]
    for h in hist._histograms.values():
        snap = h.snapshot()
        labels = snap.get("labels", {})
        label_str = ",".join(f'{k}="{v}"' for k, v in labels.items()) if labels else ""
        prefix = f"{name}{{{label_str},}}" if label_str else name
        lines.append(f"{prefix}_count {snap['count']}")
        lines.append(f"{prefix}_sum {snap.get('sum', 0)}")
    return lines


def export_metrics() -> str:
    lines: list[str] = []
    lines.append("# URA metrics")
    lines.extend(_counter_lines(requests_total, "ura_requests_total", "Total requests by mode and status"))
    lines.extend(_histogram_lines(request_latency, "ura_request_latency_seconds", "Request latency by mode"))
    lines.extend(_counter_lines(tokens_total, "ura_tokens_total", "Tokens generated per provider"))
    lines.extend(_counter_lines(errors_total, "ura_errors_total", "Total errors by type and component"))
    return "\n".join(lines) + "\n"
