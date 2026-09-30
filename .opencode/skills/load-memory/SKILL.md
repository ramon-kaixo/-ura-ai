---
name: load-memory
description: Cargar la memoria del proyecto al iniciar una sesión de trabajo
---

# Cargar memoria del proyecto

Al iniciar una sesión de trabajo:

1. Lee `.opencode/memory.md` (usa `memory:read`).
2. Si tiene contenido, úsalo como contexto base.
3. Si está vacío, dilo y sigue.

Al cerrar una sesión de trabajo:

1. Actualiza `.opencode/memory.md` (usa `memory:append` o `memory:write`).
2. Incluye: qué se hizo, decisiones nuevas, problemas conocidos, próximos pasos.
