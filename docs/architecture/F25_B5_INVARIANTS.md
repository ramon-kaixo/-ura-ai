# F25-B5: Invariants & Contract Review

**Fecha:** 2026-07-17  
**Bloque:** Arquitectura del Versionado (pre-R07)  
**Depende de:** ADR-025-02, ADR-025-03, ADR-025-04

---

## 1. Invariantes del Sistema de Conocimiento

### 1.1 Identidad

```
I01. fact_id = SHA-256(normalize(subject) + ":" + normalize(predicate) + ":" + normalize(object))[:16]
I02. fact_id es inmutable una vez creado
I03. Dos Facts con el mismo fact_id representan la misma identidad
I04. Un cambio en subject/predicate/object crea un nuevo Fact (nuevo fact_id)
I05. Un cambio en confidence/evidence/provenance crea una nueva versión (mismo fact_id)
```

### 1.2 Versionado

```
I06. FactVersion.fact_id ∈ FactHistory.fact_id
I07. FactHistory.current ∈ FactHistory.versions.keys()
I08. La cadena current → supersedes → ... termina en None (sin ciclos)
I09. version_id es determinista (mismo fact_id + timestamp + hash → mismo ID)
I10. DELETE lógico no destruye versiones (marca obsolete)
I11. DELETE físico elimina Fact + FactHistory completo
I12. ROLLBACK solo reasigna current, no destruye versiones
```

### 1.3 Determinismo

```
I13. Misma entrada + misma configuración → mismo conjunto de Facts
I14. created_at debe pasarse explícitamente (no usar default_factory=time.time)
I15. StageProvenance.timestamp debe ser reproducible (usar tiempo de ejecución, no de creación)
I16. EntityResolver.resolve() sin estado mutable externo
I17. ScoringStrategy.select() sin estado mutable externo
```

### 1.4 Provenance

```
I18. FactVersion.provenance contiene todos los claim_ids que originaron la versión
I19. FusionProvenance registra todos los componentes que participaron
I20. StageProvenance registra entrada/salida de cada etapa
I21. Toda transformación del pipeline deja StageProvenance
```

### 1.5 Concurrencia

```
I22. FactIndex frozen es thread-safe (dict.get atómico)
I23. FactIndex mutable requiere serialización externa
I24. EntityRegistry es inmutable tras __init__ (lookup concurrente seguro)
I25. FusionPipeline.run() crea FusionContext propio (sin estado compartido)
```

---

## 2. Revisión de Contratos

### 2.1 FusionContext.bundle (CRÍTICO-05 → ALTA-05)

**Estado actual:** `bundle: Any = None`  
**Problema:** Tipo `Any` impide verificación estática, serialización distribuida, y documentación de API.  
**Solución:** `bundle: CitationBundle | None = None`  
**Impacto:** Backward compatible (Any acepta cualquier valor). El cambio de tipo solo afecta a verificadores estáticos.  
**Prioridad:** ALTA — debe corregirse antes de cerrar F25.

### 2.2 KnowledgeDelta removals (CRÍTICO-07 → ALTA-07)

**Estado actual:** `facts_removed: tuple[tuple[str, ...], ...]`  
**Problema:** Tupla de tuplas de strings — estructura confusa, sin semántica definida.  
**Solución:** Reemplazar por `tombstones: tuple[FactTombstone, ...]` donde:

```python
@dataclass
class FactTombstone:
    fact_id: str
    removed_at: float
    reason: RemovalReason  # DELETED | OBSOLETE | SUPERSEDED | ROLLED_BACK
    version_id: str | None  # versión que justifica la eliminación (si aplica)
```

### 2.3 EntityRegistry version (ALTA-09)

**Estado actual:** Sin versionado.  
**Problema:** Imposible saber si el registro de entidades cambió entre ejecuciones.  
**Solución:** Añadir a EntityRegistry:

```python
class EntityRegistry:
    registry_version: str = "1.0.0"
    dataset_checksum: str = ""  # SHA-256 de todas las entradas serializadas
```

