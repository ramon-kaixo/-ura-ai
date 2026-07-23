# URA v0.33.0 Release Notes
## 2026-07-23

### Added
- G1: Prometheus metrics exporter + /metrics endpoint + Grafana dashboard
- G2: E2E tests (9 tests) + CI job
- G3: Auto-cleanup logs, SQLite vacuum, orphaned embeddings
- G4: Alerts for health, latency, errors, disk
- G5: Detect duplicates + tech debt report + CI

### Fixed
- v0.32.0 bugs: F821, ruff debt documented

### Infrastructure
- CI: tests, lint, E2E, debt report
- Monitoring: Prometheus + Grafana
- Maintenance: auto-cleanup weekly
- Alerts: health, latency, errors, disk

### Known Issues
- 23 ruff style debt (documented)
- 4 vulture fusion/engine.py (ADR-003)
