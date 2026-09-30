# Memoria del proyecto URA

OpenCode lee este archivo al inicio de cada sesión.

## Convenciones

- Tests: `python3 -m pytest tests/ -q`
- EventBus canónico: `motor/events/`. `core/event_bus.py` es legacy.
- Nunca editar archivos en `src/generated/` directamente.
- CLI de tareas: `ura-udo`. Estados: PLANNED → IN_PROGRESS → REVIEW → DONE.

## Estado actual (2026-09-30)

- Repo: `/home/ramon/URA/ura_ia_1972`, rama `main`
- Último commit: `97baa7fb chore(gitignore): ignorar reports semanales`
- Sin commitear: `motor/memory/crypto.py`, `mypy.ini`, `opencode.json`
- Worktree activo: `ia/w2` en `/home/ramon/ura-worktrees/w2`

## Problemas conocidos

- `ura-auto-reindex.service` falla (path hardcodeado incorrecto).
- `ura-backup-mac.service` lleva horas en `activating` — verificar.

## Decisiones

- 2026-09-30: OpenCode + Ollama tiene bugs (#5187, #8528) que rompen plugins de memoria con side sessions. Se abandona esa vía. Memoria persistente = este archivo + `ura-udo`.
- 2026-09-29: borrado `llama3.3:70b` (no cabía en VRAM).
- 2026-09-29: `OLLAMA_MAX_LOADED_MODELS=2` para convivir chat y summarizer.

## Próximos pasos

- Investigar `ura-auto-reindex.service`.
- Verificar `ura-backup-mac.service`.
