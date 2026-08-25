# Plan Unificado de Saneamiento core→motor

**Fecha:** 2026-08-25
**Autor:** TERM (corregido sobre V1.1.0 + AUDITORIA_FORENSE_V1)
**Estado:** EN EJECUCIÓN

---

## Progreso

| Fase | Estado | Commit | Nota |
|------|--------|--------|------|
| 0 | ✅ | `6d7e18ac` | gitignore limpio, plan creado |
| 0-BIS | ✅ | `d7e51e68` | 23 shims eliminados, 20+ archivos migrados, 102 tests pass |
| A | ✅ | — | pyproject.toml ya era 0.29.0 |
| B | 🔮 | — | Migrar 17 production core→motor ( pendiente) |
| C | 🔮 | — | Consolidar CircuitBreaker (3→1) y logging (3→1) |
| D–H | 🔮 | — | Ver detalle abajo |

---

## Estado Real Corregido (vs audit original)

| Hallazgo del audit | Realidad actual | Acción |
|---------------------|-----------------|--------|
| Ciclo bidireccional core↔motor | ✅ **YA RESUELTO** — motor/ NO importa de core/ | No hacer nada |
| pyproject.toml 0.13.0 | ✅ **YA RESUELTO** — es 0.29.0 | No hacer nada |
| Token GitHub en .git/config | ✅ **YA RESUELTO** — URL limpia | No hacer nada |
| 4-36 bare except: | ✅ **REDUCIDO** — solo 1 real (docker_orchestrator.py, ya `# noqa`) | No hacer nada |
| 26 .py:line files | ✅ **YA LIMPIADOS** | No hacer nada |
| auditoria_debug.log | ✅ **YA ELIMINADO** | No hacer nada |
| 5 docs arquitectura duplicados | 🟡 **REDUCIDO a 2** (ARCHITECTURE.md + SYSTEM_ARCHITECTURE_v1.md) | Unificar |
| 3 versiones AUDIT_FASE7 | 🟡 **REDUCIDO a 2** (V2 + V3) | Eliminar V2 |

### Trabajo REAL pendiente

| Ítem | Alcance | Prioridad |
|------|---------|-----------|
| 20 archivos core/ importan de motor/ | Migrar imports o eliminar módulos huérfanos | ALTA |
| 6 providers duplicados (core/mochila vs motor/core/llm) | Migrar mochila_server a motor/ o congelar core/ | ALTA |
| 3 CircuitBreaker implementations | Consolidar en 1 | MEDIA |
| 3 sistemas de logging | Unificar en 1 | MEDIA |
| ~105 archivos core/ sin consumers claros | Auditar y eliminar/congelar | MEDIA |
| 3 memory_snapshot_*.json en raíz | Añadir a .gitignore, git rm --cached | BAJA |
| backups_gx10/ y archives/ (untracked) | Documentar o eliminar | BAJA |
| 2 docs arquitectura duplicados | Unificar | BAJA |
| build/ (13MB, gitignored) | Limpiar | BAJA |

---

## Fases Corregidas (orden nuevo)

### Fase 0 — Quick Wins (ya parcialmente hechos, completar)

| Tarea | Estado | Acción |
|-------|--------|--------|
| memory_snapshot_*.json | 3 archivos en raíz | `git rm --cached`, añadir a .gitignore |
| backups_gx10/ | Directorio untracked con copia completa del repo | Documentar que es backup, o eliminar si no se necesita |
| archives/ | Directorio untracked | Verificar contenido, eliminar si está vacío |
| docs duplicados | 2 arch docs + 2 audit docs | Unificar ARCHITECTURE.md → SYSTEM_ARCHITECTURE, eliminar V2 |
| build/ | 13MB, gitignored | `rm -rf build/` (ya está en .gitignore) |

**Criterio:** working tree limpio, 0 archivos sueltos en raíz.
**Tiempo:** ~15 min.

### Fase 0-BIS — Auditoría de dependencias core→motor (imports lazy)

**Objetivo:** Mapear exactamente qué imports de core/→motor/ son reales vs lazy vs muertos.

| Herramienta | Qué busca |
|-------------|-----------|
| `grep -rn "from motor\." core/ --include='*.py'` | Imports directos |
| `grep -rn "import motor" core/ --include='*.py'` | Imports indirectos |
| `grep -rn "sys.modules\[.*motor" core/ --include='*.py'` | Redirects PEP-562 |

**Resultado esperado:** Lista clasificada de los 20 archivos core/→motor/ en:
- **Migrar** (consumidor real, activo)
- **Eliminar** (módulo huérfano, sin consumers)
- **Congelar** (servicio independiente que funciona)

**Criterio:** cada archivo core/→motor/ tiene una decisión documentada.
**Tiempo:** ~1h.

### Fase A — Unificar Versiones (YA HECHO en parte)

