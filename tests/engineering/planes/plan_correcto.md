# PLAN EJEMPLO 1 — Correcto (referencia)

**Objetivo**: añadir un subcomando `stats` a `scripts/pro/ura-udo` que liste el número de tareas por estado.
**Por qué**: facilita la auditoría de fases sin `list` + conteo manual.
**Contexto**: ura-udo (bash, 564 líneas) tiene `list` y `status`; el patrón de subcomandos está en el `case` principal; suite `tests/udo/test_udo.sh` (35 asserts).
**Qué hacer**: nuevo caso `stats` en el `case` (tras `status`): lee `docs/udo/tasks/*.md`, cuenta por campo `estado:`, imprime tabla.
**Mínimo**: `stats` funciona y lista los 7 estados con conteo; suite 35/35 sin regresión.
**Crítico**: no cambiar la semántica de los estados ni de subcomandos existentes; trazabilidad vía expediente.
**Comportamiento**: `ura-udo stats` imprime `PLANNED: N ... DONE: M` y exit 0.
**NO hacer**: no tocar el gate, no crear infraestructura, no añadir dependencias.
**Fuera de alcance**: gráficos, exportación, métricas históricas.
**Validación**: 1 assert nuevo en test_udo.sh + ejecución manual `ura-udo stats`.
**Cierre**: assert nuevo pasa, suite completa 35/35, commit con [TASK], expediente DONE con analisis/validacion.
