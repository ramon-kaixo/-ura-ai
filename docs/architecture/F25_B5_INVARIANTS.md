# F25-B5: Invariants & Contract Review

**Fecha:** 2026-07-17  
**Versión:** 2.0  
**Bloque:** Arquitectura del Versionado (pre-R07)  
**Depende de:** ADR-025-02, ADR-025-03, ADR-025-04

---

## 1. Invariantes del Sistema de Conocimiento

Cada invariante indica:
- **ID**: código único
- **Categoría**: identidad / consistencia / concurrencia / versionado / determinismo / rendimiento
- **Descripción**: qué debe cumplirse
- **Verificación**: cuándo se comprueba (runtime / test / CI / documentación)
- **Responsable**: qué componente garantiza el invariante
- **Violación**: cómo se detecta
- **Fallo**: qué ocurre si se viola
- **Test**: ✅ obligatorio / ⚠️ recomendado / ❌ no aplica

### 1.1 Identidad

| ID | Invariante | Verificación | Responsable | Violación | Fallo | Test |
|----|-----------|-------------|-------------|-----------|-------|------|
| I01 | `fact_id = SHA-256(normalize(subj), normalize(pred), normalize(obj))[:16]` | Test unitario | `make_fact_id()` | Dos Facts con el mismo subject+predicate+object tienen diferente ID | Hechos duplicados no detectables | ✅ |
| I02 | `fact_id` es inmutable una vez creado | Test unitario | `Fact.__init__()` | Mutación del campo fact_id | Inconsistencia en FactIndex | ✅ |
| I03 | Dos Facts con el mismo `fact_id` son el mismo hecho | Test unitario | `Fact.__eq__()` | Dos objetos Fact distintos con fact_id igual | Colisión de hash real | ⚠️ |
| I04 | `normalize_identity()` es la única implementación canónica | Code review | `ADR-025-04` | Normalización inconsistente entre componentes | IDs diferentes para el mismo hecho | ❌ (doc) |
| I05 | Un cambio en subject/predicate/object crea un nuevo Fact (nuevo fact_id) | Test integración | `KnowledgeMerger` | Merger produce mismo fact_id con diferente sujeto | Pérdida de hechos | ✅ |
| I06 | Un cambio en confidence/evidence/provenance crea nueva versión (mismo fact_id) | Test integración | `FactHistory.add_version()` | Mismo fact_id con diferente confidence | Duplicación de Facts | ✅ |

### 1.2 Versionado

| ID | Invariante | Verificación | Responsable | Violación | Fallo | Test |
|----|-----------|-------------|-------------|-----------|-------|------|
| V01 | `FactVersion.fact_id == FactHistory.fact_id` | Test unitario, runtime | `FactHistory.add_version()` | version_id pertenece a otro Fact | Consultas devuelven hechos incorrectos | ✅ |
| V02 | `FactHistory.current ∈ FactHistory.versions.keys()` | Test unitario, runtime | `FactHistory` | current apunta a versión inexistente | Crash en consulta de versión vigente | ✅ |
| V03 | Cadena `current → supersedes → ... → None` termina (sin ciclos) | Test unitario | `FactHistory.add_version()` | Ciclo en supersedes | Bucle infinito en timeline() | ✅ |
| V04 | `version_id` es independiente del orden de inserción en FactHistory | Test unitario | `make_version_id()` | version_id cambia al reordenar historial | Pérdida de trazabilidad | ✅ |
| V05 | Rollback NO crea nueva versión — solo reasigna `current` | Test unitario | `FactHistory` | Rollback genera versión fantasma | Historial inconsistente | ✅ |
| V06 | Rollback NO elimina versiones posteriores | Test unitario | `FactHistory` | Versiones desaparecen tras rollback | Pérdida de historia | ✅ |
| V07 | DELETE lógico (tombstone) mantiene la versión en FactHistory | Test unitario | `FactHistory.add_version(obsolete)` | Versión eliminada desaparece | Imposible auditar eliminaciones | ✅ |
| V08 | DELETE físico elimina Fact + FactHistory completo en cascada | Test integración | Cliente de FactIndex | FactHistory huérfano tras DELETE físico | Fugas de memoria | ✅ |
| V09 | Toda `FactVersion` pertenece exactamente a un `FactHistory` | Test unitario | `FactHistory.add_version()` | Versión huérfana sin historial | Inconsistencia de datos | ✅ |
| V10 | No existen `FactVersion` sin `FactHistory` | Runtime (constructor) | `FactVersion.__init__()` | Versión creada sin fact_id válido | Dato no recuperable | ✅ |

