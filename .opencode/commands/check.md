---
description: "Verificación sobre una tarea concreta: revisor + verificador"
agent: build
subtask: true
---

Ejecuta verificación enfocada en una tarea específica:

## Uso
/check "descripción de la tarea a verificar"

## Qué hace
1. @revisor analiza la tarea y código relacionado → GO / GO CON CAMBIOS / NO-GO
2. @verificador ejecuta gates relevantes (ruff, mypy, pytest subset, secret-scan)
3. Reporta evidencia literal y veredicto final

Solo para tareas concretas, no auditoría general.
