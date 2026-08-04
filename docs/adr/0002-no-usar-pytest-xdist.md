# ADR-0002: No usar pytest-xdist en make test-fast

## Estado
Aceptado

## Contexto
pytest-xdist con `-n auto` satura el host (64 cores) y OpenBLAS falla.

## Decision
Mantener tests secuenciales en Makefile. Se puede usar `-n auto` manualmente si se desea.

## Consecuencias
- Tests mas lentos (~7 min vs ~47s)
- Mas estable, sin saturacion de CPU
- Se puede usar manualmente: `pytest -n auto` cuando se necesite velocidad
