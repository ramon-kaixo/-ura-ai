# Propuesta — Fase 9: Impacto Funcional y Consolidación Arquitectónica

> **Versión:** 1.0
> **Fecha:** 2026-07-04
> **Estado:** 📋 Propuesta — pendiente de aprobación
> **Fase anterior:** Auditoría Arquitectónica Post-Fase 8 (`v0.7.1-audit-fase8`)

---

## Principio Rector

Solo trabajo con **impacto funcional o arquitectónico demostrable**.  
La deuda técnica residual (lint, FTS, tests dependientes del entorno,
archivos Unicode, limpieza menor) queda en backlog independiente y
no bloquea ni se mezcla con esta fase.

---

## Stream A — Consolidación de Test Runners (Arquitectura)

**Problema:** `tests/test_unit.py` y `tests/unit_test_runner.py` son casi
duplicados (~95% solapamiento). 4 runners legacy más en `tests/` con
`if __name__ == "__main__"`.

| Archivo | Líneas | Propósito actual |
|---------|--------|-----------------|
| `tests/test_unit.py` | 77 | Runner con checks inline |
| `tests/unit_test_runner.py` | 62 | Casi idéntico a test_unit.py |
| `tests/test_integration.py` | 16 | Smoke test de integración |
| `tests/test_config.py` | 34 | Test de CONFIG desde config_manager |
| `tests/benchmark_fase7.py` | ~150 | Benchmark legacy |
| `tests/e2e_fase7.py` | ~200 | E2E tests legacy |

**Acción:**
1. Unificar `test_unit.py` + `unit_test_runner.py` en un solo runner
2. Mover benchmarks legacy a `tests/benchmarks/`
3. Estandarizar todos los runners con pytest (no `__main__` inline)
4. Verificar que `coverage run -m pytest` cubre todo sin excluir nada

**Impacto:** Mantenibilidad de tests, cobertura fiable, eliminación de duplicación.

---

## Stream B — Sistema de Plugins (Arquitectura)

**Problema:** `scripts/pro/plugin_registry.py` existe pero no se usa desde
ningún pipeline activo. El concepto de plugins está esbozado pero no integrado.

**Acción:**
1. Integrar `plugin_registry` en `tuneladora_mantenimiento.py` como etapa
   opcional post-inspectores
2. El registro debe ser por convención (descubrimiento automático en
   `scripts/pro/plugins/`) sin configuración adicional
3. Cada plugin debe tener interfaz `run(context: dict) -> dict` documentada
4. Degradación graceful: sin plugins → pipeline normal

**Impacto:** Extensibilidad del pipeline sin modificar la tuneladora.

---

## Stream C — Knowledge Engine: Modo Degradado Explícito (Funcional)

**Problema:** El sistema de degradación graceful existe pero no está
documentado formalmente ni es verificable en runtime. Cuando Qdrant falla,
algunos módulos lo silencian con `except: pass` pero no hay métrica ni log
que indique que se está ejecutando en modo degradado.

**Acción:**
1. Añadir flag global `global_state.degraded_mode: set[str]` con los
   subsistemas actualmente en degradación (ej: `{"qdrant", "ollama", "fts"}`)
2. Exponer vía endpoint `/api/v1/status` en `ejecutor_api.py`
3. Loggear WARNING cuando un subsistema entre/salga de modo degradado
4. Documentar modo degradado en `docs/architecture/DEGRADED_MODE.md`

**Impacto:** Visibilidad operativa del estado real del sistema.

---

## Stream D — Refactor de `ura.py` (Arquitectura)

**Problema:** `ura.py` (520 líneas) es un monolito con responsabilidades
mezcladas: CLI, init, deploy, validate, shell, etc. Tiene 15+ branches en
`main()` y usa `import lazy` condicional dentro de funciones.

**Acción:**
1. Extraer CLI a `motor/cli/` (ya existe `cmd_pipeline.py`, `cmd_diag.py`, etc.)
2. `ura.py` queda como entrypoint mínimo que delega en `motor.cli.main`
3. Sin cambios de comportamiento — solo reorganización

**Impacto:** Separación clara de responsabilidades, CLI mantenible,
`ura.py` de 520→~30 líneas.

---

## Stream E — Timeline y Criterios de Aceptación

| Stream | Esfuerzo estimado | Risco | Dependencias |
|--------|------------------|-------|-------------|
| A — Test runners | 2-3h | Bajo | Ninguna |
| B — Plugins | 3-4h | Medio | Stream A (opcional) |
| C — Degradado | 2-3h | Bajo | Ninguna |
| D — ura.py | 3-5h | Medio | Stream A (tests) |

**Criterios de aceptación:**
- Stream A: `python3 -m pytest tests/ -q` pasa sin excluir archivos
- Stream B: `plugin_registry.py` es llamado por tuneladora en modo seco
- Stream C: `global_state.degraded_mode` es observable vía API
- Stream D: `ura.py --help` funciona igual que antes; `motor.cli.main` existe

---

## Backlog de Deuda Técnica (No Bloqueante, No Incluido en Fase 9)

| ID | Ítem | Prioridad | Stream |
|----|------|-----------|--------|
| T01 | `core/synonyms.json` chattr +i | Mínima | Limpieza |
| T02 | `sanear_codigo.py:50` syntax error | Baja | Limpieza |
| T03 | 12 archivos con caracteres no-ASCII | Baja | Limpieza |
| T04 | 5 tests CLI fallan (deps) | Baja | Tests |
| T05 | FTS schema verifier falso positivo | Media | Knowledge Engine |
| T06 | ~2.356 lint errors | Baja | Limpieza |
| T07 | `adapters/` docs | Informativa | Docs |
| T08 | ~80+ `except: pass` sin auditar | Media | Hardening |