pyproject.toml ya es 0.29.0. Solo queda:
- Verificar que `motor/assistant/main.py` coincide
- Sincronizar requirements con pyproject.toml

**Tiempo:** ~30 min.

### Fase B — Unificar core→motor (LA FASE CLAVE)

**Depende de:** Fase 0-BIS (saber qué migrar)

| Sub-fase | Tarea | Esfuerzo |
|----------|-------|----------|
| B.1 | Migrar `core/mochila/mochila_server.py` de `core.mochila.providers` a `motor.core.llm` | 4-6h |
| B.2 | Verificar que `motor.core.config.py` no depende de `core.config_manager` | 1h |
| B.3 | Congelar `core/` con README legacy | 10 min |
| B.4 | Verificar `grep -r "from core\|import core" motor/` = 0 | 30 min (ya hecho, confirmar) |

**Resultado:** motor/ independiente, core/ legacy congelado.
**Criterio:** 0 imports core→motor en código nuevo, suite pasa.
**Tiempo:** ~6-8h.

### Fase C — Consolidar Sistemas Duplicados

| Duplicado | Cuántos | Acción |
|-----------|---------|--------|
| CircuitBreaker | 3 (core/mochila, motor/core/llm, motor/diagnostico) | Consolidar en motor/core/llm/circuit_breaker.py |
| Logging | 3 (motor/observability, knowledge/engine, core/json_logger) | Unificar en motor/observability/logging.py |
| Providers | 6 (core/mochila/providers vs motor/core/llm) | Resolver en Fase B.1 |

**Criterio:** 1 CircuitBreaker, 1 sistema de logging, 0 providers duplicados.
**Tiempo:** ~8-10h.

### Fase D — Eliminar Código Muerto

**Depende de:** Fase B (saber qué está congelado)

| Módulo | Decisión |
|--------|----------|
| `core/mochila/providers/` | Eliminar si B.1 completó migración |
| `core/config_manager.py` | Eliminar si B.2 verificó que motor no lo necesita |
| `motor/intelligence/agents/` (F12) | Verificar consumidores → eliminar si 0 |
| `motor/intelligence/memory/` (F12) | Verificar consumidores → eliminar si 0 |
| Archivos core/ sin consumers | Eliminar según Fase 0-BIS |

**Criterio:** ~50 archivos eliminados, tests pasan.
**Tiempo:** ~4h.

### Fase E — Gobernanza (ADRs + docs)

| Tarea | Tiempo |
|-------|--------|
| Aprobar ADRs en Draft (F27, F28.1, F29) | 4h |
| Crear closeouts faltantes (F14, F16, F17, F17.5, F24) | 2h |
| Unificar docs de arquitectura en 1 | 2h |
| Actualizar AGENTS.md | 1h |

**Tiempo:** ~9h.

### Fase F — Política de Errores

| Tarea | Tiempo |
|-------|--------|
| Crear `motor/exceptions.py` con jerarquía | 1h |
| Establecer política (no reemplazar 773 existentes) | 30 min |
| Añadir ruff rule para prohibir bare except en nuevo código | 10 min |

**Tiempo:** ~1.5h.

### Fase G — motor/platform (Validar o Simplificar)

| Tarea | Tiempo |
|-------|--------|
| Identificar consumidores reales | 1h |
| Si solo 1-2: reducir a mínimo necesario | 4h |

**Tiempo:** ~5h.

### Fase H — Tests + CI/CD

| Tarea | Tiempo |
|-------|--------|
| Activar GitHub Actions | 1h |
| Verificar CI completo | 1h |
| Branch protection | 15 min |

**Tiempo:** ~2.5h.

---

## Resumen Corregido

| Fase | Esfuerzo original | Esfuerzo corregido | Nota |
|------|-------------------|--------------------|----|
| 0 | 30 min | 15 min | Mayoría ya hecho |
| 0-BIS | (no existía) | 1h | **NUEVA** — mapeo de dependencias |
| A | 1h | 30 min | Mayoría ya hecho |
| B | 5h | 6-8h | Más realista (mochila_server es complejo) |
| C | 5h | 8-10h | CircuitBreaker + logging + providers |
| D | 4h | 4h | Sin cambios |
| E | 10h | 9h | Sin cambios significativos |
| F | 3h | 1.5h | Más realista |
| G | 8h | 5h | Sin cambios significativos |
| H | 6h | 2.5h | Más realista |
| **Total** | **38-40h** | **~38-42h** | Similar pero más realista |

---

## Reglas de Ejecución

1. **Antes de cada fase:** revisar qué se hizo en la fase anterior y verificar el entorno
2. **Cada fase cierra con:** `ruff check .`, `pytest -q --tb=short`, working tree limpio
3. **Si una fase falla:** documentar, decidir si se corrige o se salta, nunca ignorar
4. **Commits:** `tipo(scope): [FASE-XX] descripción`
5. **Reversible:** cada fase debe poder revertirse con `git revert`
