# ADR-041: T4: integra DeepSeek en external_audit.sh

**Fecha:** 2026-07-29
**Categoría:** Seguridad: Autenticación y autorización
**Autor:** ramon-kaixo
**Commit:** de4bcf0

## Contexto
- _call_openrouter reemplazada por _call_deepseek
- Lee DEEPSEEK_API_KEY de .env (grep|cut|tr|xargs) + env var fallback
- Pipeline: DeepSeek (deepseek-coder) → Ollama fallback
- Sin exit 1 en fallo DeepSeek (solo warning + fallback)
- exit 1 solo si ambos fallan
- Elimina dependencia de motor.core.secrets

## Decisión
Seguridad: Autenticación y autorización

## Archivos afectados
- `scripts/pro/external_audit.sh`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*
