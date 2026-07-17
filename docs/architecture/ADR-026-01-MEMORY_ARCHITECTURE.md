# ADR-026-01: Memoria Histórica — Arquitectura (v2)

**Estado:** Aprobado con cambios  
**Fecha:** 2026-07-17  
**Fase:** F26-B1  
**Depende de:** F25 (v0.25.0-fase25, baseline congelado)  
**CR resueltos:** CR-01 a CR-10  

---

## 1. Objetivo de la Memoria Histórica

### ¿Qué problema resuelve?

F25 produce Facts fusionados pero no retiene el **estado del conocimiento a lo largo del tiempo**. Sin Memoria Histórica no se puede responder "¿qué sabía el sistema la semana pasada?", auditar la evolución del conocimiento, revertir a un estado anterior, ni medir la velocidad de cambio.

### ¿Qué NO resuelve?

- ❌ NO es almacén de episodios conversacionales (F27)
- ❌ NO es caché de LLM
- ❌ NO es sistema de archivos de documentos fuente (KE)
- ❌ NO es base de datos vectorial
- ❌ NO es bus de eventos

### Responsabilidad única

**Preservar, consultar y gestionar la evolución temporal del conocimiento fusionado.**

F26 registra el estado del conocimiento en instantes discretos (MemoryEntry). La secuencia de entradas forma la línea temporal del conocimiento. **MemoryTimeline NO es fuente de verdad del conocimiento — esa función pertenece a FactHistory (F25).** MemoryTimeline es únicamente un registro de la evolución temporal.

---

## 2. Fuente de Verdad (CR-01)

| Verdad | Reside en | Propietario |
|--------|-----------|-------------|
| ¿Cuál es la versión vigente de un Fact? | `FactHistory.current` | **F25** |
| ¿Cuál es el historial de versiones de un Fact? | `FactHistory.versions` | **F25** |
| ¿Cuál era el estado completo del conocimiento en T? | `MemoryTimeline.state_at(T)` | **F26** |
| ¿Cómo evolucionó el conocimiento entre T1 y T2? | `MemoryTimeline.diff(T1, T2)` | **F26** |

**Decisión:** FactHistory es la única fuente de verdad para Facts. MemoryTimeline es una **proyección temporal indexada** — replica referencias, no datos. Si FactHistory y MemoryTimeline discrepan, FactHistory prevalece.

**Implicación:** MemoryTimeline nunca se usa para responder "¿cuál es el Fact vigente ahora?". Esa pregunta se responde con FactIndex (F25). MemoryTimeline solo responde "¿cuál era el Fact vigente en T?".

---

## 3. Modelo Conceptual

### Memory

Contenedor raíz. Contiene `MemoryTimeline`, `MemoryPolicy`, `MemoryMetadata`.

### MemoryEntry (CR-02)

**NO contiene Facts.** Contiene únicamente **referencias** inmutables a Facts y FactVersion:

```python
@dataclass(frozen=True)
class MemoryEntry:
    entry_id: str                     # SHA-256 determinista (CR-08)
    timestamp: float                  # instante de observación (CR-03)
    fact_refs: tuple[FactRef, ...]    # referencias, NO Facts (CR-02)
    source: str                       # qué originó esta entrada
    event_type: MemoryEventType       # tipo de evento
    metadata: MemoryMetadata
    snapshot: bool = False            # si es un snapshot retenible

@dataclass(frozen=True)
class FactRef:
    """Referencia inmutable a una versión concreta de un Fact.

    Contiene exactamente:
    - fact_id: identidad del Fact (F25)
    - version_id: versión concreta (F25)
    - subject, predicate, object: desnormalizados para consulta
      sin cruzar a F25 (copia del Fact, no fuente de verdad)

    NO contiene history_id (se deriva de fact_id).
    NO contiene el FactVersion completo (solo referencia).
    Las referencias son inmutables y no actualizables.
    """
    fact_id: str
    version_id: str
    subject: str
    predicate: str
    object: str
```

**Regla:** `MemoryEntry` no mezcla conceptos. Una entrada es un registro de referencias. Los eventos se registran por separado en `MemoryEvent`.

### MemorySnapshot

