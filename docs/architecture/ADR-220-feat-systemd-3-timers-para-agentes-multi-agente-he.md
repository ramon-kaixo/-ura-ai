# ADR-220: feat(systemd): 3 timers para agentes multi-agente healing 5min telemetry 1min ej

**Fecha:** 2026-08-02
**Categoría:** Infraestructura: Systemd
**Autor:** ramon-kaixo
**Commit:** 2bb5c6a

## Contexto
Cambio significativo detectado automáticamente.

## Decisión
Infraestructura: Systemd

## Archivos afectados
- `systemd/ura-ejecutor.service`
- `systemd/ura-ejecutor.timer`
- `systemd/ura-healing.service`
- `systemd/ura-healing.timer`
- `systemd/ura-telemetry.service`
- `systemd/ura-telemetry.timer`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*
