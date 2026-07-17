# ADR-026-01: Memoria Histórica — Arquitectura

**Estado:** Borrador (pendiente de aprobación)  
**Fase:** F26-B1  
**Depende de:** F25 (v0.25.0-fase25, baseline congelado)  
**No implementar hasta aprobar esta revisión.**

---

## 1. Objetivo de la Memoria Histórica (ADR-026-01)

### ¿Qué problema resuelve?

F25 produce Facts fusionados pero no retiene el **estado del conocimiento a lo largo del tiempo**. Sin Memoria Histórica:
- No se puede responder "¿qué sabía el sistema la semana pasada?"
- No se puede auditar cómo evolucionó un hecho
- No se puede revertir el conocimiento a un estado anterior
- No se puede medir la velocidad de cambio del conocimiento
- No hay un "ahora" conceptual que avance con el tiempo

### ¿Qué NO resuelve?

- ❌ NO es un almacén de episodios conversacionales (eso es F27)
- ❌ NO es un caché de LLM
- ❌ NO es un sistema de archivos de documentos fuente (eso es KE)
- ❌ NO es una base de datos vectorial (puede usarla, pero no la reemplaza)
- ❌ NO es un bus de eventos (aunque use eventos internamente)

### Responsabilidad única

**Preservar, consultar y gestionar la evolución temporal del conocimiento fusionado.**

F26 es el "historial de versiones de la base de conocimiento completa". Cada `MemoryEntry` representa el estado del conocimiento en un instante. La secuencia de entradas forma la línea temporal del conocimiento del sistema.

---

## 2. Modelo Conceptual

### Memory

Contenedor raíz. Es la Memoria Histórica completa. Contiene:
- `MemoryTimeline` (la línea temporal)
- `MemoryPolicy` (reglas de retención)
- `MemoryMetadata` (metadatos del sistema)

### MemoryEntry

Estado del conocimiento en un instante. Una entrada contiene:
- `entry_id: str` — ID determinista
- `timestamp: float` — cuándo se capturó
- `facts: list[tuple[Fact, FactVersion]]` — hechos vigentes en ese instante
- `source: str` — qué originó esta entrada (pipeline, manual, rollback)
- `metadata: MemoryMetadata`

Equivale a: "esto es lo que el sistema sabía en el momento T".

### MemorySnapshot

Captura completa del estado del conocimiento en un instante. Diferencia con `MemoryEntry`:
- `MemoryEntry` es una captura completa del estado
- `MemorySnapshot` es un `MemoryEntry` marcado para retención a largo plazo (no compactable)

Un `MemorySnapshot` es un `MemoryEntry` con `snapshot=True` y política de retención explícita.

### MemoryTimeline

Secuencia ordenada de `MemoryEntry` por timestamp. NO es un historial de versiones de un Fact (eso es FactHistory). MemoryTimeline es el historial global. FactHistory es el historial por Fact.

| Concepto | Alcance | Granularidad | Propietario |
|----------|---------|-------------|-------------|
| FactHistory | Por Fact | Versiones individuales | F25 |
| MemoryTimeline | Global | Estados completos del conocimiento | F26 |

### MemoryEvent

Un evento que ocurre en el sistema y que la memoria registra:

```python
class MemoryEventType(StrEnum):
    FACT_ADDED = "fact_added"
    FACT_UPDATED = "fact_updated"
    FACT_REMOVED = "fact_removed"
    ROLLBACK = "rollback"
    SNAPSHOT = "snapshot"
    COMPACTION = "compaction"
    SYSTEM_EVENT = "system_event"
```

### MemoryReference

Referencia desde Memoria a un objeto externo:
- `fact_id` (a un Fact de F25)
- `version_id` (a una FactVersion de F25)
- `evidence_id` (a un Evidence de F24)
- `document_id` (a un documento fuente)
- `claim_id` (a un Claim de F25)

### MemoryPolicy

Reglas que gobiernan la memoria:

| Política | Defecto | Descripción |
|----------|---------|-------------|
| `retention_days` | 365 | Días que se conserva una entrada normal |
| `snapshot_interval` | 24h | Cada cuánto se fuerza un snapshot |
| `compaction_threshold` | 100_000 | Entradas antes de compactar |
| `max_entries` | 1_000_000 | Máximo de entradas sin compactar |
| `auto_prune` | True | Eliminar entradas fuera de retención |

### MemoryMetadata

Metadatos del sistema sobre una entrada:

```python
@dataclass(frozen=True)
class MemoryMetadata:
    pipeline_version: str
    fusion_config_hash: str
    source_count: int
    fact_count: int
    confidence_avg: float
    created_by: str  # "pipeline" | "manual" | "rollback" | "snapshot"
```

---

## 3. Límites Arquitectónicos

