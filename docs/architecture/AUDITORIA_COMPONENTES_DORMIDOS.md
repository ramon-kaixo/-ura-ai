# Auditoría de Componentes Dormidos — URA v0.34.0
## Fecha: 2026-08-01

## Resumen Ejecutivo
| Categoría | Total | Activos | Dormidos | Obsoletos |
|-----------|-------|---------|----------|-----------|
| Agentes | 8 | 0 | 8 | 0 |
| Validadores | 2 | 2 | 0 | 0 |
| Telemetría | 2 | 0 | 2 | 0 |
| Cleaners/Reindex | 5 | 0 | 5 | 0 |
| Scripts entrypoint | 15 | 6 | 8 | 1 |
| **TOTAL** | **32** | **8** | **23** | **1** |

## Agentes (0% cobertura, todos dormidos)
- core/agents/cli.py, conciencia.py, ejecutor.py, healing.py, orquestador.py, reparador.py, telemetry.py
- core/change_guardian.py

## Scripts desbloqueados post-Fase 5 (ahora testeables)
- scripts/pro/ura-query.py (40 líneas, core.memory_engine)
- scripts/pro/reindex_vectors.py (knowledge.engine)
- scripts/pro/cleanup_assistant.py (13 líneas, motor.assistant)
- scripts/pro/uitars_hetzner.py (motor.core.secrets)
- scripts/pro/router_rate_limiter.py (45 líneas, motor.*)
- scripts/pro/backup_f26_memory.py (53 líneas, motor.memory)

## Herramientas sin instalar (bajo esfuerzo, alto valor)
- pytest-deadfixtures
- pytest-randomly
- radon (complejidad ciclomática)

## Recomendación inmediata
Atacar los 6 scripts desbloqueados → +15-20 tests, cobertura sube a ~43%.
