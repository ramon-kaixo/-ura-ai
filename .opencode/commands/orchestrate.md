---
description: "Parsea un plan markdown y distribuye tareas al orquestador URA automáticamente. Uso: /orchestrate <ruta_plan.md>"
---

Cuando el usuario invoque `/orchestrate`, ejecuta este flujo:

## 1. Leer el plan
El usuario pasará un archivo de plan como argumento (`$ARGUMENTS`). Lee el contenido del archivo.

## 2. Parsear y crear tareas
Ejecuta el script parser contra el orquestador:

```bash
python3 /home/ramon/URA/ura_ia_1972/scripts/pro/parse_plan_to_tasks.py "$ARGUMENTS" --json
```

O si el plan está en Mac:
```bash
python3 ~/URA/ura_ia_1972/scripts/pro/parse_plan_to_tasks.py "$ARGUMENTS" --json
```

## 3. Mostrar resumen
Devuelve al usuario:
- Cuántas tareas se crearon
- IDs de cada tarea
- A qué nodos se asignaron
- Estado de la cola

## 4. Verificar distribución
```bash
curl -s "$URA_ORCHESTRATOR_URL/stats"
```

## Ejemplo de uso
El usuario escribe:
```
/orchestrate docs/plans/sprint2.md
```

Tú ejecutas:
1. Lees `docs/plans/sprint2.md`
2. Lo pasas al parser
3. Cada `- [ ]` o `1.` se convierte en una tarea via API
4. Devuelves el resumen

## Si no hay argumento
Si el usuario solo escribe `/orchestrate` sin archivo, pídele que especifique la ruta del plan.

## Formato del plan esperado
```markdown
## Sprint 2 — Eficiencia

### B1: Refactor X
- [ ] Tarea 1: descripción
  Prioridad: alta
  Nodo: gx10

### B2: Test Y
1. Tarea 2: descripción
   Prioridad: media
```

El script parsea automáticamente:
- `##` / `###` = fase/bloque
- `- [ ]` o `1.` = tarea
- `Prioridad:` = prioridad (alta/media/baja)
- `Nodo:` = nodo destino
