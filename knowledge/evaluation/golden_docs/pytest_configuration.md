# Pytest Configuration for URA

URA uses pytest 9.0.3 with specific configuration.

## Running Tests

Run all tests: `pytest -q --tb=line`
With coverage: `pytest --cov=motor.core.state --cov=motor.plugin`

## Excluded Tests

Some tests are excluded from the default run:
- test_unit.py: triggers sys.exit(78) from model_router import
- test_openclaw.py: syntax error in except block
- test_vram_guard.py: imports model_router
- test_sda.py: imports guardian_logger.py (syntax error)
- test_snc_anomalias.py: missing scanner dependency

## Dependencies

- pytest 9.0.3
- pytest-asyncio 1.4.0
- pytest-timeout
- hypothesis 6.153.2
