# Warnings de la Suite — Estado

## Resumen
- Total warnings en suite normal: 4
- RuntimeWarning: 2 (AsyncMock)
- DeprecationWarning: 1-2 (Starlette + posible nuevo)

## Warnings documentados

| # | Warning | Archivo(s) | Causa | Acción | Estado |
|---|---------|-----------|-------|--------|--------|
| 1 | RuntimeWarning: coroutine 'AsyncMock._get_child_mock' was never awaited | test_rules_hypothesis.py, test_integration_scheduler.py | AsyncMock usado en código síncrono | Reemplazar por MagicMock o asegurar await | Pendiente |
| 2 | DeprecationWarning: starlette.testclient | test_http_client.py (estimado) | httpx + starlette.testclient en versión fija de FastAPI | Upgrade de FastAPI o aceptar warning | Documentado, no bloqueante |
| 3 | DeprecationWarning: [PENDIENTE — ver output de -W error] | [PENDIENTE] | [PENDIENTE] | [PENDIENTE] | Investigando |

## Notas
- Los warnings de AsyncMock no afectan funcionalidad, pero ensucian la salida de CI.
- El warning de Starlette depende de la versión de FastAPI bloqueada en requirements.
- Nuevo warning detectado en suite completa (investigar con `pytest -W error`).