| Capacidad | F25 | F26 | F27 | LLM/Retriever |
|-----------|-----|-----|-----|---------------|
| Fusión de fuentes | ✅ Propietario | — | — | — |
| Identidad de Facts | ✅ Propietario | — | — | — |
| Versionado por Fact | ✅ FactHistory | — | — | — |
| Indexación | ✅ FactIndex | — | — | — |
| Memoria temporal global | — | ✅ Propietario | — | — |
| Snapshots | — | ✅ Propietario | — | — |
| Retención/expiración | — | ✅ Propietario | — | — |
| Compactación | — | ✅ Propietario | — | — |
| Consultas temporales | — | ✅ Propietario | — | — |
| Agentes autónomos | — | — | ✅ Propietario | — |
| Planificación | — | — | ✅ Propietario | — |
| Contexto para LLM | ContextBuilder | — | — | Consumidor |
| Retrieval semántico | — | — | — | Consumidor |
| Evaluación | — | — | — | Consumidor |

**Regla:** Ninguna característica puede tener dos propietarios.

---

## 4. Flujo Completo

```
Documento (F24)
  │
  ▼
Evidence (F24)
  │
  ▼
KnowledgeClaim (F25 - ExtractionStage)
  │
  ▼
KnowledgeFact (F25 - KnowledgeMerger)
  │
  ▼
FactHistory (F25 - por Fact) → MemoryEvent (F26)
  │                                │
  ▼                                ▼
FactIndex (F25 - vigentes)    MemoryEntry (F26 - estado completo)
                                   │
                                   ▼
                              MemoryTimeline (F26)
                                   │
                                   ▼
                              Retriever (F26)
                                   │
                                   ▼
                              ContextBuilder (F26 - extendido)
                                   │
                                   ▼
                              LLM (consumidor final)
```

Cada transición tiene un único propietario:
- `Document → Evidence`: F24
- `Evidence → Claim`: F25
- `Claim → Fact`: F25
- `Fact → FactHistory`: F25
- `FactHistory → MemoryEvent`: F26 (integración)
- `MemoryEvent → MemoryEntry`: F26
- `MemoryEntry → MemoryTimeline`: F26
- `MemoryTimeline → Retriever`: F26
- `Retriever → ContextBuilder`: F26
- `ContextBuilder → LLM`: Consumidor

---

## 5. Invariantes

### Identidad

```
M1. entry_id = SHA-256(timestamp + fact_count + source)[:16]
M2. entry_id es inmutable una vez creado
M3. Dos entradas con el mismo entry_id representan el mismo estado
M4. MemoryEntry.facts contiene solo Facts vigentes en ese instante
```

### Temporalidad

```
M5. MemoryTimeline está ordenada por timestamp (estrictamente creciente)
M6. No existen saltos temporales: t(n) < t(n+1)
M7. MemoryEntry.timestamp coincide con el momento de captura
M8. Un MemoryEntry no puede modificarse después de creado (frozen)
```

### Consistencia

```
M9. MemoryEntry.facts contiene exactamente los Facts que FactIndex tenía en T
M10. No hay Facts huérfanos: todo fact_id en MemoryEntry existe en F25
M11. Tras compactación, no se pierden snapshots
```

### Determinismo

```
M12. Mismos Facts en mismo instante → mismo entry_id
M13. MemoryEntry no depende del orden de inserción
M14. MemoryMetadata es reproducible
```

### Concurrencia

```
M15. MemoryTimeline es append-only (no se modifican entradas existentes)
M16. Las lecturas concurrentes son seguras (dict.get atómico)
M17. Las escrituras deben serializarse externamente
```

### Persistencia

```
M18. MemorySnapshot sobrevive a reinicios del sistema
M19. Compactación no pierde datos (journal + snapshot)
M20. Recuperación tras fallo: replay del journal desde el último snapshot
```

### Reproducibilidad

```
M21. Mismo conjunto de Facts en mismo orden → misma MemoryTimeline
M22. snapshot + journal = estado reconstruible bit a bit
```

---

## 6. Temporalidad: FactHistory vs MemoryTimeline

| Aspecto | FactHistory | MemoryTimeline |
|---------|-------------|----------------|
| Alcance | Un solo Fact | Toda la base de conocimiento |
| Granularidad | Versiones individuales | Estados completos |
| Qué registra | `confidence`, `evidence_ids`, `state` | Todos los Facts vigentes en T |
| Consulta típica | "¿cómo cambió este Fact?" | "¿qué sabía el sistema en T?" |
| Propietario | F25 | F26 |
| Almacenamiento | En memoria (dict) | Persistente (journal + snapshot) |
| Rollback | Reasigna current | Restaura entry completo |
| Compactación | No aplica | Sí (entradas antiguas) |

**No representan el mismo concepto.** FactHistory es interno a F25 (versionado por Fact). MemoryTimeline es la memoria global del sistema.

