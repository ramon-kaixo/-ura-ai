# CONFLICTS — Qué ocurre cuando Web y Terminal necesitan la misma zona

**UDO v5** — mecanismo de bloqueo por reserva.

## Cómo funciona

- Cada tarea activa (IN_PROGRESS/REVIEW) puede **reservar** zonas: `ura-udo reserve TASK --add "motor/core/llm/"`.
- Otra tarea que intente reservar la misma zona (exacta o prefijo `dir/`) recibe:

```
BLOQUEADO: 'motor/core/llm/x.py' — TASK=TASK-20260901-001 OWNER=WEB SCOPE=motor/core/llm (reserva activa).
Libera con reserve TASK-20260901-001 --clear o usa --force para autorización expresa.
```

- El **propietario** es quien posee la reserva válida asociada a su tarea. **No hay prioridad Web sobre Terminal** — la prueba inversa da el mismo resultado.

## Lo que puede hacer quien no tiene la reserva

**Leer, analizar, ejecutar pruebas, consultar** — sí.
**Escribir dentro del ámbito bloqueado** — NO (bloqueado por declaración).

## Bloqueo por declaración (importante)

El enforcement actúa al declarar la reserva (`update --reserva` / `reserve --add`). No hay watchers del filesystem (sería sobreingeniería). Regla práctica:

1. Antes de tocar cualquier archivo, ejecutar `ura-udo check ruta1 ruta2...`.
2. Si hay CONFLICTO → no tocar; informar, esperar o pedir autorización (`--force` auditado).
3. Si no hay conflicto → declarar la reserva ANTES de escribir.

## Tareas independientes en paralelo (permitido)

```
TASK-001 → WEB  → motor/core/llm/     ✅
TASK-002 → TERM → docs/ + scripts/    ✅  (zonas distintas, sin bloqueo mutuo)
```

El sistema evita conflictos, no impide el paralelismo útil.

## Discrepancias

`ura-udo verify TASK` compara la reserva y los cambios declarados contra Git:
- `MODIFICADOS SIN DECLARAR` — archivos tocados fuera de la reserva (⚠️).
- `RESERVADOS NO MODIFICADOS` — zona reservada sin tocar (sugerencia de liberación).
- Coherencia `cambios:` vs git (F4) — archivos reales fuera de lo declarado.
- La declaración "no modifiqué nada" con archivos en Git se detecta automáticamente.

## Desbloquear una zona

- El propietario termina y cierra la tarea → la reserva se libera automáticamente.
- `ura-udo reserve TASK --clear` — liberación manual (solo el propietario, sin `--force`).
- Lock huérfano (tarea abandonada con reserva activa): ver `TROUBLESHOOTING.md`.
