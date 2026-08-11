# Hallazgos del modo de revisión autónoma de fondo

**Política (Engineering Process v1.5 §Modo fondo)**: cuando un agente (WEB/TERM) está en modo de revisión autónoma de fondo y detecta problemas en el código de URA, los registra aquí con su gravedad. La conversación NO es memoria: si un hallazgo no está en este archivo, no existe.

**Gravedad**: `CRÍTICA` (riesgo de seguridad, pérdida de datos, rotura funcional) · `ALTA` · `MEDIA` · `BAJA` · `INFO`

**Reglas**:
- Un hallazgo CRÍTICO además se notifica por `core/notifier.py` (Telegram/Pushover) o se resalta al inicio del siguiente mensaje al humano.
- Todo `ruta:línea` citado debe existir de verdad (verificable con `ls`/`grep`).
- Un hallazgo se marca `estado: abierto | propuesto (con plan) | aprobado | corregido | descartado`.
- NO se corrige nada desde el modo fondo: los hallazgos se proponen y esperan autorización.

## Hallazgos

| fecha | ruta:línea | hallazgo | gravedad | estado |
|-------|-----------|----------|----------|--------|
| 2026-08-11 | — | (ejemplo) `core/mochila/router.py:123` fallo X | MEDIA | abierto |

## Progreso

| fecha | carpeta/módulo revisado | resultado |
|-------|------------------------|-----------|
| 2026-08-11 | (ejemplo) `core/mochila/` | 0 hallazgos nuevos |
