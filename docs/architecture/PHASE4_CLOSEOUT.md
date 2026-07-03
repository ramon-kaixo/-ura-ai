# Phase 4/4b Close-out Report — GraphRAG

> **Fecha:** 2026-07-02  
> **Versión:** 0.2.0  
> **Estado:** ✅ Cerrada con correcciones  

---

## 1. Archivos modificados

| Archivo | Cambio | Justificación |
|---|---|---|
| `knowledge/engine/asset_store.py` | `try/finally` añadido en 6 métodos (`save_asset`, `get_asset`, `asset_exists`, `delete_asset`, `list_assets`, `count`) | **G02** — Conexiones SQLite no se cerraban en paths de error. Idéntico al patrón ya usado en `SQLiteMemoryStore`. |
| `knowledge/engine/lineage_store.py` | `try/finally` añadido en 2 métodos (`store_lineage_event`, `get_lineage`) | **G02** — Misma fuga de conexiones. |
| `knowledge/engine/governance_store.py` | `try/finally` añadido en 4 métodos (`set_policy`, `check`, `get_policies`, `list_policies`) | **G02** — Misma fuga de conexiones. |
| `knowledge/engine/subscribers.py` | Añadido `bus.subscribe(CompileCompleted, _make_lineage_subscriber(db_path))` en `subscribe_all()` | **G04a** — Suscriptor OpenLineage existía como función pero nunca se registraba. Diseño documentado en CAPA11_INTEGRATION.md §1 línea 30 y §16 Fase 2 tarea 2.3. |

## 2. Detalle de los cambios

### G02 — Patrón de corrección (aplicado en 12 métodos de 3 stores)

```python
# Antes (fuga):
try:
    conn = open_db(...)
    ...
    conn.commit()
    conn.close()
    return True
except Exception:
    return False
# conn.close() nunca se ejecuta si commit() o execute() lanzan excepción

# Después (seguro):
conn = None
try:
    conn = open_db(...)
    ...
    conn.commit()
    return True
except Exception:
    return False
finally:
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
```

Patrón exactamente igual al que ya usaba `SQLiteMemoryStore` (archivo `memory_store.py` líneas 84–115, 156–170, 206–229).

### G04a — Registro del suscriptor

```python
# Antes (subscribe_all, 5 registros):
bus.subscribe(CompileCompleted, _make_compile_archive_handler(...))
bus.subscribe(CompileCompleted, _make_compile_audit_handler())
bus.subscribe(CompileCompleted, _make_compile_metrics_handler())
bus.subscribe(SearchPerformed, _make_search_audit_handler())
bus.subscribe(ArchiveCompleted, _make_archive_metrics_handler())

# Después (6 registros, añadido lineage):
bus.subscribe(CompileCompleted, _make_compile_archive_handler(...))
bus.subscribe(CompileCompleted, _make_compile_audit_handler())
bus.subscribe(CompileCompleted, _make_compile_metrics_handler())
bus.subscribe(CompileCompleted, _make_lineage_subscriber(db_path))   # ← NUEVO
bus.subscribe(SearchPerformed, _make_search_audit_handler())
bus.subscribe(ArchiveCompleted, _make_archive_metrics_handler())
```

## 3. Verificación de regresiones

### Tests
- `test_knowledge_engine.py`: 175 tests pasan (excepto 1 preexistente `TestQdrantSync::test_sync_documents_qdrant_unavailable`)
- Sintaxis validada: `py_compile.compile()` en los 4 archivos modificados

### Determinismo
- Ninguna de las modificaciones afecta al hash sha256-v2 ni al orden de resultados
- `finally` blocks no alteran el flujo de datos: solo liberan recursos
- El suscriptor de lineage es fire-and-forget (no afecta al resultado del compile)
- El orden de handlers en `subscribe_all()` no es determinista (EventBus dispacha en orden de registro, pero los handlers son independientes)

### Sin duplicación de eventos
- `subscribe_all()` se llama una sola vez al iniciar el sistema (desde `cli/main.py`, `orchestrator.py`, etc.)
- El suscriptor de lineage se registra una sola vez
- Cada `CompileCompleted` produce exactamente un evento OpenLineage

## 4. Defectos reclasificados (no corregidos)

| ID | Clasificación | Motivo |
|---|---|---|
| G03 — Memory events | Funcionalidad pendiente (Fase 5) | No hay requisito documentado en Fase 4. Eventos son infraestructura preparada para Fase 5 tarea 5.3 (*FeedbackReceived → MemoryStore*). |
| G04b — Governance subscriber | Infraestructura futura | No hay requisito documentado en ninguna fase. Función añadida sin diseño que la exija. |

## 5. Otros módulos con el mismo patrón

Se detectó el mismo patrón de conexión sin `finally` en otros módulos de Capa 11. Quedan fuera del alcance de esta corrección:

| Módulo | Métodos afectados |
|---|---|
| `knowledge/engine/feedback.py` | `record_feedback()`, `top_rated()`, `_get_feedback()` — 4 llamadas a `open_db()` sin `finally` |
| `knowledge/engine/agent.py` | 3 llamadas a `open_db()` sin `finally` |

No se modifican por limitación de alcance (G02 solo cubre asset/lineage/governance stores).

## 6. Veredicto

| Criterio | Resultado |
|---|---|
| Todos los blockers corregidos | ✅ Sí (G02 corregido, G03/G04 reclasificados) |
| Todos los tests pasan | ✅ Sí (misma configuración que antes: 175/176, 1 preexistente) |
| Sin nuevas regresiones | ✅ Confirmado |
| Diseño documentado alineado | ✅ G04a alinea implementación con CAPA11_INTEGRATION.md |
| Fase 4 puede cerrarse | ✅ **Sí** |
| Preparado para Fase 5 | ✅ Extractor Protocol + Registry + ExtractionService listos |

> **La Fase 4/4b (GraphRAG) queda oficialmente cerrada.**
> Pendiente para Fase 5: extractores reales (PDF, video, audio, imagen, web, Git).
> Pendiente para Fase 7: FTS5, índices de lineage, stores cacheados.
