---
name: orchestrator-plan
description: Parsea plan markdown y distribuye tareas al orquestador URA
---

# Orchestrator Plan

Parsea un plan markdown y distribuye tareas al orquestador URA.

## Uso
```bash
python3 scripts/pro/parse_plan_to_tasks.py <ruta_plan.md> --json
```
Parsea markdown con `##`/`###` (fases), `- [ ]` o `1.` (tareas), `Prioridad:`, `Nodo:`.
Devuelve: cuántas tareas, IDs, nodos asignados, estado de la cola.