### 1.3 Determinismo

| ID | Invariante | Verificación | Responsable | Violación | Fallo | Test |
|----|-----------|-------------|-------------|-----------|-------|------|
| D01 | Misma entrada + misma configuración → mismo conjunto de Facts | Test de regresión | Pipeline completo | Dos ejecuciones idénticas producen Facts diferentes | Sistema no reproducible | ✅ |
| D02 | `created_at` debe pasarse explícitamente (prohibido `default_factory=time.time`) | Code review, ruff | `KnowledgeFact`, `FactVersion` | created_at usa default no determinista | IDs de versión no reproducibles | ❌ (lint) |
| D03 | `EntityResolver.resolve()` sin estado mutable externo | Code review | `ContextualEntityResolver` | Resolver produce resultados diferentes para misma entrada | Entity Resolution no reproducible | ⚠️ |
| D04 | `ScoringStrategy.select()` sin estado mutable externo | Code review | `KeywordScorer` | Scorer produce resultados diferentes para misma entrada | Desambiguación no reproducible | ⚠️ |
| D05 | `make_fact_id()` produce el mismo ID para los mismos parámetros normalizados | Test unitario | `make_fact_id()` | ID diferente para mismos parámetros | Ruptura de identidad | ✅ |

### 1.4 Provenance

| ID | Invariante | Verificación | Responsable | Violación | Fallo | Test |
|----|-----------|-------------|-------------|-----------|-------|------|
| P01 | `FactVersion.provenance` contiene todos los claim_ids origen | Test integración | `KnowledgeMerger` | Fact sin provenance | Imposible auditar origen | ✅ |
| P02 | `FusionProvenance` registra todos los componentes del pipeline | Test integración | Cada stage | Componente no registrado | Imposible reproducir ejecución | ✅ |
| P03 | Toda transformación del pipeline deja `StageProvenance` | Test integración | `BaseStage.execute()` | Etapa sin StageProvenance | Pérdida de auditoría | ✅ |
| P04 | `StageProvenance.timestamp` usa tiempo de ejecución reproducible | Test unitario | `StageProvenance` | Timestamp no reproducible | Auditoría inconsistente | ⚠️ |

### 1.5 Concurrencia

| ID | Invariante | Verificación | Responsable | Violación | Fallo | Test |
|----|-----------|-------------|-------------|-----------|-------|------|
| C01 | `FactIndex` frozen es thread-safe (dict.get atómico) | Documentación | `FactIndex.freeze()` | Lectura concurrente corrompe índice | Race condition | ❌ (doc) |
| C02 | `FactIndex` mutable requiere serialización externa | Documentación | Cliente | Escritura concurrente sin lock | Inconsistencia de índices | ❌ (doc) |
| C03 | `EntityRegistry` es inmutable tras `__init__` | Test unitario | `EntityRegistry` | Registro mutado después de construcción | Inconsistencia en resolución | ✅ |
| C04 | `FusionPipeline.run()` crea `FusionContext` propio | Test unitario | `FusionPipeline` | Contexto compartido entre ejecuciones | Race condition en pipeline | ⚠️ |

### 1.6 Rendimiento

