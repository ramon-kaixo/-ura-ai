# Tests N2 — Guía

## Ejecutar

```bash
source .venv/bin/activate
pytest tests/test_n2_*.py -v
```

## Cobertura actual (Fase 1)

| Archivo | Tests | Qué cubre |
|---|---|---|
| `tests/test_n2_search_cache.py` | 7 | fingerprint, put/get, TTL, cleanup, stats, concurrencia |
| `tests/test_n2_maleta_manager.py` | 10 | validación schema, CRUD, confianza, clonado, similarity |
| `tests/test_n2_validador.py` | 6 | quality_score, contradicciones, consolidación, validate_swarm_output |
| `tests/test_n2_swarm.py` | 5 | split, run básico, cache hit, gestión de errores |
| **TOTAL** | **28** | |

## Convenciones

- **pytest-asyncio** para tests async. Se marca explícitamente con `@pytest.mark.asyncio`
  o con `pytestmark = pytest.mark.asyncio` a nivel de módulo (**solo si todos los tests son async**).
- **tmp_path fixture** para DBs y directorios aislados (nunca tocan `~/.ura`).
- **monkeypatch** para sustituir `validate_urls` (evita red real en tests).
- **Fake agents** en `tests/test_n2_swarm.py` — no golpean internet.

## Pendientes (Fase 2+)

- Tests de `ura_ddg_client.py` con `aioresponses` o `respx` (HTTP mocking).
- Tests de `ura_stealth_browser.py` con Playwright en modo recording (requiere browser).
- Tests de integración end-to-end con SearXNG local (cuando se añada en Fase 2).
- Tests de carga: 100 swarms simultáneos para verificar semáforos.

## Excluir tests lentos en CI

```bash
pytest tests/test_n2_*.py -m "not slow" -v
```
