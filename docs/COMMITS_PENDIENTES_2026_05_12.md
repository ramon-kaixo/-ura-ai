# Commits pendientes — 2026-05-12

Estado: 377 archivos sin commitear (356 modificados + 21 nuevos)

## Grupo 1 — Documentación (PRIMERO)
Archivos: docs/*.md nuevos (7 archivos)
Mensaje: "docs: 7 documentos estratégicos sesión 11-12 mayo"
Archivos concretos: CICLO_MANTENIMIENTO_GX10.md, DOSIFICADOR_UNIVERSAL.md,
  KIMI_DEV_CONTEXTO.md, PROCESO_AUDITORIA_KIMI.md, SISTEMA_SEGURIDAD_GX10.md,
  SISTEMA_VOZ.md, TEST_RENDIMIENTO_GX10.md

## Grupo 2 — Scripts y helpers
Archivos: scripts/kimi_code_review.py, scripts/gx10_kimi_dev_setup.sh,
  scripts/code_review_night.sh, scripts/nightly_diary.sh (fix),
  ecosystem.config.js (+verificador)
Mensaje: "feat: scripts Kimi-Dev review, setup GX10, nightly diary fix"

## Grupo 3 — Nuevos módulos core
Archivos: core/timeout_manager.py (nuevo), core/payment_guardian.py (refactor),
  core/observability.py (fix), core/ura_diary.py (fix),
  core/openclaw_tracker.py (forensic_scribe bridge),
  core/sandbox_orchestrator.py (refactor 5→4 sandboxes)
Mensaje: "feat: timeout_manager, payment_guardian Telegram, sandbox orchestrator v2"

## Grupo 4 — Agentes nuevos
Archivos: agents/agente_critico.py, agents/agente_auditor.py,
  agents/agente_verificador_tareas.py, agents/agente_telegram_dam.py (pagos)
Mensaje: "feat: agente_critico, agente_auditor, verificador_tareas, DAM pagos"

## Grupo 5 — Fixes except:pass (core + agents + resto)
Archivos: core/**/*.py, agents/**/*.py, dashboard/**/*.py, services/**/*.py,
  tests/**/*.py, handlers/**/*.py modificados
Mensaje: "fix: except:pass → logger.warning en 51 bloques restantes"

## Grupo 6 — Estructura sandbox
Archivos: sandbox/ (nuevo: Mantenimiento, Seguridad, Aprendizaje, Documentación)
Mensaje: "feat: estructura sandboxes 4-ciclo con scripts y READMEs"

## Grupo 7 — Kimi audit helpers (GX10)
Archivos: bin/ en GX10 (kimi_review_limpio.sh, kimi_review_batch.sh,
  kimi_batch_helper.py, auto_throttle_*.sh, post_auditoria_kimi.sh,
  whisper_transcribe.py, controlador_recursos.sh)
Mensaje: "feat: helpers GX10 para Kimi-Dev audit, whisper, throttling"

## Grupo 8 — Tests
Archivos: tests/test_central_router.py (nuevo), tests modificados
Mensaje: "test: 14 unit tests para CentralRouter"

## Orden de ejecución
1. Verificar tests pasan ANTES de empezar
2. Hacer cada grupo en un commit separado
3. Tests deben pasar entre cada commit
4. Push al final

## Reglas
- NO usar git add -A
- Verificar git diff antes de cada add
- Si algún archivo está raro, dejarlo fuera
- .env NUNCA se commitea
