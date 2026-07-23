# URA Architecture Decisions

## ADR-001: Platform/ elimination (2026-07-23)
- Decision: Migrate observability to observability/, eliminate dead code
- Rationale: 15/21 files had 0 consumers, F28 not documented
- Impact: 3 files preserved (resilience, models, serializer)

## ADR-002: F3 Observability (2026-07-23)
- Decision: HealthRegistry, correlation_id, LabeledCounter, TraceContext in assistant
- Rationale: 0% observability before, now instrumented
