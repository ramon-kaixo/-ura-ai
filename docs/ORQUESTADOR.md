# Orquestador de tareas

**Fecha:** 2026-08-05
**Script:** `scripts/pro/orquestador.py`
**Formato de tarea:** `data/tasks/TEMPLATE.json`

## Pipeline de 8 fases

1. **contexto** — archivos del módulo + verificación de memoria
2. **planificacion** — descompone el objetivo en pasos
3. **implementacion** — verifica que hay cambios en el working tree
4. **revision** — ruff check sobre el módulo
5. **tests** — pytest tests/unit
6. **auditoria** — auditoria_paralela (10 checks)
7. **quality_gate** — evaluar con reporte de prueba
8. **commit** — SKIP (decisión humana, ADR-221)

Si una fase falla, el orquestador **para** y guarda el log en `data/orquestador_logs/`.

## Uso

```bash
cp data/tasks/TEMPLATE.json data/tasks/mi-tarea.json
# editar id/objetivo/modulo
python3 scripts/pro/orquestador.py data/tasks/mi-tarea.json
```

## Ejecución parcial (para desarrollo)

```python
from scripts.pro.orquestador import ejecutar_tarea
report = ejecutar_tarea(tarea, fases=["contexto", "planificacion", "commit"])
```
