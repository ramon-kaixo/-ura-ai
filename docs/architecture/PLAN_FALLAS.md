<!-- PLAN_FALLAS v1.0 — TASK-20260809-007 -->

# PLAN — Solución de todas las fallas detectadas

**Fecha**: 2026-08-09 · **Estado**: APROBADO por Ramón ("prepárame un plan... y después soluciona")
**Baseline**: suite completa real — **21 failed, 5936 passed** (de 32 originales; 11 ya arreglados)

---

## 1. Inventario de fallas (estado real medido)

| # | Grupo | Nº | Categoría | Causa raíz |
|---|-------|----|-----------|------------|
| G1 | **Bug de producción: `call_with_fallback`** (strategy.py:277) | 1 | Código | `return result, primary` DENTRO del `for` — el fallback prueba solo 1 alternativa y abandona; ignora `fallback_max_providers>1`. Detectado al arreglar tests de resiliencia. Requiere ADR-007 (núcleo congelado) |
| G2 | **Dependencia de orden entre tests** (lexical_window, llm_init, llm_ollama, llm_router_init, llm_router, gemini, openrouter, benchmark, lmstudio, vllm) | ~15 | Tests | El `ProviderRegistry` es singleton global; los tests lo modifican sin restaurar. El fixture `reset_provider_singletons` de conftest es **vacío** (`yield` sin reset). Pasan en aislamiento, fallan en suite |
| G3 | **Tests que requieren API key/red** (gemini, openrouter) | 2 | Entorno | Sin key configurada, el validate de provider falla — deberían saltarse con skipif, no fallar |
| G4 | **Tests de benchmark** (benchmark_providers, benchmark_rag) | 6 | Entorno | Dependen de scripts/servicios pesados de benchmark; deberían marcarse `slow`/`integration` |
| G5 | **e2e chat_flow** (test_chat_basic) | 1 | Entorno | Requiere servidor HTTP real (401) — es test de integración E2E |

## 2. Análisis de causa raíz detallado

### G1 — Bug real del núcleo (el más importante)
- **Dónde**: `motor/core/llm/router/strategy.py:277` — `return result, primary` dentro del `for fallback_name`.
- **Evidencia**: debug directo — `a` falla → prueba `b` → falla → **devuelve error sin intentar `c`** (log: `llm_fallback primary=a fallback=b error=fallback_failed`, `c._calls=0`).
- **Impacto**: con `fallback_max_providers=3`, solo se usa 1 proveedor de respaldo; si el primer fallback falla, no hay más alternativas aunque existan.
- **Historia**: el bug existía antes del refactor `7d77fccc` (verificado con git) — es de diseño original, no regresión.
- **Fix (con ADR-007)**: mover el `return result, primary` FUERA del bucle (después del `for`): si todos los fallbacks fallan, devolver el error del primario. ADR breve documentado en el commit.

### G2 — Dependencia de orden (la más extendida: ~15 tests)
- **Dónde**: `tests/conftest.py` fixture `reset_provider_singletons` (vacío).
- **Evidencia**: todos pasan en aislamiento (`pytest test_x` → 1 passed), fallan en suite.
- **Causa**: `ProviderRegistry` y otros singletons (`_EngineHolder`, routers) mantienen estado entre tests. El fixture que "resetea" no resetea nada.
- **Fix**: implementar el reset real en `reset_provider_singletons` (limpiar registros de proveedores) + ampliar `modules_to_clear` en `isolate_test_environment`.

### G3-G5 — Entorno (9 tests)
- Tests que requieren credenciales/servicios externos sin skip condicional.
- **Fix**: `@pytest.mark.skipif` cuando falta la API key / marcar `slow`/`integration` los de benchmark y e2e.

## 3. Soluciones (orden de ejecución)

| Paso | Qué | Archivo(s) | Validación |
|------|-----|------------|------------|
| 1 | **G1**: fix del fallback (ADR-007 documentado) | `motor/core/llm/router/strategy.py` | test_fallback_no_chain pasa con la cadena completa (c llamado) |
| 2 | **G2**: reset real de singletons en fixture | `tests/conftest.py` | los 15 tests de orden pasan en suite |
| 3 | **G3**: skipif sin API key | `motor/tests/test_gemini.py`, `test_openrouter.py` | skipped en suite, no failed |
| 4 | **G4**: marcar benchmark slow/integration | `motor/tests/test_benchmark_*.py` | deselected con `-m "not slow"` |
| 5 | **G5**: marcar chat_flow como integration/e2e | `motor/tests/e2e/test_chat_flow.py` | deselected con `-m "not slow"` |
| 6 | Validación completa | suite completa | objetivo: **0 failed** en suite |

## 4. Riesgos

- G1 toca el núcleo (ADR-007) → el fix es mínimo (mover return fuera del bucle) y reversible; test actualizado verifica la cadena completa.
- G2: resetear singletons puede romper tests que dependen del estado residual → validar suite completa.
- No tocar: API pública del router, comportamiento de los proveedores, lógica de retry.

## 5. Criterios de cierre

1. `test_fallback_no_chain` verifica cadena completa (c llamado, fallback_max_providers respetado).
2. Suite completa: **0 failed** (o solo los skipif justificados como skipped/deselected).
3. ADR-007 documentado en el commit del fix G1.
4. Todo con trazabilidad TASK-20260809-007.

---

*Plan elaborado por TERM desde evidencia medida (suite 6:02 real). Ejecución autorizada.*

## 6. Resultados de ejecución (2026-08-09)

| Paso | Estado | Evidencia |
|------|--------|-----------|
| G1 fix fallback (ADR-007) | ✅ | test_fallback_no_chain: cadena completa a→b→c, 56 passed resiliencia |
| G3-G4 chat_flow + benchmark | ✅ | chat_flow 3 passed (con auth header); benchmark 15 deselected de suite rápida |
| test_cli + test_llm_providers | ✅ | 10 + 67 passed (autocontenidos) |
| G2 orden (fixture conftest) | ⚠️ PARCIAL | pop+re-import: 29→6 failed (5936 passed). Quedan 6 por estado compartido de _EngineHolder/mocks (TypeError MagicMock en moderation.py) — causa raíz identificada, PENDIENTE |

**Fallos residuales (6, todos de orden/estado compartido entre archivos)**:
- test_motor_lexical_window (3), test_motor_llm_ollama (1), test_motor_llm_strategy (2)
- Causa: `_EngineHolder`/config singleton contaminado por tests previos (TypeError: MagicMock en moderation.py:51)
- Pendiente: tarea aparte (no se resuelve sin tocar la arquitectura de fixtures de assistant)
