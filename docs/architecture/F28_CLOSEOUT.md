# Fase 28 — Platform Protocols — Closeout

## Summary
- **Date:** 2026-07-20
- **Tag:** `v0.28.3-stable`
- **Commit:** `715b19f`
- **Status:** Stable

## Delivered (F28 + F28.1)
- ProtocolEnvelope con 5 headers: Version, Routing, Trace, Delivery, Security
- JSON canonical serializer/deserializer + ProtocolValidator
- VersionNegotiator por MessageKind + CompatibilityChecker
- ProtocolRegistry + Transport ABC + LocalTransport
- ErrorEnvelope con trace_id + causation_id
- Observabilidad: TraceId/SpanId/parent_span_id, TraceExporter, HealthAggregator, MetricsCollector, Sampler (5 estrategias)
- RateLimiter (token bucket, thread-safe)
- Payload sanitization (8 patrones bloqueados)
- Structured JSON logging (`motor/platform/logging.py`)

## Quality
- Tests: 67 protocol + 488 tests total en F25-F28+OBS, 0 regresiones
- Ruff: 0 errores nuevos
- F28.1: P1+P2+P3 estabilizados

## Known Gaps
- ADR-028 en estado Draft (no Approved)
- Race condition conocida en LocalTransport
- Checksum pipeline nunca verificado en runtime
- 3 tests flaky de tracing

## Exit Criteria
| Criterio | Estado |
|----------|--------|
| Compilación | ✅ |
| Ruff 0 nuevos | ✅ |
| Tests sin regresión | ✅ |
| Tag creado | ✅ |
| Documentación actualizada | ✅ |

## Files
- `motor/platform/` — Protocolo, tracing, observabilidad
- `motor/memory/` — Memoria histórica (F26)
