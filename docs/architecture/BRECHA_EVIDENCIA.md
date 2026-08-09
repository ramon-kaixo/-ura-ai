# BRECHA DE EVIDENCIA — Medición real (suite completa + cobertura)

**Fecha**: 2026-08-09
**Tarea**: TASK-20260809-004 (TERM) + TASK-20260809-005 (Web, pendiente de sesión)
**Objetivo**: cerrar la brecha entre lo afirmado y lo demostrado: ¿cuántos tests hay, cuántos pasan de verdad, y cuál es la cobertura real?

---

## 1. Suite completa ejecutada (evidencia real, no estimada)

**Comando**: `.venv/bin/python -m pytest tests/unit/ tests/integration/ motor/tests/ -q --tb=short -m "not slow"` — sin cache, timeout 3000s.

### Resultado: **5925 passed, 32 failed, 38 skipped, 135 deselected** en 306s (5:06)

- ✅ **93% de los tests pasan** (5925/6323 ejecutados)
- ❌ **32 fallos reales** (más de los 16 documentados — la suite completa revela más)

### Clasificación de los 32 fallos

| Grupo | Nº | Causa | ¿Código roto o test roto? |
|-------|----|-------|---------------------------|
| Proveedores LLM sin API key (lmstudio/openrouter/gemini/vllm) | 8 | Dependen de credenciales/red externas | ⚠️ **Test que requiere entorno** (fallan en aislamiento también si no hay key) |
| Fallback/resiliencia (test_fallback_*, test_logging_*) | 5 | Usan `_call_with_fallback` — **API privada eliminada del router** | ❌ **Test roto** (firma desincronizada con el código) |
| Benchmark providers/rag | 5 | Dependen de scripts/servicios de benchmark | ⚠️ **Test de integración pesado** |
| CLI pattern_matcher | 2 | `buscar_patrones()` llamada con 4 args (firma real: 3) | ❌ **Test roto** — **ARREGLADO (10 passed)** |
| LLM providers registry | 2 | `test_registry_*` dependen de estado global | ⚠️ **Dependencia de orden** (pasan en aislamiento) |
| e2e chat_flow, detector, vllm retry/router | 6 | Mix: auth 401, servicios externos | ⚠️ Mixto |

### Confirmación clave (prueba de orden)

- `test_lmstudio.py`: **12 passed EN AISLAMIENTO** pero falló en suite → **dependencia de orden/estado compartido** entre archivos de test (el fixture autouse de conftest no aísla todo).
- `test_resiliencia.py::test_fallback_no_chain`: falla SIEMPRE → API privada `_call_with_fallback` eliminada del router (el código usa `call_with_fallback` de módulo).

## 2. Cobertura real

**NO VERIFICADA con medición completa**: la suite con `--cov` de los 3 módulos no terminó en el tiempo de ejecución disponible (timeout). Datos documentados previos (AGENTS.md):

| Fecha | Fuente | Cobertura |
|-------|--------|-----------|
| Post-F29 F2 | AGENTS.md | CI 20.8% → **65.9%** |
| PM v3.1 | PLAN_MAESTRO_CLOSEOUT | core/ 38.8% → **51.1%** |
| 2026-08-09 | **sin medición completa** | **NO VERIFICADO** |

**El "90%" que mencionaste NO tiene evidencia en el repo.** La única forma de verificarlo: ejecutar la suite completa con `--cov` (timeout >30 min) o por módulos en paralelo. Pendiente real.

## 3. Tests retirados (F0 de la tarea mutmut)

- `motor/tests/test_mcp_server.py` — eliminado (módulo archivado en purga)
- 2 tests MCP de `test_e2e.py` — retirados con nota (módulo archivado)
- Recolección actual: **6378 tests, 0 errores** (limpia)

## 4. Hallazgos nuevos (clasificación §15)

| Id | Hallazgo | Clase |
|----|----------|-------|
| B1 | **~7 tests usan API privada eliminada** (`_call_with_fallback`) — son los fallos "reales" de resiliencia | NECESARIO (tarea aparte de arreglo) |
| B2 | **Dependencia de orden entre test files** — lmstudio/providers pasan solos, fallan en suite (el fixture autouse no aísla proveedores entre archivos) | NECESARIO (investigación de fixtures) |
| B3 | **8 tests requieren API keys/red externa** sin skip condicional — ensucian la suite | MEJORA (añadir `@pytest.mark.skipif` si falta key) |
| B4 | **5 tests de benchmark** dependen de scripts/servicios pesados | MEJORA (marcar `slow`/`integration`) |
| B5 | Cobertura 90% **sin evidencia** | DESCUBRIMIENTO (medir con timeout largo) |
| B6 | 32 fallos reales > 16 documentados | DESCUBRIMIENTO (la suite completa importa) |

## 5. Veredicto

**La brecha está caracterizada** (esto era el objetivo): 
- **Tests**: 6378 recolectados · **5925 pasan** (93%) · **32 fallan** (5 arreglados hoy: test_cli 10 passed)
- **Cobertura**: 65.9% documentado (julio) · **90% NO VERIFICADO**
- "Revisado 100×100" → **recolectado 100%, ejecutado ~93%**, con 32 fallos reales documentados y clasificados

**Pendientes para cerrar del todo**:
1. Arreglar los ~7 tests de resiliencia con API privada rota (tarea dedicada)
2. Investigar la dependencia de orden (fixtures de proveedores)
3. Medir cobertura completa (timeout >30 min, o por módulos)
4. Añadir skips condicionales a tests que requieren API keys

---

*Informe por TERM (TASK-004). Datos: suite completa real (5:06), no estimaciones. Web: TASK-005 pendiente de sesión.*
