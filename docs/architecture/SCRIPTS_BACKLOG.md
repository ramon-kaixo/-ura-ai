"""Scripts backlog — tests pendientes (post Fase 5).

Estos scripts importan motor/core/knowledge o necesitan infraestructura
especial (X11, GPU, Docker). Se cubriran tras la refactorizacion Fase 5.

| Archivo | Lineas | Bloqueo | Plan |
|---------|--------|---------|------|
| scripts/pro/test_latencia_mac.py | 45 | Importa core.voice.* | Fase 5+ |
| scripts/pro/captura_virtual.py | 61 | Necesita X11/scrot/xdotool | Integracion con Docker |
| scripts/pro/backup_f26_memory.py | 53 | Importa motor.memory | Fase 5+ |
| scripts/pro/reuse_detector_plugin.py | 17 | Importa scripts.pro.reuse.reuse | Fase 5+ |
| scripts/pro/router_rate_limiter.py | 45 | Importa motor.* | Fase 5+ |
| scripts/pro/ura-query.py | 40 | Importa core.memory_engine | Fase 5+ |
| scripts/pro/patch_timestamps.py | 55 | Script one-off de migracion | No testear (ya ejecutado) |
| scripts/pro/cleanup_assistant.py | 13 | Importa motor.assistant.* | Fase 5+ |
| scripts/pro/knowledge_engine.py | 16 | Thin wrapper de knowledge.engine.cli | Ya testeado via cli |
| scripts/pro/orchestrator.py | 21 | Puro stdlib | DONE (2 tests) |
| scripts/pro/check_secrets.py | 13 | Puro stdlib | DONE (2 tests) |
| scripts/pro/utils.py | 36 | Puro stdlib | DONE (3 tests) |
| scripts/pro/lock_manager.py | 68 | Puro stdlib | DONE (4 tests) |
| scripts/pro/reglas_loader.py | 62 | Puro stdlib | DONE (4 tests) |
| scripts/pro/backup_assistant.py | 47 | Puro stdlib | DONE (4 tests) |

Cobertura scripts/ hoy: 15 archivos analizados, 6 testeados (40%), 9 pendientes.
