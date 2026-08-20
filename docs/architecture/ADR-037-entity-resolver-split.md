# ADR-037: División de entity_resolver.py en 5 submódulos (Consolidación Fase 3)

> **Fecha:** 2026-08-20
> **Propósito:** Reducir complejidad del núcleo de fusión (764 → 312 líneas) sin cambiar API pública
> **Estado:** ✅ Aprobado (ejecutado, commit `91242a6b`)

## Contexto

`motor/core/fusion/stages/entity_resolver.py` (764 líneas, F25-B3) concentraba
5 responsabilidades distintas: modelos de datos (EntityDef, CachePolicy),
registro de entidades (EntityRegistry + defaults), cache LRU, estrategias de
scoring (ScoringStrategy, KeywordScorer) y resolvers (RuleBased/Contextual +
EntityResolutionStage). Superaba los límites de longitud y complejidad del plan
de consolidación (objetivo: núcleo sin archivos >400 líneas).

## Decisión

Dividir en 5 archivos por responsabilidad, manteniendo `entity_resolver.py`
como fachada con re-exports (API pública intacta):

| Archivo | Contenido |
|---------|-----------|
| `entity_models.py` | EntityDef, CachePolicy |
| `entity_registry.py` | EntityRegistry, _DEFAULT_ENTRIES, _DEFAULT_REGISTRY |
| `entity_cache.py` | LRUCache |
| `entity_scoring.py` | ScoringStrategy, KeywordScorer |
| `entity_resolver.py` | _extract_entity_candidates, RuleBasedEntityResolver, ContextualEntityResolver, EntityResolutionStage + re-exports |

## Alternativas consideradas

- **No dividir** (mantener 764 líneas): no cumple el plan de consolidación.
- **Dividir en 2-3 archivos**: menor ganancia de mantenibilidad.

## Impacto

- Importadores (`motor/core/fusion/__init__.py:78`, `stages/__init__.py:8`,
  `engine.py:93`) no cambian: importan los 9 símbolos desde `entity_resolver`.
- Tests: 232 passed (81 unit + 151 motor/tests), 0 regresiones.
- Cobertura: 92.6% en resolver, ruff limpio, mypy 0 errores.

## Reversibilidad

`git revert 91242a6b` restaura el archivo original (los 4 nuevos se eliminan).

## Degradación

Sin el cambio: el sistema funciona igual (solo empeora mantenibilidad).