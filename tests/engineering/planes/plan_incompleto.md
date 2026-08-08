# PLAN EJEMPLO 2 — Incompleto (defecto: faltan mínimos, validación y NO HACER)

**Objetivo**: cambiar el formato de los expedientes UDO para incluir seguimiento de tiempo.
**Por qué**: saber cuánto tarda cada tarea.
**Contexto**: los expedientes viven en `docs/udo/tasks/`.
**Qué hacer**: añadir campos `inicio:` y `fin:` al template y a `create`.
**Comportamiento**: al crear una tarea, se rellenan los timestamps.
**Cierre**: los campos existen.
