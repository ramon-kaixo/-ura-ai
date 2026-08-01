# Resolucion de conflictos Fase 5 — Preparado

## Archivos afectados

| Archivo | Conflicto | Resolucion |
|---------|-----------|------------|
| tests/integration/test_api.py | Eliminado por OpenCode | Recuperar nuestros 8 tests funcionales |
| tests/unit/test_path_setup.py | Movido + reescrito | Merge manual: nuestros 4 tests + notifier/json_logger de OpenCode |
| tests/unit/test_ura_maintenance.py | Vacio en main, eliminado | Sin accion |
| tests/unit/test_router_handler.py | Eliminado por OpenCode | Sin accion |

## Instrucciones post-merge

1. Copiar docs/merge_resolution/test_api.py → tests/integration/test_api.py
2. Copiar docs/merge_resolution/test_path_setup.py → tests/test_path_setup.py
3. Eliminar tests/unit/test_path_setup.py (duplicado)
4. Ejecutar suite completa: pytest tests/ -q
5. Si todo verde → commit fix(merge): resolver conflictos Fase 5
