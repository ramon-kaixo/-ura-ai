# workflow_engine.py — ARCHIVADO

**Fecha de archivado:** 2026-05-12
**Razón:** Legacy del 6 de mayo de 2026. Reemplazado por `core/central_router.py`.
**Último importador real:** `api/main.py` (migrado a central_router en commit `86cded9`)
**Referencias restantes:** solo en benchmarks/tests (no producción)

## Cómo restaurarlo

```bash
mv archive/legacy/workflow_engine.py core/workflow_engine.py
```

## Por qué se archivó

- Era el "motor principal" original pero quedó obsoleto
- `central_router.py` tiene 93 agentes vs 15 del registry original
- El método `process_request()` que esperaba `api/main.py` NO existía (AttributeError)
- 0 módulos de producción lo importaban