---

## 7. Política de Actualización

| Operación | Semántica | ¿Crea MemoryEntry? | ¿Modifica FactIndex? |
|-----------|-----------|-------------------|---------------------|
| **append** | Añadir nuevo estado al final de la timeline | ✅ Sí | ❌ No |
| **merge** | Combinar dos entradas consecutivas (compactación) | ✅ Nueva | ❌ No |
| **replace** | Reemplazar una entrada (solo antes de persistir) | ❌ No | ❌ No |
| **expire** | Marcar entrada como fuera de retención | ❌ No | ❌ No |
| **archive** | Mover entrada a almacenamiento de larga duración | ❌ No | ❌ No |
| **delete** | Eliminar entrada permanentemente | ❌ No | ❌ No |
| **rollback** | Restaurar el conocimiento a un entry anterior | ✅ Nueva | ✅ Sí (vía F25) |

**Reglas:**
- `append` es la única operación que añade entries
- `rollback` sobre F25 produce un nuevo FactHistory que, al ser capturado por F26, genera un nuevo MemoryEntry
- `delete` físico es irreversible (solo tras backup)
- `expire` es lógico (la entrada no se elimina, solo se marca)

---

## 8. Persistencia

### Estrategia: Snapshot + Append-Only Journal

```
Estado inicial: vacío
Cada N entries o T tiempo:
  → MemorySnapshot (todos los Facts vigentes)
  → Journal (entries desde el último snapshot)
  → Compactación: journal + snapshot = nuevo snapshot
```

### Formato

- Snapshot: archivo JSON/msgpack con todos los Facts vigentes + metadatos
- Journal: archivo append-only con entries nuevos desde el último snapshot
- Compactación: snapshot nuevo + journal vacío

### Recuperación

```
1. Cargar último snapshot
2. Replay journal (entries después del snapshot)
3. MemoryTimeline = snapshot.entries + journal.entries
```

### Índices persistentes

Los índices de consulta (por entidad, tiempo, evento) se reconstruyen desde la timeline en memoria. Se persisten como archivos separados para acelerar la carga.

---

## 9. Consultas (Diseño)

```python
class MemoryQuery:
    def by_entity(self, entity: str) -> list[MemoryEntry]: ...
    def by_time(self, start: float, end: float) -> list[MemoryEntry]: ...
    def by_event(self, event_type: MemoryEventType) -> list[MemoryEntry]: ...
    def by_source(self, source: str) -> list[MemoryEntry]: ...
    def by_confidence(self, min_conf: float) -> list[MemoryEntry]: ...
    def by_provenance(self, claim_id: str) -> list[MemoryEntry]: ...
    def by_relation(self, fact_id: str) -> list[MemoryEntry]: ...

    # Compuestas
    def state_at(self, timestamp: float) -> MemoryEntry: ...
    def diff(self, entry_a: str, entry_b: str) -> MemoryDiff: ...
    def timeline(self, entity: str) -> list[MemoryEntry]: ...
```

---

## 10. Escalabilidad (Objetivos)

| Volumen | Entry size | RAM estimada | Persistencia |
|---------|-----------|-------------|-------------|
| 10K | ~50 MB | ~10 MB | ✅ Memoria |
| 100K | ~500 MB | ~100 MB | ✅ Memoria |
| 1M | ~5 GB | ~1 GB | ⚠️ Memoria + journal |
| 10M | ~50 GB | ~10 GB | ❌ Solo persistente |
| 100M | ~500 GB | ~100 GB | ❌ Solo persistente |

**Target inicial:** 100K entries en memoria. Más allá de 1M, usar journal + carga bajo demanda.

---

## 11. Concurrencia

**Modelo elegido:** Single Writer + Copy-on-Read

| Operación | Modelo | Justificación |
|-----------|--------|---------------|
| Escritura (append) | Single writer serializado | MemoryTimeline es append-only. Un solo escritor garantiza orden temporal. |
| Lectura (consulta) | Copy-on-read | Las entries son inmutables. Las consultas reciben una copia de la referencia al entry. |
| Compactación | Single writer (exclusivo) | No debe haber lecturas durante compactación para evitar estado inconsistente. |

**Implementación:**
```python
class MemoryTimeline:
    def __init__(self):
        self._entries: dict[str, MemoryEntry] = {}
        self._timeline: list[str] = []
        self._lock = threading.Lock()

    def append(self, entry: MemoryEntry) -> None:
        with self._lock:
            self._entries[entry.entry_id] = entry
            self._timeline.append(entry.entry_id)

    def get(self, entry_id: str) -> MemoryEntry | None:
        return self._entries.get(entry_id)  # seguro: entry es inmutable

    def timeline(self) -> list[MemoryEntry]:
        with self._lock:
            return [self._entries[eid] for eid in self._timeline]
```

---

## 12. Integración con F25

