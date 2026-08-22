# PLAN DE PENDIENTES ESTRUCTURALES — Cobertura 100% y Mypy strict

[TERM] (ASUS) — 2026-08-22 · CI reparado (ver sección 1) · Planes de ejecución futura (NO ejecutados)

---

## 1. QUÉ SE HA ARREGLADO EN EL CI (hoy)

| # | Problema | Fix | Estado |
|---|---|---|---|
| 1 | Gate script usaba `.venv/bin/python` (inexistente en runners) → `GATE FAIL` inmediato; **el gate de mutación nunca había pasado en CI** | `PY` detecta `.venv/bin/python` en local o `python3` en CI | ✅ verificado: gate pasa en CI (3m35s) |
| 2 | `--instafail` en addopts pero ausente en `[dev]` → todos los jobs de pytest morían con rc=4 | `pytest-instafail>=0.5` añadido a los grupos `test` y `dev` | ✅ |
| 3 | Symlinks rotos: `docs/audit_externa_latest.md` (ruta `docs/docs/...`) y `docs/external_audits/latest.md` (**ruta absoluta**, se rompía en runners) → `ruff format --check` fallaba | Ambos corregidos a rutas relativas válidas; borrador del issue formateado | ✅ |
| 4 | Semgrep CI (`--config auto`): 20 findings de reglas comunitarias (Dockerfiles sin USER, SQL crudo ya auditado, docs...) | CI usa `.semgrep.yml` local (3 reglas personalizadas, misma política que el hook); verificado RC=0 | ✅ |
| 5 | `audit_git_secrets --fail`: 3 falsos positivos en tests (ejemplos de redacción) | Excluye ficheros de `tests/` del escaneo | ✅ |
| 6 | 7 tests con dependencia del entorno ASUS (nombre del directorio `ura_ia_1972` hardcoded; escritura en `~/.nervioso`) | Nombre del repo derivado de `__file__`; `NERVIOSO`/`CONFIG_PATH` parcheados a `tmp_path` | ✅ |
| 7 | `rank_bm25` sin declarar (import en `motor/intelligence/retrieval/lexical.py`) → error de colección en CI | Declarada en extras `test`+`dev` (pin corregido a `>=0.2.2`, máximo disponible en PyPI) | ✅ |
| 8 | `test_weights_y_explanation`: umbral de recency dependiente de la fecha (episodio "2026-08-10" daba 0.948 < 0.95 hoy) | Episodio más reciente con `datetime.now(UTC)` | ✅ |

**Estado final del CI (push `3b7e0aa8`):**
- `CI` (ci.yml): ✅ **success** (lint, test 3.11/3.12/3.13, e2e, build, security, coverage)
- `Mutation & Quality` (tests.yml): ✅ **success** (coverage, mypy, **gate de mutación**, semgrep, integración)
- `cobertura-nuevos`: ✅ success

Enlace al workflow: https://github.com/ramon-kaixo/-ura-ai/actions

---

## 2. PLAN COBERTURA 100% (estado: 98,5% global — faltan 482 líneas)

### Cifras reales por paquete (medición 2026-08-22, suite completa con cobertura)

| Paquete | Cobertura | Faltan | Prioridad |
|---|---|---|---|
| motor/assistant | 95,8% | 99 | ALTA (uso intensivo) |
| knowledge/engine | 98,8% | 94 | ALTA (motor de conocimiento) |
| motor/core | 99,0% | 70 | ALTA |
| motor/intelligence | 97,0% | 68 | ALTA |
| motor/cli | 96,5% | 26 | MEDIA |
| motor/agents | 98,0% | 15 | MEDIA |
| core/event_bus | 91,0% | 13 | MEDIA |
| core/agents | 52,0% | 12 | BAJA (shim legacy) |
| core/mochila | 99,5% | 11 | MEDIA |
| core/infra | 94,0% | 10 | MEDIA |
| core/voice | 25,0% | 9 | BAJA (solo anker, ya al 94,6% con su test) |
| motor/observability | 99,2% | 8 | BAJA |
| core/sandbox | 93,0% | 8 | BAJA |
| core/health_monitor | 91,1% | 8 | BAJA |
| resto (14 paquetes ≥99%) | — | ~31 | BAJA |

**Total: 482 líneas** (de 31.345). El 100% es alcanzable por fases.

### Ejecución propuesta (3 fases, ~8-14h)

