# ADR-040: T3: external_audit.sh — quitar Claude/GPT-4o, verificar output Ollama

**Fecha:** 2026-07-29
**Categoría:** Arquitectura: Refactorización
**Autor:** ramon-kaixo
**Commit:** 69b0593

## Contexto
- Elimina _call_openrouter para Claude 3.5 Sonnet y GPT-4o
- Añade verificación post-Ollama: archivo no vacío y >=500 bytes
- Si la verificación falla: exit 1 con mensaje de error
- Actualiza echo final a solo OLLAMA_FILE

## Decisión
Arquitectura: Refactorización

## Archivos afectados
- `scripts/pro/external_audit.sh`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*