| ID | Invariante | Verificación | Responsable | Violación | Fallo | Test |
|----|-----------|-------------|-------------|-----------|-------|------|
| R01 | `FactIndex.lookup()` O(1) amortizado | Benchmark CI | `FactIndex` | Lookup degrada a O(n) | Consultas lentas | ✅ |
| R02 | `FactIndex.add_fact()` O(1) amortizado | Benchmark CI | `FactIndex` | Inserción degrada | Pipeline lento | ✅ |
| R03 | `FactHistory.add_version()` O(1) | Benchmark CI | `FactHistory` | Inserción en historial degrada | Versionado lento | ✅ |
| R04 | `make_fact_id()` < 1µs | Benchmark CI | `make_fact_id()` | Cálculo de ID lento | Cuello de botella en merge | ⚠️ |

---

## 2. Contratos Pendientes de Implementación

| ID | Cambio | ADR | Prioridad | Estado |
|----|--------|-----|-----------|--------|
| C-01 | `FusionContext.bundle: CitationBundle \| None` (eliminar Any) | — | ALTA | Pendiente R07 |
| C-02 | `KnowledgeFact.created_at: float = 0.0` (sin default factory) | ADR-025-04 | ALTA | Pendiente R07 |
| C-03 | `EntityRegistry.registry_version + dataset_checksum` | — | ALTA | Pendiente R07 |
| C-04 | `QualitySourceScorer` leer pesos de FusionConfig | — | ALTA | Pendiente R07 |
| C-05 | `make_fact_id()` con normalize_identity() interno | ADR-025-04 | CRÍTICA | Pendiente R07 |
| C-06 | `EvidenceSet` como frozen | — | MEDIA | Pendiente R07 |
| C-07 | `KnowledgeDelta.facts_removed` → `FactTombstone` | ADR-025-03 | ALTA | Pendiente R07 |
| C-08 | `FactTombstone` modelo + integración con FactIndex | ADR-025-03 | ALTA | Pendiente R07 |

---

## 3. Evolución: Claim → Fact → FactVersion → Rollback → Tombstone

### Ejemplo 1: Creación

```python
# Claim inicial
claim = KnowledgeClaim(id="c001", text="Apple sells oranges", confidence=0.8)

# Tras pipeline: Fact + primera versión
fact = Fact(fact_id="abc123", subject="apple", predicate="sells", object="oranges")
v1 = FactVersion(
    version_id="v1",
    fact_id="abc123",
    confidence=0.8,
    evidence_ids=("ev001",),
    provenance=("c001",),
    created_at=1000.0,
)
history = FactHistory.create(fact, v1)
assert history.current == v1
```

### Ejemplo 2: Actualización (nueva evidencia, mayor confianza)

```python
# Nueva evidencia: misma fuente, fragmento más completo
v2 = FactVersion(
    version_id="v2",
    fact_id="abc123",
    confidence=0.95,
    evidence_ids=("ev001", "ev002"),
    provenance=("c001", "c002"),
    created_at=1200.0,
    supersedes="v1",
)
history.add_version(v2)
assert history.current == v2  # v2 reemplaza a v1
assert len(history.timeline()) == 2
```

### Ejemplo 3: Rollback

```python
# Se descubre que v2 tenía un error (evidencia incorrecta)
history.rollback("v1")
assert history.current == v1  # v1 es vigente otra vez
assert "v2" in history.versions  # v2 sigue existiendo (no se elimina)
assert len(history.timeline()) == 2  # ambas versiones visibles
```

### Ejemplo 4: Corrección después de rollback

```python
# Nueva versión basada en v1 corregida
v3 = FactVersion(
    version_id="v3",
    fact_id="abc123",
    confidence=0.9,
    evidence_ids=("ev001", "ev003"),
    provenance=("c001", "c003"),
    created_at=1400.0,
    supersedes="v1",  # reemplaza a v1 directamente
)
history.add_version(v3)
assert history.current == v3
assert history.current_version_at(1300.0) == v1  # consulta temporal
```

### Ejemplo 5: Tombstone (DELETE lógico)