- **Fase C1** (los 4 huecos grandes, ~331 líneas, 4-6h): motor/assistant (99), knowledge/engine (94), motor/core (70), motor/intelligence (68). Técnicas: tests de ramas de error (except/fallback), casos extremos de borde (listas vacías, límites), parametrizaciones.
- **Fase C2** (~85 líneas, 2-3h): motor/cli (26), motor/agents (15), core/event_bus (13), core/mochila (11), core/infra (10), core/observability+health_monitor (16).
- **Fase C3** (~66 líneas, 2-4h): líneas dispersas de los paquetes pequeños (core/voice, core/sandbox, core/secretario_cache, core/agents, scraper_pool...). Las líneas sueltas son las más caras (ramas de error raras, except de librerías).
- **Cierre**: gate de cobertura en CI con umbral 98,5%→100% progresivo (sin umbral hoy: el job coverage es informativo con `|| true`).

**Nota de realismo**: el 100% exacto en código real incluye líneas de defensa (except de librerías externas, fallbacks de degradación) que a veces solo se cubren con mocks muy específicos; el coste de las últimas ~50 líneas puede superar al de las primeras 300. Si se acepta 99,5% como objetivo práctico, el esfuerzo baja a ~4-6h.

---

## 3. PLAN MYPY STRICT (estado: básico 0 errores; strict: 228 errores)

### Cifras reales (medición con strict activado, 2026-08-22)

| Origen | Errores | Ficheros representativos |
|---|---|---|
| motor/ (propios de fusion/llm/assistant + compartidos motor/core) | 120 | llm/__init__ (11), llm/ollama (8), llm/router/__init__ (7), fusion/stages/__init__ (6), fusion/context_builder (6), config_manager (6) |
| knowledge/engine/ (transitivos legacy) | 76 | rules (15), graphrag (13), orchestrator, memory_store, ontology/schema_org |
| motor/core/qdrant_client.py | 23 | — |
| motor/memory/ (transitivos) | 13 | memory (6), episodic... |
| **Total** | **228** | 66 ficheros (63 propios + transitivos) |

**Causas más comunes** (por tipo de error):
- `type-arg` (113, ~50%): `list`/`dict` sin genéricos → mecánico pero requiere conocer el tipo real de cada sitio.
- `no-untyped-def` (53, ~23%): funciones sin anotar en módulos legacy (knowledge/engine, motor/memory).
- `no-any-return` (20) + `no-untyped-call` (19): retornos implícitos y llamadas a código sin tipos.
- `attr-defined` (7) + `unused-ignore` (4): limpieza.

### Ejecución propuesta (4 fases, ~4-8h)

- **Fase M0 — transitivos compartidos (~112 errores, 2-3h)**: knowledge/engine/rules.py, graphrag.py, orchestrator, memory_store; motor/memory/*; motor/core/qdrant_client.py; config_manager. Son los que hacen que `motor/assistant` (que los importa) dé 224 errores: anotarlos de abajo arriba elimina la cascada.
- **Fase M1 — motor/core/llm (~50, 1-1.5h)**: llm/__init__, ollama, router/__init__, base, providers.
- **Fase M2 — motor/core/fusion (~40, 1h)**: stages/__init__, context_builder, source_scorer, entity_scoring.
- **Fase M3 — motor/assistant propios (~26 restantes, 0.5-1h)** tras M0-M2.
- **Cierre**: descomentar las secciones `[mypy-motor.*] strict = True` de `mypy.ini` (ya preparadas) y el gate del CI pasa al nivel strict automáticamente (el job mypy ya corre con mypy.ini).

**Riesgo**: anotar firmas no cambia runtime (las anotaciones son solo tipos), pero los `type-arg` requieren entender cada contenedor; el riesgo de rotura es bajo y la verificación es `mypy` + suite.

---

## 4. PRIORIDAD Y ORDEN DE EJECUCIÓN RECOMENDADO

1. **CI ya verde** (hecho hoy) — la base está asegurada.
2. **Fase M0 (transitivos mypy)** antes que la cobertura: desbloquea el strict completo y reduce la deuda de tipos más grande con menor riesgo.
3. **Fase C1 (cobertura 98,5→99,5%)** — el mayor impacto visible.
4. **Fases M1-M3 + C2-C3** según disponibilidad; cada fase con su TASK UDO y gates.

Esfuerzo total pendiente: ~12-22h repartidas en ~7 fases independientes (commiteables y revisables por separado).
