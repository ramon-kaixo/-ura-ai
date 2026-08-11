# Hallazgos del modo de revisión autónoma de fondo

**Política (Engineering Process v1.5 §Modo fondo)**: cuando un agente (WEB/TERM) está en modo de revisión autónoma de fondo y detecta problemas en el código de URA, los registra aquí con su gravedad. La conversación NO es memoria: si un hallazgo no está en este archivo, no existe.

**Gravedad**: `CRÍTICA` (riesgo de seguridad, pérdida de datos, rotura funcional) · `ALTA` · `MEDIA` · `BAJA` · `INFO`

**Reglas**:
- Un hallazgo CRÍTICO además se notifica por `core/notifier.py` (Telegram/Pushover) o se resalta al inicio del siguiente mensaje al humano.
- Todo `ruta:línea` citado debe existir de verdad (verificable con `ls`/`grep`).
- Un hallazgo se marca `estado: abierto | propuesto (con plan) | aprobado | corregido | descartado`.
- **Todo hallazgo accionable (v1.7)** se registra con estado `propuesto (con plan)` y un plan mínimo: QUÉ · POR QUÉ · IMPACTO · VERIFICACIÓN · RIESGO/REVERSIBILIDAD. Se presenta al humano; si se aprueba, se convierte en TASK UDO formal. NO se ejecuta por cuenta propia.
- Un hallazgo se marca `corregido` solo cuando la corrección está hecha y verificada (con commit y evidencia).
- NO se corrige nada desde el modo fondo: los hallazgos se proponen y esperan autorización.

## Hallazgos

| fecha | ruta:línea | hallazgo | gravedad | estado | plan propuesto |
|-------|-----------|----------|----------|--------|----------------|
| 2026-08-11 | core/mochila/router.py:79-87 | El clasificador usa coincidencia simple de palabras clave (`self.patrones` + puntuaciones, líneas 79-87). Si se necesitara mayor precisión en la clasificación, se podría considerar técnicas de NLP más avanzadas. (Corregido por WEB: el hallazgo original citaba línea 93, que corresponde a `return "rapido"`.) | MEDIA | propuesto (con plan) | **QUÉ**: Reemplazar el clasificador actual con un modelo de machine learning que use embeddings para mejorar la precisión de la clasificación de tareas. **POR QUÉ**: El algoritmo simple basado en palabras clave puede dar resultados imprecisos en casos complejos, afectando la selección del proveedor correcto. **IMPACTO**: Los archivos afectados incluirían `core/mochila/router.py`, `core/mochila/_state.py` y `core/mochila/app.py`. Sería un cambio significativo en el comportamiento del sistema pero manteniendo compatibilidad hacia atrás. **VERIFICACIÓN**: Se podría crear una prueba unitaria que verifique los resultados de clasificación antes y después del cambio, comparando métricas como recall y precision en un conjunto de datos etiquetados. **RIESGO/REVERSIBILIDAD**: El riesgo es moderado ya que se necesita asegurar que no se introduzcan regresiones en el comportamiento de selección de modelos. La reversibilidad sería posible con una opción para desactivar la nueva implementación y volver al clasificador original. |
| 2026-08-11 | core/mochila/router.py:130 | El método `route()` llama a `self.clasificador.clasificar()` en la línea 136. Si un clasificador diferente fuera utilizado o redefinido, podría cambiar el comportamiento del sistema sin que se note. | MEDIA | propuesto (con plan) | **QUÉ**: Añadir una capa de verificación o validación al método route para asegurar que la salida de `self.clasificador.clasificar()` cumpla ciertos criterios mínimos y evitar clasificaciones inválidas. **POR QUÉ**: Para prevenir resultados inesperados si unclasificador personalizado no sigue el contrato esperado, lo cual podría afectar la selección incorrecta de modelos. **IMPACTO**: El impacto sería en `core/mochila/router.py` donde se modificaría la función route, aunque solo sería para evitar fallos en condiciones extremas. **VERIFICACIÓN**: Se podría crear una prueba unitaria especializada que pruebe las salidas válidas e inválidas del clasificador para asegurar el correcto manejo de errores. **RIESGO/REVERSIBILIDAD**: Bajo riesgo, se puede revertir simplemente deshabilitando esa capa de verificación si se encuentra algún problema. |

## Progreso

| fecha | carpeta/módulo revisado | resultado |
|-------|------------------------|-----------|
| 2026-08-11 | core/mochila/ | 2 hallazgos nuevos encontrados: uno relativo al clasificador basado en palabras clave y otro sobre validación de salida del clasificador || 2026-08-11 | motor/core/fusion/fact_history.py:351-355 | El TERM (modo fondo) modificó código (formateo) sin autorización — viola la regla v1.7. Detectado y revertido por WEB; despertador reforzado con PROHIBIDO ESCRITURA (TASK-20260812-001). | ALTA | corregido | **QUÉ**: Añadir al mensaje MODO FONDO del despertador un refuerzo explícito: NO ejecutar write/edit/format. **POR QUÉ**: El TERM aplicó ruff-format en un archivo durante la revisión. **IMPACTO**: despertador-fondo.sh + prompt v1.8. **VERIFICACIÓN**: grep del refuerzo en el script. **RIESGO**: bajo, reversible. |
