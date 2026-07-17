# ADR-025-03: Fact Versioning Model

**Estado:** Aprobado  
**Fecha:** 2026-07-17  
**Contexto:** F25-B5 (Arquitectura del Versionado)  
**Bloqueantes resueltos:** CRÍTICO-03, CRÍTICO-04, CRÍTICO-07, MEDIA-18  
**Depende de:** ADR-025-02 (Knowledge Identity Model)

---

## Problema

El modelo actual (`KnowledgeFact.superseded_by`, `KnowledgeFact.previous_version`) usa enlaces dobles entre hechos para representar versionado. Esto:
1. No escala — cada hecho debe modificarse para apuntar a su sucesor
2. No soporta árboles o forks históricos
3. Impide consultas tipo "¿qué versión estaba vigente en fecha T?"
4. No distingue entre tipos de cambio (updated, corrected, superseded, obsolete)

## Decisión

### Modelo de versionado basado en FactHistory (árbol lineal)

```
Fact: fact_id = "abc123"
  │
  ├── v1: created_at=100, confidence=0.7, supersedes=None
  ├── v2: created_at=200, confidence=0.8, supersedes="v1"
  ├── v3: created_at=300, confidence=0.9, supersedes="v2"
  └── v4: created_at=400, confidence=0.6, supersedes="v3"  ← current
```

Cada `FactVersion` tiene un `version_id` único y una referencia opcional a la versión que reemplaza (`supersedes`). No hay retroreferencia (`previous_version`). La cadena se recorre hacia atrás desde `current`.

### Tipos de cambio

| Tipo | Significado | ¿Nueva versión? | ¿Nuevo Fact? |
|------|------------|-----------------|--------------|
| **created** | Versión inicial de un Fact | Sí | Sí |
| **updated** | Cambio en confianza, evidencia o provenance | Sí | No |
| **corrected** | Corrección semántica del objeto (ej: typo) | Sí | No (mismo sujeto/predicado) |
| **superseded** | Reemplazado por información más reciente | Sí | No |
| **obsolete** | El hecho ya no es válido (sin reemplazo) | Sí (tombstone) | No |
| **forked** | Bifurcación: dos versiones vigentes simultáneas | Sí | No |

### Representación de eliminación

```
DELETE lógico: versión marcada como obsolete (tombstone)
DELETE físico: eliminación del Fact completo + todas sus versiones
ROLLBACK: reasignar current a una versión anterior (NO reescribe historia)
```

**Regla de rollback:** Rollback NO crea una nueva versión. Solo reasigna `FactHistory.current` a una versión existente. No se reescribe ni se elimina historia. Las versiones posteriores a la restaurada permanecen en `FactHistory.versions` accesibles vía `timeline()`.

```
Ejemplo:
  v1 (current) ← rollback desde v3
  v2
  v3 (current original)

Después de rollback a v1:
  v1 (current) ← restaurada
  v2              ← sigue existiendo en timeline()
  v3              ← sigue existiendo en timeline()
  current = v1, no se pierde ninguna versión
```

### Tombstone en FactIndex

El tombstone (versión marcada como OBSOLETE) **SÍ** participa en FactIndex
hasta que ocurra DELETE físico. Esto permite:

- Consultar "¿este fact existió?" (trazabilidad)
- Detectar ciclos de create/delete/create
- Implementar soft-delete sin pérdida de información

```python
@dataclass
class FactTombstone:
    fact_id: str
    removed_at: float
    reason: RemovalReason  # DELETED | OBSOLETE | SUPERSEDED | ROLLED_BACK
    version_id: str | None  # versión que justifica la eliminación
```

### FactHistory y DELETE físico

DELETE físico elimina el Fact + FactHistory completo. Después del DELETE físico:
- FactHistory ya no existe (no mantiene referencias)
- FactIndex debe eliminar todas las referencias al fact_id
- Las FactVersion se destruyen en cascada
- No hay forma de recuperar el hecho (consistencia)```

### VersionId — independencia del orden de inserción

```python
def make_version_id(fact_id: str, timestamp: float, content_hash: str) -> str:
    """ID determinista de versión.

    Participan en el hash:
    - fact_id (identidad del hecho)
    - timestamp (cuándo se creó, debe pasarse explícitamente)
    - content_hash (qué contiene — confidence + evidence_ids + provenance)

    NO participan:
    - El orden de inserción en FactHistory
    - El número de versión (ordinal)
    - El estado de current en FactHistory
    - Cualquier estado temporal del sistema

    Esto garantiza:
    - Mismo hecho + mismo contenido + mismo instante → mismo version_id
    - version_id es independiente de cuándo/dónde se inserte en el historial
    - version_id no cambia aunque se reordene el historial
    """
    raw = f"{fact_id}:{int(timestamp)}:{content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
```

## API de FactHistory

```python
class FactHistory:
    @classmethod
    def create(cls, fact: Fact, version: FactVersion) -> FactHistory: ...

    def add_version(self, version: FactVersion) -> None: ...

    @property
    def current(self) -> FactVersion: ...

    def version_at(self, timestamp: float) -> FactVersion | None:
        """Retorna la versión vigente en el instante dado."""
        ...

    def timeline(self) -> list[FactVersion]:
        """Retorna versiones ordenadas por created_at ascendente."""
        ...

    def diff(self, v1: str, v2: str) -> FactDiff: ...
```

## FactDiff

```python
@dataclass
class FactDiff:
    fact_id: str
    version_a: str
    version_b: str
    confidence_delta: float
    evidence_added: tuple[str, ...]
    evidence_removed: tuple[str, ...]
    provenance_added: tuple[str, ...]
    change_type: ChangeType
```

## Consecuencias

### Positivas
1. Consulta histórica O(1) por version_id
2. Rollback: reasignar `current` (O(1))
3. Sin enlaces bidireccionales — consistencia más simple
4. Tipos de cambio explícitos (no solo "updated" genérico)
5. Compatible con FactIndex sin cambios

### Negativas
1. FactHistory debe almacenarse externamente (memoria, después persistencia)
2. Tombstones ocupan espacio hasta DELETE físico
3. Diferencias entre updated/corrected/superseded requieren semántica externa

### Invariantes

```
V1. FactHistory.current.supersedes ∈ FactHistory.versions ∪ {None}
V2. La cadena current → supersedes → ... → None termina (sin ciclos)
V3. version_id es determinista (mismo fact_id + timestamp + hash → mismo ID)
V4. DELETE físico no puede revertirse (tombstone es el límite)
V5. ROLLBACK no destruye versiones — solo reasigna current
```

## Relación con el modelo actual

```python
# Actual BasicChangeDetector → Futuro
ADDED    → FactHistory.create()  (nuevo Fact + primera versión)
UPDATED  → FactHistory.add_version()  (nueva versión del mismo Fact)
REMOVED  → FactHistory.add_version(obsolete) o DELETE físico
```

## No implementado todavía

- Forks/bifurcaciones (reservado para F26 si es necesario)
- Merge de forks (idem)
- Persistencia (BD, archivo, KE bridge)
- Cache de FactHistory (LRU para consultas frecuentes)