Un `MemoryEntry` con `snapshot=True`. Se diferencia de un `MemoryEntry` normal en que:
- No es compactable
- Tiene política de retención explícita (por defecto: no expirar)
- Sirve como punto de recuperación

### MemoryTimeline

Secuencia ordenada de `entry_id` por timestamp. **NO almacena Facts ni versions.** Solo índices temporales.

```
MemoryTimeline
├── _by_time: SortedList[tuple[float, str]]  # (timestamp, entry_id)
├── _by_entity: dict[str, list[str]]          # entity → entry_ids
├── _by_event: dict[str, list[str]]           # event_type → entry_ids
└── _entries: dict[str, MemoryEntry]          # entry_id → entry
```

### MemoryEvent

Evento atómico que originó un `MemoryEntry`:

```python
class MemoryEventType(StrEnum):
    FACT_ADDED = "fact_added"
    FACT_UPDATED = "fact_updated"
    FACT_REMOVED = "fact_removed"
    ROLLBACK = "rollback"
    SNAPSHOT = "snapshot"
    COMPACTION = "compaction"
    SYSTEM = "system_event"
```

### MemoryReference

Referencia desde F26 a objetos de F25:
- `fact_id` + `version_id` (a FactVersion de F25)
- `claim_id` (a KnowledgeClaim de F25)
- `evidence_id` (a Evidence de F24)

Todas las referencias son inmutables.

### MemoryPolicy

| Política | Defecto | Descripción |
|----------|---------|-------------|
| `snapshot_interval_entries` | 10_000 | Cada N entradas se fuerza snapshot |
| `snapshot_interval_seconds` | 86400 | Cada 24h se fuerza snapshot |
| `compaction_max_entries` | 1_000_000 | Máximo de entradas antes de compactar |
| `retention_days` | 365 | Días de retención para entradas normales |
| `snapshot_retention` | forever | Los snapshots no expiran |
| `auto_prune` | True | Eliminar entradas fuera de retención al compactar |

### MemoryMetadata

```python
@dataclass(frozen=True)
class MemoryMetadata:
    pipeline_version: str
    fusion_config_hash: str
    fact_count: int
    confidence_avg: float
    created_by: str  # "pipeline" | "manual" | "rollback" | "snapshot" | "compaction"
```

---

## 4. Semántica Temporal (CR-03)

MemoryEntry.timestamp representa el **instante de observación**: cuándo F26 capturó el estado del conocimiento.

| Concepto | Significado | Quién lo asigna |
|----------|-------------|-----------------|
| **Instante de observación** | Cuándo F26 capturó el estado | F26 (time.time() en el momento de append) |
| **Instante de ingestión** | Cuándo el documento fuente fue ingerido | `Evidence.fetched_at` (F24) |
| **Instante de validez** | Cuándo el hecho era verdadero (si aplica) | No lo gestiona F26 — es semántica externa |
| **Instante del evento** | Cuándo ocurrió el cambio en el conocimiento | `MemoryEvent.timestamp` (≈ instante de observación) |

**Regla:** F26 solo garantiza el instante de observación. Los instantes de ingestión y validez se conservan en los modelos de F24/F25 (`Evidence.fetched_at`, `FactVersion.created_at`). F26 nunca asigna ni modifica esos timestamps.

**Invariante:** `MemoryTimeline` está ordenada estrictamente por instante de observación creciente. No existen saltos temporales.

---

## 5. FactHistory vs MemoryTimeline (CR-01 + CR-06)

| Aspecto | FactHistory (F25) | MemoryTimeline (F26) |
|---------|-------------------|---------------------|
| **Fuente de verdad** | ✅ SÍ — para versiones de un Fact | ❌ NO — solo registro temporal |
| **Alcance** | Un solo Fact | Toda la base de conocimiento |
| **Granularidad** | Versiones individuales | Estados completos en instantes discretos |
| **Qué contiene** | FactVersion (contenido completo) | FactRef (referencias, no contenido) |
| **Consulta típica** | "¿cómo cambió este Fact?" | "¿qué sabía el sistema en T?" |
| **Propietario** | F25 | F26 |
| **state_at(T)** | O(k) recorriendo supersedes | **O(log n)** con índice temporal |
| **Almacenamiento** | En memoria (dict) | Persistente (journal + snapshot) |
| **Rollback** | Reasigna current | Registra el cambio como nuevo entry |
| **Compactación** | No aplica | Sí, sobre entries antiguos |