`dataset_checksum` se calcula automáticamente en `_rebuild_index()` o se inyecta externamente.

### 2.4 SourceScore normalization (ALTA-11)

**Estado actual:** Pesos hardcodeados en `QualitySourceScorer`, sin documentación de normalización.  
**Solución:** Documentar formalmente:

- `overall = authority * w_a + freshness * w_f + relevance * w_r`
- `w_a + w_f + w_r = 1.0`
- Cada componente debe estar en [0, 1]
- `overall` en [0, 1]
- Si algún componente es NaN → tratarlo como 0.0
- Si algún componente es None → tratarlo como 0.5
- Los pesos deben leerse de `FusionConfig` (no hardcodeados)

### 2.5 make_fact_id() normalization (CRÍTICO-02)

Según ADR-025-04, `make_fact_id()` debe normalizar internamente.
**Cambio requerido:**

```python
def make_fact_id(subject: str, predicate: str, obj: str, version: int = 1) -> str:
    raw = f"{_normalize_id(subject)}:{_normalize_id(predicate)}:{_normalize_id(obj)}:v{version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
```

### 2.6 created_at determinism (ALTA-06)

**Estado actual:** `KnowledgeFact.created_at: float = field(default_factory=time.time)`  
**Problema:** `time.time()` es no determinista. Si el Fact se reconstruye, `created_at` cambia.  
**Solución:** Hacer `created_at` obligatorio (sin default) o usar `0.0` como "no establecido":

```python
@dataclass(frozen=True)
class KnowledgeFact:
    ...
    created_at: float = 0.0  # 0.0 = no establecido, debe pasarse explícitamente
```

### 2.7 EvidenceSet mutability (MEDIA-19)

**Estado actual:** `claims: list[KnowledgeClaim]` mutable.  
**Problema:** Puede modificarse después de creado, rompiendo trazabilidad.  
**Solución:** Marcar como `frozen=True` o usar `tuple[KnowledgeClaim, ...]`.

---

## 3. Decisiones Posteriores (no implementar en B5)

| Decisión | Depende de | Propuesta |
|----------|-----------|-----------|
| Persistencia de FactHistory | R07+R08 | SQLite + KE bridge |
| Cache LRU de FactHistory | R07+R08 | LRUCache < FactHistory.timeline() |
| FusionPipeline reentrada | F26 | Documentar contrato (MEDIA-15) |
| WarningCode enum | F26 | Reemplazar list[str] (MEDIA-21) |
| Statistics dict → tipado | F26+ | Migración gradual (MEDIA-20) |

---

## 4. Resumen de Checklist Pre-R07

| ID | Acción | Prioridad | Estado |
|----|--------|-----------|--------|
| CR-01 | ADR Knowledge Identity Model | 🔴 Crítica | ✅ CREADO (ADR-025-02) |
| CR-02 | make_fact_id() normalization | 🔴 Crítica | ✅ DEFINIDO (ADR-025-04) |
| CR-03 | Separar Fact / FactVersion / FactHistory | 🔴 Crítica | ✅ DISEÑADO |
| CR-04 | Versiones como árbol, no enlaces dobles | 🔴 Crítica | ✅ DISEÑADO |
| A-05 | FusionContext.bundle: eliminar Any | 🟠 Alta | ❌ Pendiente implementación |
| A-06 | created_at determinismo | 🟠 Alta | ✅ DEFINIDO |
| A-07 | KnowledgeDelta removals formal | 🟠 Alta | ✅ DEFINIDO (FactTombstone) |
| A-09 | EntityRegistry version | 🟠 Alta | ✅ DEFINIDO |
| A-11 | SourceScore normalization | 🟠 Alta | ✅ DEFINIDO |
| CR-12 | Justificar truncado SHA-256 | 🔴 Crítica | ✅ DOCUMENTADO (ADR-025-04) |
| M-19 | EvidenceSet inmutable | 🟡 Media | ✅ DEFINIDO |

---

*Los cambios de código (A-05, A-06, A-09, A-11, M-19, make_fact_id normalization) se implementarán al comenzar R07, no en este bloque arquitectónico.*
