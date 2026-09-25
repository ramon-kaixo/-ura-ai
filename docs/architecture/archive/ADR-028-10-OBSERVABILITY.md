# ADR-028-10: Platform Observability

**Status:** Approved  
**Phase:** F28-B3  
**Approved:** 2026-07-19  
**Verification:** PlatformMetrics in `motor/platform/metrics.py` implements all 10 metric types (4 counters, 3 histograms, 3 gauges) with dynamic labels. Wired into LocalTransport, ProtocolValidator, VersionNegotiator. Health metrics + ComponentLogger + health probes for OB01-OB08 compliance. Prometheus client optional — noop fallback via MetricsRegistry. 138 tests passing.  

---

## Problem

No metrics, no dashboards, no SLOs. Logging is ad-hoc (print + logging).
Alerting requires manual observation.

## Decision

### Metrics

Every Platform Protocol component exposes counters:

```python
# Counter names (Prometheus format):
platform_messages_sent_total{source, destination, message_kind}
platform_messages_received_total{source, destination, message_kind}
platform_messages_error_total{source, destination, error_code}
platform_serialization_duration_ms{source, message_kind}
platform_validation_duration_ms{source}

# Gauges:
platform_envelope_size_bytes{source, message_kind}
platform_registry_protocols_count
platform_registry_message_types_count

# Histograms:
platform_negotiation_duration_ms
```

### Logging

- Structured JSON logging (one line per event)
- Fields: `timestamp`, `level`, `service`, `message_id`, `correlation_id`, `message`
- Log levels: DEBUG, INFO, WARN, ERROR, FATAL

### Dashboards

- "Platform Health": message throughput, error rates, latency
- "Protocol Versions": distribution of protocol_version in use
- "Component Map": connectivity graph between services

### SLOs

| SLO | Target | Window |
|-----|--------|--------|
| Message delivery success rate | >99.9% | 30d |
| Serialization p99 latency | <10ms | 30d |
| Validation p99 latency | <1ms | 30d |
| Version negotiation success | >99.99% | 30d |

### Implementation

- Use `motor/observability/` module (already exists with MetricsRegistry)
- Wire counters into: serializer, validator, negotiator, transport
- No external dependencies (Prometheus client library is optional)