**No representan el mismo concepto ni pueden confundirse.** Uno es versionado por Fact (F25). El otro es evolución global del conocimiento (F26).

---

## 6. Persistencia (CR-04)

### Estrategia: Snapshot + Append-Only Journal

```
[MemoryTimeline en memoria]
       │
       ├── cada N entries o T tiempo ──→ MemorySnapshot (disco)
       │
       └── cada append ──→ Journal (disco, append-only)
```

### Snapshot

- **Frecuencia:** cada 10.000 entries o 24h (lo que ocurra primero)
- **Contenido:** Todos los `MemoryEntry` desde el último snapshot + metadatos
- **Formato:** JSON (legible) o msgpack (rápido) — decisión de implementación
- **Atomicidad:** Se escribe a un archivo temporal y se renombra (`os.rename`)

**Versión de esquema del snapshot (CR-14):**

```python
SNAPSHOT_SCHEMA_VERSION = 1

@dataclass(frozen=True)
class SnapshotHeader:
    schema_version: int = SNAPSHOT_SCHEMA_VERSION
    snapshot_version: str       # ej: "v26.1.0-snapshot-001"
    checksum: str               # SHA-256 del contenido completo
    creation_time: float        # timestamp de creación del snapshot
    compatible_from: str        # versión mínima de F26 compatible
    entry_count: int            # número de entries en este snapshot
    journal_offset: int         # posición del journal al crear el snapshot
```

**Migración futura:** Si `SNAPSHOT_SCHEMA_VERSION` cambia, la función `load_snapshot()` aplica transformaciones. No hay migraciones destructivas.

### Journal

- **Formato:** JSON Lines (una entrada por línea)
- **Róta** con cada snapshot (el journal anterior se compacta en el snapshot)
- **Tamaño máximo:** 10.000 entries entre snapshots (~50 MB)

### Compactación

- **Cuándo:** Al superar `compaction_max_entries` (1M)
- **Qué hace:** Toma el último snapshot + journal → nuevo snapshot → journal vacío
- **Coste máximo:** O(n) donde n = entries desde el último snapshot
- **Consistencia:** No hay lecturas durante compactación (single writer lock)

### Recuperación tras fallo

```
1. Cargar último snapshot completo
2. Replay journal (entries después del snapshot, en orden)
3. Reconstruir índices temporales (_by_time, _by_entity, _by_event)
4. Verificar: count(snapshot) + count(journal) == count(MemoryTimeline)
```

**Coste máximo de recuperación para 1M entries:** < 5s (objetivo)

**Consistencia durante snapshot:** El snapshot se escribe atómicamente (rename). Si el proceso falla durante la escritura, el archivo temporal se descarta y el próximo reinicio usa el snapshot anterior + journal completo.

---

## 7. Concurrencia (CR-05)

### Modelo: Single Writer + Copy-on-Read

| Operación | Modelo | Responsable |
|-----------|--------|-------------|
| `append()` | Single writer (lock exclusivo) | `Memory.append()` |
| `state_at()` | Lectura concurrente (sin lock) | Memoria |
| `timeline()` | Lectura concurrente (sin lock) | Memoria |
| `compact()` | Single writer (lock exclusivo, without lecturas) | `Memory.compact()` |

### ¿Quién posee el writer?

El **proceso que ejecuta `Memory.append()`**. En el caso nominal, es el mismo proceso que ejecuta `FusionPipeline.run()`. No hay writer remoto ni distribuido en F26.

### Arbitración de múltiples productores

Si múltiples pipelines ejecutan en paralelo, cada uno produce su propio `FusionResult`. Un `MemoryConsumer` serializa los resultados y llama a `append()` secuencialmente. El writer lock garantiza orden temporal.

### Comportamiento ante reinicio

La memoria se reconstruye desde el último snapshot + journal. No hay estado en memoria que sobreviva al reinicio del proceso.

### Comportamiento distribuido futuro (post-F26)

Si en el futuro hay múltiples procesos escribiendo:
1. Cada proceso tiene su propio journal
2. Un proceso centralizado (MemoryServer) consolida los journals
3. Los timestamps de observación se asignan en el servidor, no en los productores

