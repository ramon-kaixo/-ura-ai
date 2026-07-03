# Auditoría Técnica — Capa 11 Fase 4/4b (GraphRAG)

> **Fecha:** 2026-07-02  
> **Auditor:** OpenCode  
> **Alcance:** GraphRetriever, ContextBuilder, AssetStore, MemoryStore, LineageStore, GovernanceStore, API `/metadata/context`, CLI, EventBus, subscribers  
> **Tests revisados:** 0 específicos de GraphRAG (no existen); 175 generales pasan, 1 preexistente saltado  

---

## Resumen ejecutivo

**Estado: Requiere cambios**

Se encontraron **3 defectos de severidad alta** y **5 de severidad media**.  
El más grave: **fuga de conexiones (`conn.close()` no se ejecuta en todos los paths de error)** en 3 stores (asset, lineage, governance), lo que puede agotar descriptores de archivo en producción.  
Además, **los eventos MemoryCreated/MemoryUpdated/MemoryLinked están definidos pero NUNCA se emiten**, y los suscriptores de lineage/governance están completamente muertos (`subscribe_all()` no los registra).  
Se recomienda corregir estos defectos antes de iniciar la Fase 5.

---

## 1. Defectos encontrados

### 🔴 Críticos

| ID | Componente | Evidencia | Impacto | Solución |
|---|---|---|---|---|
| **G01** | `lineage_store.py:70` | `pattern = f"%{asset_id}%"` usado en `LIKE ?` | **Falsos positivos en lineage**: `LIKE '%abc%'` matchea `xyzabcdef`. Con 1M+ assets, colisiones de substrings posibles aunque el asset_id tenga 16 hex chars. | Añadir delimitadores al patrón: `LIKE ?` → `pattern = f"%/{asset_id}/%"` o usar `json_each()` con índice sobre `input_ids`/`output_ids`. O mejor: crear tabla `op_lineage_edges(src, dst, relation)` como planifica Fase 7. |

### 🟠 Altos

| ID | Componente | Evidencia | Impacto | Solución |
|---|---|---|---|---|
| **G02** | `asset_store.py:78-80` | `conn.close()` solo en path exitoso. Si `commit()` lanza excepción, la conexión nunca se cierra. Mismo patrón en `lineage_store.py:60` y `governance_store.py:48`. | **Fuga de conexiones SQLite**. En condiciones de error (SQLITE_FULL, SQLITE_BUSY persistente), las conexiones no retornan al pool del OS. Con suficientes errores → `Too many open files`. | Envolver en `try/finally` como ya hace `memory_store.py:110-115`. Mejor aún: crear context manager en `connection.py`. |
| **G03** | `eventbus.py:42-63` | `MemoryCreated`, `MemoryUpdated`, `MemoryLinked` definidos pero `memory_store.py` NUNCA llama a `bus.publish()`. | **Eventos muertos**. Cualquier suscriptor de memoria jamás recibe notificaciones. Roto el contrato EventBus. | Añadir `get_bus().publish(MemoryCreated(...))` en `SQLiteMemoryStore.save()` y análogos. |
| **G04** | `subscribers.py:24-36` | `subscribe_all()` registra archive, audit, metrics, search — pero NO los suscriptores de lineage (`_make_lineage_subscriber()`) ni governance (`_make_governance_subscriber()`). | **Código muerto**: los handlers existen pero nunca se conectan. Lineage y governance post-compile no funcionan. | Añadir `bus.subscribe(CompileCompleted, _make_lineage_subscriber(db_path))` y análogo en `subscribe_all()`. |

### 🟡 Medios