| Componente F25 | Uso en F26 |
|----------------|-----------|
| `FactIndex` | Fuente de Facts vigentes para cada MemoryEntry |
| `FactHistory` | NO se consulta desde F26 (solo F25) |
| `FusionResult.index` | Punto de entrada: cada `FusionResult` produce un `MemoryEvent` |
| `ContextBuilder` | Se extiende para consultar `MemoryTimeline` además de `FactIndex` |
| `Fact`, `FactVersion` | Modelos compartidos (inmutables, sin cambios) |

**NO hay duplicación de almacenamiento:**
- Facts vigentes: los tiene FactIndex (F25)
- Historial por Fact: lo tiene FactHistory (F25)
- Historial global: lo tiene MemoryTimeline (F26)

Cada componente tiene una única responsabilidad y una única fuente de verdad.

---

## 13. Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| **Crecimiento infinito** | Alta | Medio | Política de retención + compactación + snapshot |
| **Duplicación de Facts** | Media | Alto | Referencias a FactIndex, no copias |
| **Pérdida de coherencia** | Baja | Crítico | Journal + snapshot + verificación post-compactación |
| **Fragmentación** | Media | Bajo | Compactación periódica |
| **Coste temporal** | Media | Medio | Append-only O(1), consultas O(log n) con índice |
| **Coste RAM** | Alta | Alto | Más allá de 1M entries, solo persistente |
| **Inconsistencia FactIndex vs MemoryTimeline** | Baja | Crítico | Un único punto de entrada (FusionResult) |

---

## 14. Métricas (Objetivos pre-Implementación)

| Métrica | Target | Cómo se mide |
|---------|--------|-------------|
| `MemoryTimeline.append` latency p50 | <1ms | Benchmarks |
| `MemoryTimeline.append` latency p99 | <5ms | Benchmarks |
| `state_at(timestamp)` latency | <10ms | Benchmarks |
| `timeline(entity)` latency | <50ms | Benchmarks |
| Peak RAM (100K entries) | <150 MB | `tracemalloc` |
| Recovery time (1M entries) | <5s | Medición |
| Compaction throughput | >10K entries/s | Medición |
| Journal growth rate | <1MB/hora normal | Medición |

---

## 15. Criterios de Aceptación

F26 no se cerrará sin demostrar E2E que:

```
Document (F24)
  → Evidence (F24)
    → KnowledgeFact (F25)
      → MemoryEntry (F26)
        → MemoryTimeline (F26)
          → Retriever query (F26)
            → ContextBuilder output (F26)
              → LLM prompt (consumidor)
```

**Criterios específicos:**

| # | Criterio | Cómo se demuestra |
|---|----------|-------------------|
| 1 | Un Fact producido por F25 llega a MemoryTimeline | Test E2E: pipeline.run() → Memory.append() → timeline contiene el Fact |
| 2 | Se puede consultar el estado en un instante pasado | Test: state_at(t) retorna los Facts vigentes en t |
| 3 | Rollback en F25 genera un nuevo MemoryEntry | Test: F25 rollback → F26 captura el cambio |
| 4 | Compactación preserva snapshots | Test: compactación → snapshots intactos |
| 5 | Recuperación tras fallo | Test: snapshot + journal → mismo estado que antes |
| 6 | ContextBuilder puede consultar memoria histórica | Test: query temporal → facts formateados para LLM |
| 7 | Sin regresiones en F25 baseline | `pytest -q` contra tests de F25 |
| 8 | Sin regresiones en benchmarks de F25 | Benchmarks de F25 siguen pasando |

---

## Resumen para Aprobación

| Entregable | Estado |
|-----------|--------|
| 1. ADR-026-01 (Objetivo) | ✅ Definido |
| 2. Modelo conceptual | ✅ 8 conceptos definidos |
| 3. Límites arquitectónicos | ✅ Tabla F25/F26/F27/LLM |
| 4. Flujo completo | ✅ 11 transiciones, propietario único cada una |
| 5. Invariantes | ✅ 22 invariantes (7 categorías) |
| 6. Temporalidad | ✅ FactHistory ≠ MemoryTimeline |
| 7. Política de actualización | ✅ 7 operaciones con semántica formal |
| 8. Persistencia | ✅ Snapshot + journal + compactación |
| 9. Consultas | ✅ 8 tipos de consulta diseñados |
| 10. Escalabilidad | ✅ Objetivos 10K–100M |
| 11. Concurrencia | ✅ Single writer + copy-on-read |
| 12. Integración | ✅ Tabla de integración con F25 |
| 13. Riesgos | ✅ 7 riesgos identificados |
| 14. Métricas | ✅ 8 métricas con target |
| 15. Criterios aceptación | ✅ 8 criterios E2E |

---

**Pendiente de aprobación para comenzar implementación de F26-B2.**
