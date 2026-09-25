# Sesión 2026-09-25 — Saneamiento y optimización

## Resumen

Sesión de diagnóstico y corrección del entorno Mac/ASUS OpenCode.

## Cambios realizados

### Mac
- Protocolo <<<RESUMEN>>> instalado en ~/.config/opencode/AGENTS.md
- Modelo qwen3-coder:30b-mejorado-100k añadido al config del proyecto
- default_agent cambiado de "general" (subagente) a "build"
- Symlinks rotos en ~/.config/opencode/ eliminados o re-apuntados
- 3 scripts de fases: phase-checkpoint.sh, phase-close.sh, prune-phase.sh
- Hook pre-push Syncthing arreglado (HTTPS + -k)
- Hook audit-cierre-udo arreglado (bash -c para || true)
- 5 expedientes UDO con commits reales

### ASUS (DECLARADO — no verificado en esta sesión)
- OLLAMA_KEEP_ALIVE=-1
- OLLAMA_NUM_PARALLEL=3
- OLLAMA_CONTEXT_LENGTH=100000
- Modelo -100k creado (num_ctx 100000, 48.6 GB VRAM vs 97 GB del original)

### Seguridad
- Secreto Syncthing (MAC_API_KEY) rotado
- Ramas con el secreto purgadas
- Stash purgado
- Reflog expirado + GC
- Bundle de backup en ~/backups-repo/

## Estado del CI

- Antes: rojo desde 2026-08-31 (25 días)
- Después: verde, 9/9 jobs (último run: 36153350317)

## Pendientes

- Fusión AGENTS.md (Protocolo de Fases)
- Fase v6.1
- Deuda: cobertura <80%, flaky tests