| ID | Componente | Evidencia | Impacto | Solución |
|---|---|---|---|---|
| **G05** | `graphrag.py:203` | `assets = store.list_assets(..., limit=limit * 3)` | **Espacio de búsqueda artificialmente limitado a 30 assets** (los más recientes). Assets antiguos con title-match perfecto nunca se recuperan. | Sin FTS transversal no hay solución trivial. Mitigación en Fase 7: FTS5 en `op_assets`. Por ahora, documentar la limitación. |
| **G06** | `lineage_store.py:70-76` | `LIKE` sobre `input_ids`/`output_ids` (columnas JSON). Sin índice. | **Full table scan** por cada `get_lineage()`. 10K eventos → 10K filas leídas + JSON parse por fila. `retrieve_neighbors()` multiplica por branching factor. | Indexar con `CREATE INDEX idx_op_lineage_inputs ON op_lineage(input_ids)` (no ayuda con LIKE). Solución real: `op_lineage_edges` desnormalizada en Fase 7. |
| **G07** | `memory_store.py:182-196` | Búsqueda LIKE `%query%` en title + content. Sin FTS5. | **Full table scan** por cada búsqueda de memoria. 10K registros → 10K filas escaneadas. | Schema v13 ya incluye `op_memory_fts`. Usarlo: `MATCH ?` en vez de `LIKE`. |
| **G08** | `api.py:488` | `/memory` retorna `total: len(records)` | **Métrica engañosa**: el cliente cree que solo hay N registros cuando hay M > N. | Cambiar a `store.count(kind=kind)` o ejecutar `SELECT COUNT(*)` aparte. |
| **G09** | `api.py:535-541` | `ContextRequest` NO incluye `neighbor_depth` | **Feature gap**: `build_context()` acepta `neighbor_depth` pero la API no lo expone. Vecinos en GraphRAG inaccesibles vía REST. | Añadir `neighbor_depth: int = Field(default=0, ge=0, le=3)` a `ContextRequest`. |

### 🔵 Bajos

| ID | Componente | Evidencia | Impacto | Solución |
|---|---|---|---|---|
| **G10** | `ontology/internal.py:127-129` | `wraps_document()` no-op en frozen dataclass | **Código muerto**: el método no hace nada. Comentario confuso. | Eliminar el método. La intención se cubre con `metadata["wraps"]`. |
| **G11** | `graphrag.py:101-103` | `from dateutil import parser` dentro del cuerpo de `_compute_score()` | **Import inline** innecesario. Penaliza rendimiento en cada llamada. | Mover a imports de módulo (línea 20). |
| **G12** | `graphrag.py:218` | `snippet=a.metadata.get("content_sha256", "")[:64]` | **Snippet inútil**: fragmento de hash SHA-256 no es un snippet significativo. | Usar primeros caracteres del contenido real o del título. |

---

## 2. Riesgos abiertos

| Riesgo | Probabilidad | Impacto | Notas |
|---|---|---|---|
| **R1**: Fuga de conexiones (G02) en producción con errores frecuentes | Baja | Alto | Agotamiento de fd tras N errores consecutivos. |
| **R2**: Falsos positivos en lineage (G01) con 1M+ assets | Baja | Medio | Colisiones de substrings en asset_id. Probabilidad baja con hex 16. |
| **R3**: Búsqueda de assets limitada a N más recientes (G05) | Alta | Medio | Assets antiguos relevantes no se recuperan. |
| **R4**: Latencia de neighbors (G06) con grafo denso | Media | Alto | BFS + full scan por nodo = O(n × b^depth). Depth=3 con branching=10 → 222 full scans. |
| **R5**: Eventos de memoria nunca emitidos (G03) | Alta | Medio | Cualquier suscriptor de memoria que se implemente en Fase 5 no recibirá datos históricos. |

---

## 3. Deuda técnica