**Esto no se implementa en F26.** Se documenta como posible evolución.

---

## 8. MemoryEntry: Identidad Estable (CR-08)

```python
def make_entry_id(event_type: str, fact_version_ids: list[str], timestamp: float) -> str:
    """ID determinista de MemoryEntry basado en contenido canónico.

    Participan:
    - event_type: tipo de evento (string canónico)
    - fact_version_ids: TODOS los version_id referenciados, ordenados (sorted)
    - timestamp: instante de observación (int)

    NO participa la posición en MemoryTimeline.
    NO participan metadatos agregados (fact_count, confidence_avg).

    Garantías:
    - Mismo contenido en mismo instante → mismo entry_id
    - Dos eventos con mismo timestamp pero diferente contenido → IDs diferentes
    - Idempotente: reordenar fact_version_ids no cambia el ID (están sorted)
    """
    sorted_ids = sorted(fact_version_ids)
    raw = f"{event_type}:{','.join(sorted_ids)}:{int(timestamp)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
```

**Garantías:**
- `entry_id` es independiente de la posición en la timeline
- Mismo estado en mismo instante → mismo entry_id
- `entry_id` no cambia aunque se reordene la timeline
- La posición en la timeline NO es parte de la identidad

---

## 9. Política de Eliminación (CR-09)

### Principio General

La retención elimina información operativa. **Nunca elimina información necesaria para reproducibilidad o auditoría.** MemorySnapshot y journal se conservan aunque superen el período de retención, siempre que exista espacio en disco.

### Política por tipo

| Elemento | ¿Cuándo se elimina? | ¿Cómo? | ¿Afecta a auditoría? |
|----------|---------------------|--------|----------------------|
| **MemoryEntry** normal | Tras `retention_days` sin pertenecer a un snapshot | Marcado como `expired` + excluido de consultas. DELETE físico en compactación. | ❌ No, si existe un snapshot que lo cubra |
| **MemorySnapshot** | Nunca (retención permanente) | No se elimina | ✅ Los snapshots son la base de la auditoría |
| **Journal** | Con cada snapshot | El journal anterior se descarta tras confirmar el snapshot | ✅ El snapshot resultante contiene toda la información del journal |
| **Referencias a Fact** | Nunca (son solo strings) | No aplica — las referencias son inmutables | ✅ Las referencias persisten aunque el entry expire |
| **Índices temporales** | Al expirar un entry | Reconstruidos durante compactación | ❌ Los índices son reconstruibles desde entries no expirados |
| **Archivo de snapshot** | Nunca (retención permanente) | Conservado incluso tras compactación | ✅ Base para reconstrucción histórica |

### Excepciones a la retención

- **Auditorías activas:** Si existe una investigación o auditoría en curso que requiera entries fuera del período de retención, esos entries se marcan como `protected` y no se eliminan.
- **Reconstrucciones históricas:** Para reconstruir el estado en T, se necesita:
  1. El snapshot inmediatamente anterior a T
  2. Todos los entries entre ese snapshot y T
  Si alguno de esos entries fue eliminado, la reconstrucción no es posible.
- **Protección:** Los snapshots NUNCA se eliminan automáticamente. Solo por decisión explícita del operador.

**DELETE físico es irreversible.** Solo ocurre durante compactación y siempre tras backup implícito (el snapshot anterior sigue existiendo hasta el próximo ciclo).

---

## 10. Escalabilidad con Presupuesto RAM (CR-07)

| Volumen | Entry size | RAM (entries) | RAM (índices) | RAM total | Estrategia |
|---------|-----------|---------------|---------------|-----------|------------|
| 10K | ~150 KB | ~1.5 MB | ~0.5 MB | ~2 MB | ✅ Memoria |
| 100K | ~1.5 MB | ~15 MB | ~5 MB | ~20 MB | ✅ Memoria |
| 1M | ~15 MB | ~150 MB | ~50 MB | ~200 MB | ⚠️ Memoria + journal |
| 10M | ~150 MB | ~1.5 GB | ~500 MB | ~2 GB | ❌ Solo persistente |
| 100M | ~1.5 GB | ~15 GB | ~5 GB | ~20 GB | ❌ Solo persistente |

