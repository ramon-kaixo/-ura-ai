# URA v0.30.0 Release Notes
## 2026-07-23

### Fixed
- Remote repository frozen since v3.5.1 → now synchronized
- 200+ local-only tags → pushed to GitHub
- motor/platform/ 15 dead files eliminated, 3 preserved, 4 migrated to observability/
- 5 except:pass fixed with proper logging
- LatencyStats missing methods (record, compute_percentiles, to_dict, count, errors)
- LabeledCounter collect() and LabeledHistogram _histograms fallback

### Added
- F3 Observability: HealthRegistry, correlation_id, LabeledCounter/Histogram, TraceContext spans
- /health and /metrics endpoints in assistant
- JSONFormatter in assistant logging
- CI workflow (.github/workflows/ci.yml)
- Docker + docker-compose + deploy docs
- systemd service (ura.service)
- Environment-based config (no hardcoded IPs)
- ADR-001, ADR-002, VERSIONING.md, SECURITY_AUDIT.md

### Known Issues
- 51 pre-existing lint errors in plugin/ and tests/
- 4 vulture findings in fusion/engine.py (public API)
- 16 pre-existing mypy errors in plugin/
- Docker build requires writable filesystem (not available on GX10)
