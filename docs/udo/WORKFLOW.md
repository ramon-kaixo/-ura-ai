# WORKFLOW — Cómo trabajar con Web y Terminal

**UDO v5** (Fase 5 — hardening y cierre, 2026-08-09)

## Modelo de trabajo

```
Ramón ──► TASK-ID ──► Web (programador) + Terminal (consultor/revisor)
                          │                │
                          └──── Git ───────┘
                               │
                    Documentación + Verificación
```

- **Web programa** (ejecutor por defecto).
- **Terminal consulta, revisa y puede hacer tareas independientes**.
- **Git demuestra qué ocurrió** — nunca se depende de la conversación.

## Flujo normal

1. Ramón pide algo (o Terminal crea la tarea): `ura-udo create "descripción"`.
2. La tarea pasa a `IN_PROGRESS` con roles: `ura-udo update TASK --estado IN_PROGRESS --agente_web "WEB (ejecutor)" --agente_terminal "TERM (revisor)"`.
3. El ejecutor **declara su reserva** de zona: `ura-udo reserve TASK --add "zona/..."`.
4. El ejecutor analiza el plan (campo `--analisis`), implementa, commitea (`[TASK-ID][WEB|TERM]`).
5. Se registra validación: `ura-udo update TASK --validacion "suite 35/35, make validate"`.
6. La tarea pasa a `REVIEW`: quien revisa comprueba `ura-udo verify TASK` (gate: commits, pinning, árbol, discrepancias).
7. Cierre: `ura-udo update TASK --estado DONE --analisis "..." --validacion "..."` (solo desde REVIEW, con gate).
8. Si el revisor no está disponible: la tarea se cierra con **AUTO-REVISIÓN** y entra en `docs/udo/review-pending.md`.

## Envío de trabajo a la Web

- `ura-opencode "mensaje"` — crea tarea, la pasa a IN_PROGRESS con roles, inyecta el contexto UDO y la envía a la Web (puerto 8081).
- `ura-udo context TASK` / `ura-ask TASK` — recupera el contexto desde Git/expediente aunque el otro agente esté idle.
- `ura-chat "pregunta"` — chat LLM a Ollama (herramienta distinta).

## Reglas que nunca se rompen

1. Git es la fuente de verdad del código.
2. TASK-ID identifica el trabajo.
3. No modificar una zona bloqueada (reserva ajena).
4. No marcar DONE sin evidencia (gate).
5. Las discrepancias se registran (verify).
6. No guardar conversaciones completas (memoria = Git + expedientes).
7. No crear infraestructura nueva sin autorización.

## Recuperación tras interrupción

- `ura-udo status` — muestra tareas activas con owner, última actividad, commits, pendientes.
- `ura-ask TASK` — contexto completo reconstruible sin la conversación.
- Una tarea a medias queda `IN_PROGRESS`/`REVIEW`/`BLOCKED`, nunca DONE.
