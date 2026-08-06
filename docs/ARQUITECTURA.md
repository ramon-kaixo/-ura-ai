# Arquitectura URA — Referencia v4.0

**Fecha:** 2026-08-06
**Fase:** 8 del Plan v4.0 (`docs/ARQUITECTURA_v4.0_PLAN.md`)
**Estado:** Referencia consolidada — VERIFICADA (auditorías read-only 2026-08-06)

---

## Visión general

URA es un asistente multi-agente con: core de dominio, motor extensible, agentes
especializados, consciencia/coordinación, memoria de conocimiento y un swarm de
investigación autónomo. Codificado en Python 3, enfocado a GX10 (GB10, 128GB RAM).

## Estructura de capas

| Capa | Ruta | Rol |
|---|---|---|
| **Núcleo (dominio)** | `core/` | Lógica de dominio: consciencia, valores, escriba forense, rollback, mochila, memoria, debate, multi-agente |
| **Motor (plataforma)** | `motor/` | Motor extensible: config única (`motor/core/config.py`), memoria, agentes, intramedia, platform protocols, CLI |
| **Agentes** | `agents/` | Agentes especializados (organizados por dominio/subdirectorios) |
| **Conocimiento** | `knowledge/` | Memoria a largo plazo, fragmentos de documentos, base de conocimiento, engine (F0-7), FTS5 |
| **Scripts pipeline** | `scripts/pro/` | Tuneladora (mejora continua), herramientas, servicios (~146 archivos el índice viejo; ~120 verificados v4) |
| **Deploy** | `deploy/` | Unidades systemd, timers |
| **Docs** | `docs/` | Arquitectura, planes, closeouts, diagnósticos |

## Componentes canónicos verificados (A la fecha 2026-08-06)

Ver `docs/MODULOS_CANONICOS.md` para la lista completa con etiquetas.

| Componente | Estado | Nota |
|---|---|---|
| `core/mochila/*` (:4098) | 🔵 VIVO PROD | No tocar; servidor activo |
| `core/memoria/*` | 🔵 VIVO PROD | Usado por mochila |
| `motor/core/llm/*` | 🟢 CANÓNICO | Fuente de verdad config/LLM |
| `motor/memory/*` | 🟢 CANÓNICO v2 | Fase 26 |
| `motor/intelligence/memory/*` | 🟢 CANÓNICO v2 | Fase 12 |
| `scripts/pro/tuneladora/*` | 🟢 CANÓNICO | Motor pipeline (Makefile+tests) |
| `core/model_router/` | 🟡 TRANSICIÓN | 0 consumidores vivos; ver `docs/ROUTERS.md` |

## Pipelines

| Pipeline | Ubicación | Estado |
|---|---|---|
| Mejora continua | `scripts/pro/tuneladora_mejora.py` | 🟢 |
| Mantenimiento | `scripts/pro/tuneladora_mantenimiento.py` | 🟢 (refs degradadas, F6.2) |
| Refactorización | `scripts/pro/pipeline_refactor.py` | 🟢 sano |
| Supremo (red) | `scripts/pro/pipeline_supremo.py` | 🟡 7 pasos degradados |
| Motor ejecutable | `/usr/local/bin/ura-motor pipeline` | 🟢 (ura-pipeline.timer) |

Ver `docs/PIPELINE.md`.

## Memoria (3 vías coexistentes)

Ver `docs/MEMORIA.md` — core/memoria (v1 prod), motor/intelligence/memory (v12),
motor/memory (v26). Unificación v1→v2 = v4.0e (Ramón).

## Routers (triplicación)

Ver `docs/ROUTERS.md` — v1 mochila PROD, v2 motor, core/model_router repo (transición).

## Servicios systemd (LIVE)

Ver `docs/SERVICIOS.md` + `docs/SYSTEMD_V4.0.md` — 5 failed documentados, secretos en
opencode.service pendientes de saneo.

## Historial de fases relevantes

- V0.x-…: Fases 1-29 cerradas (ver AGENTS.md).
- v4.0: saneamiento arquitectónico con documentación verificada (este plan) — en curso.

## Métricas baseline (referencia)

- Tests: 1381 (make validate) — pre-commit ejecuta unit/motor/core/monitor.
- Ruff: 0 errores (make lint).
- Pydeps: `docs/arch_core_deps.json` (160 nodos/570 rel), `docs/arch_motor_deps.json` (303/1297).
- Cobertura core/: 51.1% (PM v3.1).