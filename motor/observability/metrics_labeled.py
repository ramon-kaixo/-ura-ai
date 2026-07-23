"""Platform-level metrics instrumentation (ADR-028-10).

Wires counters, histograms, and gauges into serializer, validator,
negotiator, and transport. No external Prometheus dependency required;
metrics are accessible via MetricsRegistry.snapshot() for Prometheus
scrape or /metrics endpoint.
"""

from __future__ import annotations

from motor.observability.metrics import (
    Counter as _Counter,
)
from motor.observability.metrics import (
    Gauge as _Gauge,
)
from motor.observability.metrics import (
    Histogram as _Histogram,
)
from motor.observability.metrics import (
    MetricsRegistry,
)


def _default_registry() -> MetricsRegistry:
    return MetricsRegistry()


class LabeledCounter:
    """Counter with dynamic label dimensions.

    Each unique combination of label values produces an independent
    counter instance, keyed by a composite key string.
    """

    def __init__(self, name: str, description: str = "", registry: MetricsRegistry | None = None) -> None:
        self._name = name
        self._description = description
        self._registry = registry or _default_registry()
        self._counters: dict[str, _Counter] = {}

    def inc(self, amount: int = 1, **labels: str) -> None:
        key = _label_key(labels)
        if key not in self._counters:
            self._counters[key] = self._registry.counter(
                f"{self._name}.{key}",
                self._description,
                labels,
            )
        self._counters[key].inc(amount)


class LabeledHistogram:
    """Histogram with dynamic label dimensions."""

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: list[float] | None = None,
        registry: MetricsRegistry | None = None,
    ) -> None:
        self._name = name
        self._description = description
        self._buckets = buckets
        self._registry = registry or _default_registry()
        self._histograms: dict[str, _Histogram] = {}

    def observe(self, value: float, **labels: str) -> None:
        key = _label_key(labels)
        if key not in self._histograms:
            self._histograms[key] = self._registry.histogram(
                f"{self._name}.{key}",
                self._description,
                self._buckets,
            )
        self._histograms[key].observe(value)


class LabeledGauge:
    """Gauge with dynamic label dimensions."""

    def __init__(self, name: str, description: str = "", registry: MetricsRegistry | None = None) -> None:
        self._name = name
        self._description = description
        self._registry = registry or _default_registry()
        self._gauges: dict[str, _Gauge] = {}

    def set(self, value: float, **labels: str) -> None:
        key = _label_key(labels)
        if key not in self._gauges:
            self._gauges[key] = self._registry.gauge(
                f"{self._name}.{key}",
                self._description,
                labels,
            )
        self._gauges[key].set(value)


def _label_key(labels: dict[str, str]) -> str:
    return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))


class PlatformMetrics:
    """Central metrics hub for the protocol layer.

    Provides named methods for every ADR-028-10 metric, wrapping the
    underlying MetricsRegistry with dynamic label support.
    """

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        reg = registry or _default_registry()

        # ── Counters ──────────────────────────────────────
        self.messages_sent = LabeledCounter(
            "platform_messages_sent_total",
            "Total messages sent by each component",
            registry=reg,
        )
        self.messages_received = LabeledCounter(
            "platform_messages_received_total",
            "Total messages received by each component",
            registry=reg,
        )
        self.messages_error = LabeledCounter(
            "platform_messages_error_total",
            "Total message errors, tagged by error code",
            registry=reg,
        )

        # ── Timers (recorded as ms) ───────────────────────
        self.serialization_duration = LabeledHistogram(
            "platform_serialization_duration_ms",
            "Time spent serializing envelopes (ms)",
            registry=reg,
        )
        self.validation_duration = LabeledHistogram(
            "platform_validation_duration_ms",
            "Time spent validating envelopes (ms)",
            registry=reg,
        )
        self.negotiation_duration = LabeledHistogram(
            "platform_negotiation_duration_ms",
            "Distribution of version negotiation latency (ms)",
            registry=reg,
        )

        # ── Gauges ────────────────────────────────────────
        self.envelope_size = LabeledGauge(
            "platform_envelope_size_bytes",
            "Observed envelope size in bytes",
            registry=reg,
        )

        # ── F29 B1: Health metrics ───────────────────────────
        self.health_status = LabeledGauge(
            "ura_health_status",
            "Health status per component (1=ok, 0=degraded)",
            registry=reg,
        )
        self.health_ready = LabeledGauge(
            "ura_health_ready",
            "Readiness per component (1=ready, 0=not ready)",
            registry=reg,
        )

    # ── F29 B1: Record health status from HealthAggregator ──

    def record_health(self, component: str, status: str, ready: bool) -> None:
        self.health_status.set(1.0 if status == "ok" else 0.0, component=component)
        self.health_ready.set(1.0 if ready else 0.0, component=component)

    # ── Convenience wiring methods ────────────────────────

    def record_sent(
        self,
        source: str,
        destination: str,
        message_kind: str,
        size_bytes: int,
        duration_ms: float,
    ) -> None:
        self.messages_sent.inc(source=source, destination=destination, message_kind=message_kind)
        self.serialization_duration.observe(duration_ms, source=source, message_kind=message_kind)
        self.envelope_size.set(float(size_bytes), source=source, message_kind=message_kind)

    def record_received(
        self,
        source: str,
        destination: str,
        message_kind: str,
        size_bytes: int,
    ) -> None:
        self.messages_received.inc(source=source, destination=destination, message_kind=message_kind)
        self.envelope_size.set(float(size_bytes), source=source, message_kind=message_kind)

    def record_error(
        self,
        source: str,
        destination: str,
        error_code: str,
    ) -> None:
        self.messages_error.inc(source=source, destination=destination, error_code=error_code)

    def record_validation(
        self,
        source: str,
        duration_ms: float,
    ) -> None:
        self.validation_duration.observe(duration_ms, source=source)

    def record_negotiation(
        self,
        duration_ms: float,
    ) -> None:
        self.negotiation_duration.observe(duration_ms)


# Singleton for easy import (no global state — instantiated per-registry).
_default_metrics = PlatformMetrics()


def get_platform_metrics() -> PlatformMetrics:
    """Return the default PlatformMetrics instance."""
    return _default_metrics
