# URA v0.32.0 Release Notes
## 2026-07-23

### Fixed
- F821 undefined names (3 bugs) → 0
- ruff auto-fixes: 66 → 27 → 0 bugs

### Added
- docs/DATABASE.md: 5 SQLite databases documented with schema
- docs/sql/knowledge_db_schema.sql: complete schema (108 lines)
- Module-database mapping
- motor/tests/tuneladora/: 11 tests, 11/11 passed
  - test_engine_init.py (4 tests)
  - test_plugin_code_quality.py (2 tests)
  - test_plugin_health.py (2 tests)
  - test_plugin_cleanup.py (2 tests)
  - test_plugin_reporting.py (1 test)

### Known Issues
- 24 ruff style debt documented (PLR0915, PTH, SIM105/115)
- 4 vulture in fusion/engine.py (public API, ADR-003)
- Docker RO filesystem (documented workaround)
