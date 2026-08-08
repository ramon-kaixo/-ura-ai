# PLAN EJEMPLO 4 — Fase futura (defecto: implementa trabajo de F4 durante F3)

**Objetivo**: desplegar la telemetría de fases en un panel web.
**Por qué**: visualizar el estado de las tareas.
**Contexto**: la fase actual es F3 (cierre de revisiones); F4 (panel de telemetría) está planificada como fase posterior en el roadmap.
**Qué hacer**: crear `scripts/pro/panel_telemetria.py` (servidor HTTP con FastAPI), una BD SQLite para métricas de tareas, y un dashboard.
**Mínimo**: panel accesible en :9093 con datos de las tareas.
**Comportamiento**: el panel muestra tareas por estado.
**Validación**: curl al panel responde 200.
**Cierre**: panel operativo.
