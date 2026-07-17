# ADR-025-02: Knowledge Identity Model

**Estado:** Aprobado  
**Fecha:** 2026-07-17  
**Contexto:** F25-B5 (Arquitectura del Versionado)  
**Bloqueantes resueltos:** CRÍTICO-01, CRÍTICO-03, CRÍTICO-04

---

## Problema

KnowledgeFact mezcla actualmente tres conceptos distintos en un mismo `dataclass(frozen=True)`:

1. **Identidad** — qué hace único a este hecho (¿sobre qué trata?)
2. **Contenido** — el valor actual del hecho (confianza, evidencia, versión)
3. **Versionado** — cómo se relaciona con versiones anteriores/posteriores

Esto impide un modelo de versionado limpio y fuerza referencias cruzadas frágiles (`superseded_by`, `previous_version`).

## Decisión

Separar el modelo en tres capas conceptuales con tipos diferenciados.
Cada capa tiene su propia identidad, independiente de las demás.

```
Fact (identidad inmatable)
  │
  ├── FactVersion (contenido en un instante)
  │     ├── version_id: str
  │     ├── confidence: float
  │     ├── evidence_ids: tuple[str, ...]
  │     ├── provenance: tuple[str, ...]
  │     └── created_at: float
  │
  └── FactHistory (orden de versiones)
        ├── current: VersionId
        ├── versions: OrderedDict[VersionId, FactVersion]
        └── supersedes: VersionId → VersionId (opcional, árbol)
```

### Identidad por capa

| Capa | ¿Qué identifica? | ID | Inmutable | Dependencia |
|------|-----------------|----|-----------|-------------|
| **Fact** | Un hecho de conocimiento único | `fact_id` | ✅ Sí | Independiente |
| **FactVersion** | Una versión concreta de un Fact | `version_id` | ✅ Sí | Depende de Fact (vía `fact_id`) |
| **FactHistory** | El historial de un Fact | `fact_id` (1:1 con Fact) | ❌ Mutable | Depende de Fact + contiene FactVersions |

**Regla:** `FactVersion` **nunca puede existir sin** `FactHistory`. Toda versión pertence a un historial. No hay versiones huérfanas.

### Capa 1 — Fact (identidad del hecho)

```python
@dataclass(frozen=True)
class Fact:
    """Identidad inmatable de un hecho de conocimiento.

    - Dos Facts son el mismo hecho si tienen el mismo fact_id.
    - fact_id se deriva exclusivamente de (normalized_subject, normalized_predicate, normalized_object).
    - Ningún otro atributo participa en la identidad.
    - Un Fact no tiene confianza, evidencia ni versión — solo identidad.
    - La identidad de un Fact no cambia nunca.
    """
    fact_id: str
    subject: str       # canónico (post entity resolution)
    predicate: str     # canónico
    object: str        # canónico
```

### Capa 2 — FactVersion (identidad de la versión)

```python
@dataclass(frozen=True)
class FactVersion:
    """Una versión concreta de un hecho en un instante.

    - Pertenece exactamente a un Fact (vía fact_id). NO puede existir sin él.
    - Diferentes versiones del mismo Fact comparten el mismo fact_id.
    - version_id es independiente del orden de inserción en FactHistory.
    - La versión vigente es FactHistory.current, no la de mayor version_id.
    - La identidad de una versión (version_id) no cambia nunca.
    """
    version_id: str
    fact_id: str
    confidence: float
    evidence_ids: tuple[str, ...]
    provenance: tuple[str, ...]
    created_at: float
    supersedes: str | None = None   # version_id que reemplaza (opcional, DAG)
```

### Capa 3 — FactHistory (identidad del historial)

```python
@dataclass
class FactHistory:
    """Historial completo de versiones de un Fact.

    - Existe exclusivamente para su Fact (relación 1:1).
    - `current` apunta a la versión vigente (puede cambiar con rollback).
    - Las versiones forman una cadena lineal (o árbol si hay forks).
    - La identidad del historial es la de su Fact (fact_id).
    - Si el Fact se elimina (DELETE físico), el FactHistory también se elimina.
    """
    fact_id: str
    current: str                    # version_id vigente
    versions: dict[str, FactVersion]  # version_id → FactVersion
    created: float                  # timestamp de la primera versión
    updated: float                  # timestamp de la última versión
```

## Consecuencias

### Positivas
1. **Identidad desacoplada de contenido** — cambiar confianza o evidencia no cambia la identidad
2. **Versionado explícito** — consultar historial es O(1) por fact_id
3. **Sin referencias cruzadas frágiles** — `supersedes` es un enlace unidireccional (no bidireccional)
4. **KnowledgeFact actual puede mapearse** — `Fact(KnowledgeFact.id, subject, predicate, object)` + `FactVersion(...)` con los campos restantes
5. **FactIndex indexa Fact.fact_id** — compatible sin cambios

### Negativas
1. Tres clases donde había una — más código, más tests
2. Operaciones atómicas requieren actualizar `FactHistory.current`
3. Migración del modelo existente requiere script de transformación

### Invariantes

```
I1. fact_id = SHA-256(normalize(subject), normalize(predicate), normalize(object))[:16]
I2. ∀ v ∈ FactHistory.versions : v.fact_id == FactHistory.fact_id
I3. FactHistory.current ∈ FactHistory.versions.keys()
I4. La cadena supersedes no contiene ciclos (DAG)
I5. Una versión no puede cambiar de Fact (fact_id es inmutable en FactVersion)
I6. Toda FactVersion pertenece exactamente a un FactHistory
I7. No existen FactVersion sin FactHistory (no hay versiones huérfanas)
I8. DELETE físico de Fact elimina cascada: Fact + FactHistory + todas sus FactVersion
```

## Relación con el modelo actual

```python
# Actual → Futuro
KnowledgeFact.id         → Fact.fact_id
KnowledgeFact.subject    → Fact.subject (post normalización)
KnowledgeFact.predicate  → Fact.predicate
KnowledgeFact.object     → Fact.object
KnowledgeFact.confidence → FactVersion.confidence
KnowledgeFact.evidence_ids → FactVersion.evidence_ids
KnowledgeFact.provenance → FactVersion.provenance
KnowledgeFact.version    → ordinal en FactHistory
KnowledgeFact.created_at → FactVersion.created_at
KnowledgeFact.superseded_by → (eliminado — lo gestiona FactHistory)
KnowledgeFact.previous_version → (eliminado — lo gestiona FactHistory)
KnowledgeFact.evidence   → (eliminado — usar evidence_ids)
```

## Migración

No implementar ahora. Solo diseño. Cuando se implemente R07:

1. `FactIndex` indexa `Fact.fact_id` — sin cambios en su API
2. `KnowledgeMerger` produce `Fact` + `FactVersion` en lugar de `KnowledgeFact`
3. `SimpleKnowledgeMerger` se adapta para crear el par (Fact, FactVersion)
4. `FusionResult.accepted` pasa a ser `tuple[FactVersion, ...]`
