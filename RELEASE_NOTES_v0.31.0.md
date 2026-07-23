# URA v0.31.0 Release Notes
## 2026-07-23

### Added
- Tuneladora: PipelineEngine with 5 plugins, checkpoint, ledger, snapshot
- Assistant API split: routes.py, handlers.py, middleware.py (539→448 lines)
- LLM Router split: strategy.py, health.py, providers.py, capability.py, utils.py (535→480 lines)
- aiohttp in dev dependencies

### Fixed
- 22 mypy errors in motor/plugin/ → 0
- 8 ruff errors in tests/ → 0
- log.warn() deprecated → log.warning() in engine.py
- _persist_health() except:pass → logging
- tuneladora_mejora.py main() complexity 16→5
- json.loads without JSONDecodeError → validated
- 115 obsolete tags eliminated
- Health init eager (not lazy)
- Docker RO filesystem documented

### Known Issues
- 66 pre-existing ruff errors in motor/ (not caused by v0.31.0)
- 4 vulture findings in fusion/engine.py (public API, ADR-003)