**Cálculo por entry:**
- `entry_id` (16 chars): ~50 bytes
- `timestamp` (float): 24 bytes
- `fact_refs` (promedio 50 referencias): 50 × ~200 bytes = ~10 KB
- `source` (string): ~50 bytes
- `metadata`: ~200 bytes
- Overhead dict: ~100 bytes
- **Total por entry:** ~150 bytes + 10 KB de referencias

**Target inicial:** 100K entries en memoria (~20 MB RAM).  
**Límite superior sin persistencia:** 1M entries (~200 MB RAM).  
**Más allá de 1M:** solo persistente (journal + snapshot + carga bajo demanda).

---

## 11. state_at(timestamp) — Complejidad O(log n) (CR-06)

```python
def state_at(self, timestamp: float) -> MemoryEntry | None:
    """Retorna el MemoryEntry vigente en el instante dado.

    Regla de desempate (CR-13):
    Si múltiples entries tienen el mismo observation_timestamp,
    prevalece el de mayor entry_id (orden lexicográfico inverso).
    Esto garantiza determinismo incluso con timestamps duplicados.

    Complejidad: O(log n) donde n = número de entries.
    """
    idx = self._timeline.bisect_right((timestamp, "\uffff")) - 1
    if idx < 0:
        return None
    _, entry_id = self._timeline[idx]
    return self._entries.get(entry_id)
```

**Garantía:** `state_at()` es O(log n). Se implementa sobre una **estructura ordenada con búsqueda O(log n)** (no se acopla a una implementación concreta: puede ser `bisect` sobre lista ordenada, `SortedList`, B-tree, o índice de base de datos). No hay recorrido lineal de la timeline.

---

## 12. Consultas

```python
class MemoryQuery:
    def state_at(self, ts: float) -> MemoryEntry | None          # O(log n)
    def by_entity(self, entity: str) -> list[MemoryEntry]        # O(1) + O(m)
    def by_time(self, start: float, end: float) -> list[MemoryEntry]  # O(log n + m)
    def by_event(self, event_type: str) -> list[MemoryEntry]     # O(1) + O(m)
    def by_source(self, source: str) -> list[MemoryEntry]        # O(1) + O(m)
    def diff(self, entry_a: str, entry_b: str) -> MemoryDiff     # O(a + b)
    def timeline(self, entity: str) -> list[MemoryEntry]         # O(1) + O(m)
```

---

## 13. Invariantes de F26 (CR-10)

### Identidad

```
M01. entry_id = SHA-256(event_type + sorted(fact_version_ids) + timestamp)[:16]
M02. entry_id es inmutable. No depende de la posición en la timeline.
M03. Dos entries con el mismo entry_id representan el mismo registro de observación.
M04. entry_id NO se deriva de metadatos agregados (fact_count, confidence_avg).
```

### Fuente de verdad

```
M04. MemoryTimeline NO es fuente de verdad del conocimiento.
     La fuente de verdad es FactHistory (F25).
M05. MemoryTimeline solo contiene referencias (FactRef), nunca Facts completos.
M06. Si MemoryTimeline y FactHistory discrepan, FactHistory prevalece.
```

### Temporalidad

```
M07. MemoryTimeline está ordenada por instante de observación estrictamente creciente.
M08. timestamp = instante de observación (no de ingestión, no de validez).
M09. No existen saltos temporales: t(n) < t(n+1).
M10. Un MemoryEntry no puede modificarse después de creado (frozen).
```

### Consistencia

```
M11. Toda referencia (fact_id, version_id) en MemoryTimeline existe en F25.
M12. Tras compactación, no se pierden snapshots.
M13. Tras expiración, las referencias se eliminan de índices (no de F25).
```

### Concurrencia

```
M14. MemoryTimeline es append-only. No se modifican entries existentes.
M15. append() requiere lock exclusivo.
M16. state_at() y consultas son seguras sin lock (entries inmutables).
```

### Persistencia

```
M17. MemorySnapshot sobrevive a reinicios del sistema.
M18. count(snapshot) + count(journal) == count(MemoryTimeline) tras recuperación.
M19. La recuperación es bit-a-bit reproducible desde snapshot + journal.
```

### Rendimiento

