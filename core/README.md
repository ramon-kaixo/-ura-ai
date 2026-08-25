# core/ — LEGACY (frozen)

**Estado:** Congelado. No agregar código nuevo aquí.

Todo el código nuevo va en `motor/` (canonical) o `knowledge/engine/`.

## Servicios productivos que dependen de core/

| Servicio | Archivo | Módulo usado |
|----------|---------|--------------|
| `deploy/model-router.service` | `python3 -m core.model_router` | `core/model_router/` |
| `deploy/systemd-prod/ura-mochila.service` | `uvicorn core.mochila.mochila_server:app` | `core/mochila/` |

Estos servicios seguirán funcionando mientras core/ exista. La migración a motor/
se hará cuando los servicios productivos se actualicen para usar `motor.*` directamente.

## Qué NO hacer

- No añadir features nuevas a core/
- No refactorizar core/ (excepto fixes de seguridad críticos)
- No crear nuevos módulos en core/
- Los imports de motor/→core/ están prohibidos (motor/ es independiente)

## Migración completada (2026-08-25)

- ✅ core/interfaces/ eliminado (6 files) → motor/core/interfaces/
- ✅ core/secretario_cache.py eliminado → motor/ equivalentes
- ✅ core/bin_paths.py eliminado → inlined en monitor/snc.py
- ✅ core/mochila/providers/ eliminado (7 files) → motor/core/llm/
- ✅ 23 shims core→motor eliminados
- ✅ Logging consolidado: knowledge/engine/logging_config + motor/core/json_logger → motor/observability/logging
- ✅ motor/ tiene 0 imports de core/