```python
# El hecho ya no es válido
v4 = FactVersion(
    version_id="v4",
    fact_id="abc123",
    confidence=0.0,
    evidence_ids=(),
    provenance=("c004",),
    created_at=1500.0,
    supersedes="v3",
    change_type=ChangeType.OBSOLETE,  # tombstone
)
history.add_version(v4)
assert history.current == v4
assert history.current.is_tombstone is True
# FactIndex todavía tiene el fact (disponible para consultas históricas)
```

### Ejemplo 6: DELETE físico

```python
# El hecho se elimina permanentemente
fact_id = "abc123"
history = fact_store.get_history(fact_id)
fact_store.delete(fact_id)
# Fact + FactHistory + todas las versiones destruidas
# FactIndex.remove_fact(fact_id)
assert fact_store.get_history(fact_id) is None
```

---

## 4. Model Glossary

| Término | Definición | Inmutable | ID |
|---------|-----------|-----------|----|
| **Evidence** | Fragmento textual extraído de un documento fuente. Contiene el texto exacto, la URL, el hash y la calidad. | ✅ (frozen) | `evidence_id` |
| **KnowledgeClaim** | Afirmación extraída de una Evidence, enriquecida durante el pipeline (normalización, entidades, scoring). | ❌ (mutable) | `claim_id` |
| **Fact** | Identidad única de un hecho de conocimiento. Solo contiene subject, predicate, object normalizados. | ✅ (frozen) | `fact_id` |
| **FactVersion** | Versión concreta de un Fact en un instante. Contiene confidence, evidence_ids, provenance. | ✅ (frozen) | `version_id` |
| **FactHistory** | Historial ordenado de todas las versiones de un Fact. Gestiona current, timeline, rollback. | ❌ (mutable) | `fact_id` (1:1 con Fact) |
| **Entity** | Entidad del mundo real resuelta (Apple Inc., Nikola Tesla, etc.). | ❌ | `entity_id` |
| **Conflict** | Relación entre dos Claims que comparten subject+predicate pero difieren en object. | ❌ (mutable) | `conflict_id` |
| **KnowledgeDelta** | Conjunto de cambios entre dos estados de conocimiento: facts añadidos, actualizados, eliminados. | ❌ | — |
| **FactTombstone** | Marcador de eliminación lógica de un Fact. Indica que el hecho ya no es válido pero su historia persiste. | ✅ (frozen) | `version_id` |
| **FusionResult** | Salida del pipeline de fusión: Facts aceptados, Claims rechazados, Conflictos, Warnings. | ❌ | — |

---

## 5. Trazabilidad: Componente → ADR → Invariantes → Tests

| Componente | ADR | Invariantes | Tests |
|-----------|-----|-------------|-------|
| `make_fact_id()` | ADR-025-04 | I01, D05 | `test_fact_id_deterministic`, `test_fact_id_normalization` |
| `Fact` | ADR-025-02 | I02, I03, I05 | `test_fact_identity_inmutable`, `test_fact_equals` |
| `FactVersion` | ADR-025-02, ADR-025-03 | V04, V09, V10 | `test_version_id_independent`, `test_version_requires_fact` |
| `FactHistory` | ADR-025-02, ADR-025-03 | V01, V02, V03, V05, V06, V07 | `test_history_current_in_versions`, `test_history_no_cycles`, `test_rollback_no_new_version` |
| `FactIndex` | — | R01, R02, C01, C02 | Benchmarks + `test_frozen_thread_safe` |
| `EntityRegistry` | — | C03 | `test_registry_inmutable_after_init` |
| `ContextualEntityResolver` | — | D03 | `test_resolve_deterministic_same_context` |
| `FusionPipeline` | — | C04 | `test_pipeline_independent_contexts` |
| `FusionProvenance` | — | P02, P03 | `test_provenance_all_fields_set` |
| `StageProvenance` | — | P04 | `test_stage_provenance_has_timestamp` |
| `KnowledgeMerger` | ADR-025-04 | I05, P01 | `test_merger_preserves_provenance` |
| `BasicChangeDetector` | ADR-025-03 | — | `test_delta_added_confirmed` |
