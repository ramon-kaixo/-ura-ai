# LangGraph + URAOrchestrator — ARCHIVADO

**Fecha:** 2026-05-12
**Razón:** Instalado pero nunca ejecutado en producción.

## Estado al archivar
- 0 tareas procesadas (logs/telegram.log vacío)
- 0 tests
- Solo 15 agentes registrados vs 93 de central_router
- 6 dependencias externas (~50MB): langgraph, langchain-core, langgraph-checkpoint, langgraph-prebuilt, langgraph-sdk, pxxhash

## Por qué se archivó
- `central_router.py` tiene 93 agentes vs 15 del registry de LangGraph
- Telegram nunca procesó tareas reales
- Slack bot nunca se usó
- Mantener 2 sistemas de routing paralelos es deuda técnica

## Archivos archivados
- `orchestrator_langgraph.py` — URAOrchestrator + LangGraph pipeline (3 nodos)
- `slack_bot.py` — dependía de URAOrchestrator

## Cómo restaurar
```bash
mv archive/langgraph_unused/orchestrator_langgraph.py .
mv archive/langgraph_unused/slack_bot.py .
pip install langgraph langchain-core
```
