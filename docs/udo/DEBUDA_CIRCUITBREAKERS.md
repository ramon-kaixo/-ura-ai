# Deuda de CircuitBreakers — Estado y decisión

**Fecha:** 2026-08-25 · **Auditoría:** FASE C.1 del PLAN MAESTRO V5

## Estado real (verificado)

Existen **3 implementaciones** de CircuitBreaker en el código:

| Archivo | Clase | API | Uso | Consumers |
|---------|-------|-----|-----|-----------|
| `motor/platform/resilience.py` | `CircuitBreaker` | `call(fn, ...)` | CB genérico thread-safe, factory | `motor/core/llm/circuit_breaker.py` (wrapper) |
| `motor/core/llm/circuit_breaker.py` | `CircuitBreaker(_CircuitBreaker)` | `call(fn, ...)` → lanza `CircuitBreakerOpenError` | LLM router | `motor/core/llm/router/strategy.py` |
| `motor/diagnostico/circuit_breaker.py` | `CircuitBreaker` | `operacional() -> bool` | Health check Qdrant | `motor/diagnostico/diagnostico.py` |
| `core/mochila/circuit_breaker.py` | `CircuitBreaker` | per-provider, JSON persistencia | Mochila providers | `core/mochila/mochila_server.py` |

## Decisión (tomada 2026-08-25, documentada)

**RETENER las 4 implementaciones.** Razones:

1. **APIs diferentes, no intercambiables:**
   - `motor/platform` → wrapper de llamadas (`call`)
   - `motor/diagnostico` → sonda de salud Qdrant (`operacional`)
   - `core/mochila` → estado por provider con persistencia JSON

2. **Dominios distintos:** LLM router, Qdrant health, mochila providers — cada uno con semántica propia de fallo.

3. **Riesgo de consolidación > beneficio:** unificar exigiría reescribir 3 APIs + sus consumers + tests, sin mejora funcional.

**Nota:** `motor/core/llm/circuit_breaker.py` ya es un wrapper fino sobre `motor/platform` (no duplicación de lógica). La única duplicación "pura" es la clase base, que es trivial (~30 líneas).

## Alternativa futura (no bloqueante)
Si se quisiera consolidar: unificar `motor/diagnostico` sobre `motor/platform` añadiendo un método `is_available()` — pero requiere tocar `core/mochila` (legacy congelado), por lo que se difiere hasta la migración de mochila a motor/.
