# F29 B7 — Gobernanza

## Component Ownership

| Component | Owner | Source of Truth |
|-----------|-------|-----------------|
| F26 Memory | `motor/memory/` | ADR-026-01..04 |
| F27 Agents | `motor/agents/` | ADR-027-01, ADR-027-02 |
| F28 Protocol | `motor/platform/` | ADR-028-01..10 |
| F24 WebFetch | `knowledge/engine/fetcher/` | ADR-024 |
| F25 Fusion | `motor/fusion/` | ADR-025 |
| Observability | `motor/platform/` | ADR-029-01 |

## Runbooks

| Situación | Runbook | Ubicación |
|-----------|---------|-----------|
| Graceful shutdown | B4 Runbook | `docs/architecture/F29_B4_RUNBOOK.md` |
| Backup/Restore | backup_f26_memory.py | `scripts/pro/backup_f26_memory.py` |
| Chaos tests | chaos_f29_b5.py | `scripts/pro/chaos_f29_b5.py` |
| Benchmarks | benchmark_f29_b2.py | `scripts/pro/benchmark_f29_b2.py` |

## SLOs (Target)

| Component | SLO | Medición |
|-----------|-----|----------|
| F26 Memory append | p99 < 1ms | PlatformMetrics |
| F27 Scheduler submit | p99 < 100ms | PlatformMetrics |
| F28 Serialize | p99 < 5ms | PlatformMetrics |
| F28 Deserialize | p99 < 10ms | PlatformMetrics |
| System uptime | 99.5% | HealthAggregator |

## Release Checklist
1. ✅ All tests pass: `pytest -q`
2. ✅ Benchmarks: 0 regresiones vs baseline
3. ✅ Chaos tests: todos verdes
4. ✅ ADRs: todos Approved
5. ✅ Working tree clean
6. Tag `v0.29.0-fase29`
