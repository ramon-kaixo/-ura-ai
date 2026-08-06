# ROUTERS — Triplicación de Model Routers (Fase 5 v4.0)

**Fecha:** 2026-08-06
**Fase:** 5 del Plan v4.0 (`docs/ARQUITECTURA_v4.0_PLAN.md`)
**Estado:** Documento de veredicto — CÓDIGO VERIFICADO contra producción

## Veredicto F5

| # | Router | Ubicación | Estado real | Veredicto |
|---|---|---|---|---|
| 1 | **v1 Model Router (Mochila)** | `core/mochila/router.py` + `core/mochila/_state.py` | 🟢 **VIVO en PRODUCCIÓN** — `mochila_server.py` lo importa; la aud tarjeta `ura-mochila.service` ACTIVA (:4098) lo carga | **CONSERVAR** (producción) |
| 2 | **v2 Model Router (Motor)** | `motor/core/llm/router/` (`__init__.py`, `strategy.py`, `providers.py`, `capability.py`, `health.py`) | 🟢 **VIVO** — importado por `core/mochila/_state.py`, `core/agents/telemetry.py`, `core/agents/reparador.py`, `core/memory_engine.py`, `core/debate/debate_engine.py` + tests motor | **CONSERVAR** (v2 canónico de motor) |
| 3 | **core/model_router/ (paquete repo)** | `core/model_router/` (11 módulos: `proxy.py`, `handler.py`, `router.py`, `cache.py`, `cli.py`, `dashboard.py`, `metrics.py`, `model_selection.py`, `vram_guard.py`, `__main__.py`, `__init__.py`) | 🟡 **TRANSICIÓN** — 6 tests unitarios pasan (`tests/unit/test_model_router_*`), pero **0 consumidores vivos**: solo `motor/cli/cmd_ura.py` lo referencía y es vía `core/model_router_main.py` que **NO EXISTE** (ni en repo ni .attic — no encontrado con `find`). Servicios `model-router.service` (sistema y user) **inactive** | **DEGRADACION DOCUMENTADA**: dado el 0-refs de invocador vivo, candidato a archivar en F6.2 con decisión Ramón |

## Detalle de invocadores verificados (2026-08-06)

### 1. v1 Mochila (`core/mochila/router.py`)
- `core/mochila/mochila_server.py` lo importa → **servidor PROD :4098**
- `core/mochila/_state.py` lo referencia (estado de dependencia)
- También importa `motor.core.llm.router` (puente v1→v2 ya existe)

### 2. v2 Motor (`motor/core/llm/router/`)
Consumidores VIVOS verificados:
- `core/mochila/_state.py`
- `core/agents/telemetry.py`
- `core/agents/reparador.py`
- `core/memory_engine.py`
- `core/debate/debate_engine.py`
- `motor/core/llm/router/providers.py`, `strategy.py` (internos)
- Tests: `motor/tests/test_profiler.py`, `test_monitor.py`, `test_anthropic.py` (rendering más amplio)

### 3. `core/model_router/` (paquete repo)
- Sin importadores NO-test NO-self: el único externo es `motor/cli/cmd_ura.py` que usa
  `core/model_router_main.py` (NO EXISTE — es el wrapper que se eliminó en Fase 1 o purgas;
  `find .attic` no lo encuentra → el package está sin entrada).
- 6 tests: `test_model_router_cache/cli/metrics/proxy/router/selection` → todos consumen el paquete.
- Servicio real: `model-router.service` INACTIVE (system + user) → NO está en producción.
- AGENTS.md describe "Model Router Enhanced v2.0" en `/home/ramon/URA/core/model_router.py`
  (FUERA del repo), consistente → el despliegue real vive fuera del repo.

## Conclusión F5

1. **Triplicación CONFIRMADA** y documentada (3 routers: v1 prod, v2 motor, repo legacy).
2. `core/model_router/` paquete repo: **transición** — tests pasan pero sin invocador vivo. El
   único camino de entrada (`core/model_router_main.py`) está roto/n existe.
3. **NO se archiva en F5**: la decisión de archivar `core/model_router/` (11 módulos con tests)
   requiere confirmación de Ramón (F6.2) — por protocolo si un cambio toca `core/` se necesita
   segunda revisión (ADR-007: "mandatory second-party review" para modificaciones de core).
4. Documentar en AGENTS.md: `model-router` service real = INACTIVE (contradice "activo :11435").

## Pendientes F5 (para Fase 7 / AGENTS.md)

- [ ] AGENTS.md: corregir sección "Model Router Enhanced v2.0" — servicio user NO activo.
- [ ] Decisión Ramón (F6.2): archivar vs reconstruir `core/model_router_main.py` stub.
- [ ] Limpiar `motor/cli/cmd_ura.py` refs a `core/model_router_main.py` (rota de origen).