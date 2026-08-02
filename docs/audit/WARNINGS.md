# Warnings de la Suite — Estado

## Resumen
- Total warnings en suite normal: 4
- RuntimeWarning: 2 (AsyncMock)
- DeprecationWarning: 2 (StructuredLogger + ast.Str)
- UserWarning: 1 (Duplicate Operation ID)
- StarletteDeprecationWarning: 1 (httpx + testclient)

## Warnings que CAUSAN FALLO con pytest -W error

| # | Warning | Archivo | Causa | Accion |
|---|---------|---------|-------|--------|
| 1 | DeprecationWarning: StructuredLogger is deprecated | core/json_logger.py:24 | StructuredLogger deprecado, usar ComponentLogger | Refactorizar json_logger.py |
| 2 | DeprecationWarning: ast.Str is deprecated, use ast.Constant | test_plugin.py::test_from_source_with_list | ast.Str removido en Python 3.14 | Reemplazar por ast.Constant |

## Warnings informativos (no bloquean)

| # | Warning | Archivo | Causa | Accion |
|---|---------|---------|-------|--------|
| 3 | RuntimeWarning: AsyncMock coroutine never awaited | test_rules_hypothesis.py, test_integration_scheduler.py | AsyncMock en codigo sincrono | Reemplazar por MagicMock |
| 4 | RuntimeWarning: AsyncMockMixin coroutine never awaited | test_qdrant_client.py::test_disponible_false | AsyncMock usado incorrectamente | Revisar mock |
| 5 | StarletteDeprecationWarning: httpx + testclient | fastapi/testclient.py:1 | Version fija de FastAPI | Upgrade o aceptar |
| 6 | UserWarning: Duplicate Operation ID | mochila_server.py via openapi/utils.py:252 | Dos rutas mismo operation_id | Renombrar operation_id |

## Notas
- Los 2 DeprecationWarning bloquean pytest -W error (G6).
- Los RuntimeWarning son deuda tecnica de tests.
- StarletteDeprecationWarning depende de version FastAPI en requirements.

## Warnings de Flaky Tests (agosto 2026)

| Test | Causa | Estado |
|------|-------|--------|
| test_100_exitos | Estado compartido _get_success_rate | ✅ Arreglado (try/finally) |
| test_ensure_publisher_async | Estado compartido event_bus | ✅ Marcado @slow |
| test_api.py (8 tests) | Requieren servidor FastAPI | ✅ Marcado @slow |
| test_core_rollback_app.py | Contaminación cruzada con pytest-randomly | 🔄 Pendiente |
| test_mochila_infra.py (3 tests) | Flaky con cobertura | ✅ Marcado @slow |

**Nota:** pytest-randomly ejecuta tests en orden aleatorio. Tests que mutan estado global (monkeypatch, sys.path, singletons) fallan cuando otro test los contamina. Solución a largo plazo: aislar estado con fixtures de pytest o desactivar randomly en CI.