```
M20. state_at() es O(log n).
M21. append() es O(1) amortizado.
M22. by_entity() es O(1) + O(m) donde m = resultados.
```

---

## 14. Integración con F25

| Componente F25 | Uso en F26 | Naturaleza |
|---------------|-----------|-----------|
| `FusionResult.index` (FactIndex) | Punto de entrada: produce MemoryEntry con FactRefs | Lectura |
| `FactHistory` | NO se consulta desde F26 | — |
| `Fact`, `FactVersion` | Modelos referenciados via FactRef (solo strings) | Referencia |
| `ContextBuilder` | Se extiende para consultar MemoryTimeline | Extensión |
| `make_fact_id` | Se usa para construir FactRef | Herramienta |

**No hay duplicación de almacenamiento. No hay ownership compartido.**

---

## 15. Riesgos

| Riesgo | Prob | Impacto | Mitigación |
|--------|------|---------|-----------|
| Crecimiento infinito | Alta | Medio | Política de retención + compactación + snapshot |
| Duplicación de referencias | Media | Bajo | entry_id determinista (mismo estado → mismo ID) |
| Pérdida de coherencia tras fallo | Baja | Crítico | snapshot atómico + journal replay + verificación |
| Contención de writer | Baja | Medio | append O(1), journal asíncrono |
| Coste RAM > 200 MB | Media | Alto | A 1M entries, migrar a solo persistente |
| Inconsistencia FactIndex vs MemoryTimeline | Baja | Crítico | Un único punto de entrada (FusionResult), sin modificación externa |

---

## 16. Métricas

| Métrica | Target | Cómo se mide |
|---------|--------|-------------|
| `append()` latency p50 | <1ms | time.perf_counter() |
| `append()` latency p99 | <5ms | time.perf_counter() |
| `state_at()` latency | <1ms (O(log n)) | time.perf_counter() |
| `by_entity()` latency (100K entries) | <10ms | time.perf_counter() |
| Peak RAM (100K entries) | <150 MB | tracemalloc |
| Recovery time (1M entries) | <5s | time.perf_counter() |
| Journal growth rate | <1 MB/h | Medición en CI |

---

## 17. Criterios de Aceptación para Cierre de F26

| # | Criterio | Cómo se demuestra |
|---|----------|-------------------|
| 1 | Fact → MemoryEntry con referencias (no Facts duplicados) | Test: entry.fact_refs contiene strings, no Fact objects |
| 2 | `state_at(T)` retorna el estado correcto en T | Test: 3 entries en T1<T2<T3 → state_at(T1.5) = entry en T1 |
| 3 | Rollback en F25 → nuevo MemoryEntry en F26 | Test: F25 rollback → F26 captura como entry nuevo |
| 4 | Compactación preserva snapshots | Test: compact → snapshot intacto |
| 5 | Recuperación desde snapshot + journal | Test: crash simulado → mismo estado |
| 6 | Sin regresiones en F25 baseline | pytest F25 completo |
| 7 | Sin regresiones en benchmarks F25 | Benchmarks F25 pasan |
| 8 | `state_at()` es O(log n) verificado | Benchmark: 10K, 100K, 1M entries → latencia constante |

---

## Resumen de Cambios v1→v2

| CR | Cambio | Sección |
|----|--------|---------|
| CR-01 | FactHistory = fuente de verdad. MemoryTimeline = proyección temporal. | §2 |
| CR-02 | MemoryEntry contiene solo FactRef (strings), no Facts. | §3 |
| CR-03 | timestamp = instante de observación. Documentados los otros 3 tipos. | §4 |
| CR-04 | Snapshot cada 10K entries o 24h. Journal JSON Lines. Recuperación <5s. | §6 |
| CR-05 | Single writer en el proceso pipeline. Distribuido documentado como futuro. | §7 |
| CR-06 | state_at() = O(log n) con bisección binaria. | §11 |
| CR-07 | RAM cuantificado: 100K = ~20MB, 1M = ~200MB, >1M = persistente. | §10 |
| CR-08 | entry_id determinista (SHA-256). NO depende de posición. | §8 |
| CR-09 | Política por tipo: entries expiran, snapshots no, journal rota con snapshot. | §9 |
| CR-10 | 22 invariantes separados de F25 (7 categorías). | §13 |
