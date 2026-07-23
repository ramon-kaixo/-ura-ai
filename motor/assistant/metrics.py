"""Metrics for the assistant module.

Labeled counters and histograms for observability (F3).
"""

from motor.observability.metrics_labeled import LabeledCounter, LabeledHistogram

requests_total = LabeledCounter("assistant_requests_total", "Total requests by mode and status")
request_latency = LabeledHistogram(
    "assistant_request_latency_seconds", "Request latency by mode", buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)
tokens_total = LabeledCounter("assistant_tokens_total", "Tokens generated per provider")
errors_total = LabeledCounter("assistant_errors_total", "Total errors by type and component")

def check_latency_alert(threshold: float = 5.0) -> list[str]:
    """Retorna alertas si alguna metrica de latencia supera el umbral."""
    import logging
    log = logging.getLogger("ura.metrics")
    alerts: list[str] = []
    for key, hist in request_latency._histograms.items():
        snap = hist.snapshot()
        count = snap.get("count", 0)
        suma = snap.get("sum", 0)
        if count > 0:
            avg = suma / count
            if avg > threshold:
                msg = f"LATENCY ALERT: {key} avg={avg:.2f}s > {threshold}s"
                log.warning(msg)
                alerts.append(msg)
    return alerts

def check_error_alert(threshold: float = 0.01) -> list[str]:
    """Retorna alertas si error rate > threshold."""
    import logging
    log = logging.getLogger("ura.metrics")
    total = 0
    for c in requests_total._counters.values():
        total += c.snapshot()["value"]
    errors = 0
    for c in errors_total._counters.values():
        errors += c.snapshot()["value"]
    alerts: list[str] = []
    if total > 0:
        rate = errors / total
        if rate > threshold:
            msg = f"ERROR RATE ALERT: {errors}/{total} ({rate:.2%}) > {threshold:.2%}"
            log.error(msg)
            alerts.append(msg)
    return alerts
