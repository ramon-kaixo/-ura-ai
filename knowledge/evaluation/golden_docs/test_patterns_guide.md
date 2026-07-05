# URA Test Patterns Guide

Tests in URA follow specific patterns for different components.

## Component Tests

- EventBus: tests/test_event_bus_f11.py — publish, subscribe, pattern, async
- PluginRegistry: tests/test_registry_v2.py — discover, load, dependencies
- Pipeline: tests/test_pipeline_mvp.py — execution, rollback, hooks
- Observability: tests/test_observability_f11.py — metrics, health, readiness

## Test Conventions

- Use `tmp_path` fixture for temporary files
- Use `pytest.mark.asyncio` for async tests
- No `skip`, `xfail`, or disabled tests
- Private member access in tests: add `# ruff: noqa: SLF001` at file level
- Test file naming: test_<component>.py
