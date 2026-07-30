# P3 Report — Cobertura de Tests (shared/paths.py + motor/assistant/auth.py)

**Fecha:** 2026-07-29
**Commit:** d67fe3c
**Estado:** ✅ Completado

## Resultados

| Módulo | Statements | Miss | Cobertura |
|--------|-----------|------|-----------|
| `shared/paths.py` | 12 | 0 | 100% |
| `motor/assistant/auth.py` | 14 | 0 | 100% |

## Tests Añadidos

### `tests/test_shared_paths.py` (7 tests)
- `test_ura_root_default` — URA_ROOT es Path y existe
- `test_ura_root_from_env` — URA_ROOT se sobreescribe con env var
- `test_all_paths_are_path_objects` — todos los paths son Path
- `test_scripts_is_relative_to_root` — SCRIPTS relativo a URA_ROOT
- `test_scripts_pro_is_relative_to_root` — SCRIPTS_PRO relativo a URA_ROOT
- `test_derived_paths_are_relative` — DEPLOY, DOCS, LOGS, CONFIG, TESTS, NERVIOSO correctos
- `test_ura_root_env_fallback` — fallback a ruta por defecto cuando no hay env var

### `tests/test_auth_middleware.py` (6 tests)
- `test_auth_disabled` — AuthMiddleware pasa cuando auth desactivado
- `test_auth_enabled_no_header` — 401 sin cabecera Authorization
- `test_auth_enabled_wrong_key` — 401 con key incorrecta
- `test_auth_enabled_valid_key` — 200 con key correcta
- `test_non_chat_path_skips_auth` — paths no-chat saltan auth
- `test_auth_no_bearer_prefix` — 401 sin prefijo "Bearer"

## Cobertura Total

Baseline: 19% (sobre motor/, knowledge/, shared/).
Delta: +2 módulos a 100%.

## Pendiente
- `core/model_router.py` aún a 0%
- `motor/assistant/vector_memory.py` a 23%
