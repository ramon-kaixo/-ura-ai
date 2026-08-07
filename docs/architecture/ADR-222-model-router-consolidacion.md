# ADR-222: Consolidación de Model Router (v1 `core/model_router` → v2 `motor/core/llm/router`)

> **Estado:** 📝 Propuesta (requiere revisión Ramón)
> **Fecha:** 2026-08-07
> **Fase:** F7 — Siguiente pasos (post-cierre)
> **Aplica a:** `core/model_router/` (v1), `motor/core/llm/router/` (v2)
> **Regla núcleo:** ADR-007 — modificación a `motor/core` prohibida sin esta revisión + segunda parte

---

## 1. Contexto

Existen **dos routers LLM** en el código base:

| Vía | Ubicación | Qué hace | Estado producción |
|---|---|---|---|
| v1 | `core/model_router/` (11 módulos: cache, cli, dashboard, handler, metrics, model_selection, proxy, router, vram_guard) | Proxy HTTP :11435, prompt caching 2h TTL, metrics, dashboard, CLI, VRAM guard, selección por ruta | 🟢 **VIVO** — `model-router.service` (`ExecStart=python3 core/model_router.py`) |
| v2 | `motor/core/llm/router/` (capability, health, providers, strategy, utils) + `LLMRouter` | Selección provider + circuit breaker + retry + fallback, instrumentado | Parte de F11/F12, estable |

**Consumidores de producción del v1:** el servicio `model-router.service` (proxy/cache/metrics) + scripts de tuneladora que consultan su `/metrics`.
**Consumidores directos del v1 como biblioteca:** solo tests (`test_model_router_*`, `test_router_*`).

El v2 NO replica: proxy HTTP, cache HTTP, dashboard web, CLI, ni VRAM guard.

## 2. Problema

- Dos implementaciones del mismo dominio → divergencia de big decisions (rutas, fallback, metrics).
- Mantenimiento duplicado (cache, health, selección de modelo).
- El v1 queda en `core/` (región v4.0 canónica "VIVO") mientras el v2 es el "estándar motor" — deuda de migración.

## 3. Decisiones de diseño

### D1 — El v1 NO se elimina ni se refactoriza en esta fase
El servicio `model-router.service` (2) produce en producción. Cambiar su ruta o su
API HTTP rompería el router de operación que consumen la tuneladora y los health checks.
**Migración incremental, nunca romper.**

### D2 — La consolidación es por CIMENTACIÓN, no por rewrite
Fase A (solo docs): documentar contrato público de v1 (endpoints, CLI, salidas `/metrics`,
formato de rutas) y mapeo funcional v1↔v2. Resultado: `docs/architecture/ADR-222-ANEXO-1-APIS.md`.
Fase B (decisión Ramón): elegir una de las 3 vías:
- **B1 (recomendada):** v2 `motor/core/llm/router` expone una *fachada de compat* que implementa la interfaz HTTP del v1 (proxy/cache/dashboard) delegando la lógica de selección a `LLMRouter`/`providers.py`. El servicio `model-router.service` apunta al nuevo módulo; se preservan todos los endpoints. Degradable: si `motor` falla, el v1 sigue instalable.
- **B2:** migración limpia del v1 a `motor/core/llm/router/extras/` y dejar `core/model_router.py` como shim (DeprecationWarning). El servicio cambia de ruta una sola vez.
- **B3 (no recomendado):** mantener v1 como está hasta v5.0 (más deuda).

### D3 — Regla de degradación (ADR-007)
La fachada B1 debe operar sin el v1 y sin el v2 por separado:
| Fallo v2 | v1 sobrevive |
| Fallo v1 (proxy) | v2 se mantiene para llamadas internas |

### D4 — No-duplicación de rutas
Definir **DEFAULT_ROUTES única** en `motor` (fuente de verdad) y el v1 consume la misma tabla — elimina el delta de rutas `codigo_complejo/codigo_rapido/razonamiento/...`.

---

## 4. Roturas posibles (anticipación — precheck)

| # | Rotura | Detección | Mitigación |
|---|--------|-----------|------------|
| R1 | `model-router.service` deja de responder en :11435 | `systemctl is-active model-router` + curl `/metrics` + watch `tuneladora` | No tocar el servicio en AVR; en B1 mantener contrato HTTP idéntico; rollback = `systemctl start model-router` con v1 |
| R2 | Los tests `test_model_router_*` (≈50) fallan al cambiar imports | `pytest tests/unit/test_model_router* -q` | En AVR NO tocar `core/`; tests v1 quedan como guarda de no regresión |
| R3 | Divergencia de rutas (v1 vs v2) → comportamiento distinto | Test de contrato: mismo prompt → mismo proveedor | Rutas únicas en `providers.DEFAULT_ROUTES`; test de igualdad v1↔v2 |
| R4 | Doble `PromptCache` (v1 y v2) → doble consumo de RAM | Mass generación + metrics RSS | Render constr en v2; el v1 cache HTTP queda solo en la fachada |
| R5 | `core/`viv por ing — ADR-007 | revisión de segunda parte obligatoria | Todas las vías B redactan ADR con justificación + plan y reembolso... documento, NO ejecución |
| R6 | Retirada de `vram_guard`, `dashboard`, `cli` sin reemplazo | Inv entario de comandos usados (tuneladora, mantto) | Mover esos 3 a `motor/core/llm/router/extras/` intactos (solo cambio de carpeta) |

## 5. Pasos concretos (Fase siguiente, tras revisión)

1. **A1 (documentación, sin código):** este ADR + ANEXO-1 con mapeo de endpoints (100% offline).
2. **B1 (propuesta; exec solo con OK Ramón):** crear la fachada, tests de contrato (endpoints/prompts), apuntar el servicio, smoke en pre-...   (rollback: `git revert` + `systemctl start` con unidad original).
3. **Verificación:** `curl localhost:11435/metrics`, `curl localhost:11435/v1/chat/completions` con prompt conocido → mismo provider que v1.

## 6. Servicios y riesgos en elreshold

- No dejar el v1 roto: `model-router.service` NO se modifica hasta B1 aprobado.
- Degradación: sistema sigue con Ollama vía `.Router` aun sin fachada.
- **DDOS:** no.
- **Migración reversible:** el servicio apunta a un `symlink/shim` — revertir es cambiar destino.

## 7. Revisión pendiente

- ✅ Documentado (este ADR)
- ⬜ Aprobación de Ramón para ejecutar B1
- ⬜ Revisión de segunda parte (ADR-007) antes de tocar `motor/`