| Item | Esfuerzo | Impacto | Notas |
|---|---|---|---|
| **DT1**: Patrón `open_db()` + `try/except` + `conn.close()` duplicado 15× en 4 stores | 1h | Medio | Unificar con context manager `with db_connection(db_path) as conn:` en `connection.py`. |
| **DT2**: `_row_to_asset` y `_row_to_record` duplican lógica de JSON parsing | 30min | Bajo | Extraer helper `_safe_json_load(val, default)` común. |
| **DT3**: `build_context()` 52 líneas con responsabilidades mixtas | 1h | Bajo | Separar: `_build_asset_context()`, `_build_lineage_context()`. |
| **DT4**: Sin tests específicos para GraphRAG, stores, API metadata | 4h | Alto | 0 tests para 4 stores + retriever + 2 endpoints. Cobertura nula. |

---

## 4. Mejoras recomendadas (ordenadas por impacto)

1. **🔴 Corregir fuga de conexiones (G02)** en asset_store, lineage_store, governance_store — adoptar patrón `try/finally` como memory_store. *Estimación: 30min.*
2. **🔴 Publicar eventos de memoria (G03)** en `SQLiteMemoryStore.save()` y `link_asset()`. *Estimación: 15min.*
3. **🔴 Activar suscriptores de lineage/governance (G04)** en `subscribe_all()`. *Estimación: 5min.*
4. **🟡 Cambiar LIKE por FTS5 en memory_store (G07)** usando schema v13. *Estimación: 1h.*
5. **🟡 Añadir `neighbor_depth` a API (G09)** en `ContextRequest`. *Estimación: 10min.*
6. **🟡 Corregir `total` en `/memory` (G08)** para reflejar COUNT real. *Estimación: 10min.*
7. **🟡 Documentar limitación de búsqueda en GraphRAG (G05)** como known issue. *Estimación: 5min.*
8. **🔵 Eliminar código muerto (G10, G11, G12)**. *Estimación: 15min.*
9. **🔵 Escribir tests mínimos (DT4)** para stores + retriever + API endpoints. *Estimación: 4h.*
10. **🔵 Context manager de BD (DT1)** para eliminar duplicación. *Estimación: 1h.*

---

## 5. Validación por categoría

| Categoría | Resultado | Notas |
|---|---|---|
| 1. Funcionalidad | ⚠️ Aprobado con observaciones | G01 (falsos positivos lineage), G05 (recall limitado) |
| 2. Regresiones | ✅ Sin regresiones | API/CLI/Protocols/EventBus backward-compatible |
| 3. Arquitectura | ⚠️ Aprobado con observaciones | G10 (dead code), núcleo no modificado ✅, hexagonal ✅ |
| 4. Rendimiento | ⚠️ Aprobado con observaciones | G05/G06/G07 (bottlenecks conocidos, planificados en Fase 7) |
| 5. Seguridad | ⚠️ Aprobado con observaciones | G02 (fuga conexiones) |
| 6. Determinismo | ✅ Aprobado | Scores varían con tiempo (documentado), orden SQL estable |
| 7. Escalabilidad | ⚠️ Aprobado con observaciones | Degrada con 10K+ eventos/registros |
| 8. Calidad código | ⚠️ Aprobado con observaciones | DT1-DT4 (deuda técnica aceptable) |
| 9. Observabilidad | ❌ Requiere cambios | G03/G04 (eventos no emitidos, suscriptores no registrados) |
| 10. Preparación Fase 5 | ✅ Aprobado | Extractor Protocol + Registry + ExtractionService listos |

---

## 6. Veredicto final

> **Requiere cambios** — No aprobar cierre de Fase 4b hasta corregir G02, G03, G04.

Los defectos G02 (fuga de conexiones), G03 (eventos de memoria no emitidos) y G04 (suscriptores muertos) deben corregirse antes de autorizar la transición a Fase 5. No requieren una reimplementación profunda (< 1h de trabajo total), pero afectan la corrección del sistema y la observabilidad.

Una vez corregidos estos 3 defectos, la fase puede darse por cerrada. G01, G05-G12 son mejoras planificables para Fase 7 o sprints de mantenimiento.

---

*Documento generado por auditoría automática. Corregir defectos marcados como 🔴 antes de iniciar Fase 5.*
