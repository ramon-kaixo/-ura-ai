# ADR-025-04: Hash & Identity Policy

**Estado:** Aprobado  
**Fecha:** 2026-07-17  
**Contexto:** F25-B5 (Arquitectura del Versionado)  
**Bloqueantes resueltos:** CRÍTICO-02, ALTA-06, CRÍTICO-12  
**Depende de:** ADR-025-02, ADR-025-03

---

## Problema

`make_fact_id()` actual no normaliza sus parámetros, lo que significa que
`make_fact_id("Apple", "sells", "oranges")` produce un ID diferente de
`make_fact_id("apple", "sells", "oranges")`. Esto es incorrecto: ambas
representan el mismo hecho.

Además, `created_at` usa `time.time()` como default, lo que rompe el
determinismo si no se pasa explícitamente.

## Decisión

### Política de normalización para IDs

```
fact_id = SHA-256(
    normalize(subject) + ":" +
    normalize(predicate) + ":" +
    normalize(object) + ":" +
    "v" + str(version)
)[:16]
```

Donde `normalize(s)` se define como:

```python
def normalize_identity(text: str) -> str:
    """Normalización para identidad de hechos.

    Aplica a subject, predicate y object para calcular fact_id.
    - lowercase + strip
    - espacios múltiples → simple
    - puntuación no esencial eliminada
    - NO resuelve sinónimos (CEO → Chief Executive Officer)
    - NO resuelve entidades (Apple → E0001)
    """
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)  # elimina puntuación
    return text.strip()
```

### ¿Qué NO participa en la identidad?

| Campo | ¿Participa? | Justificación |
|-------|-----------|---------------|
| subject | ✅ SÍ | Componente de identidad |
| predicate | ✅ SÍ | Componente de identidad |
| object | ✅ SÍ | Componente de identidad |
| version | ❌ NO | La versión distingue instancias, no identidad |
| confidence | ❌ NO | Atributo mutable |
| evidence_ids | ❌ NO | Atributo mutable |
| provenance | ❌ NO | Atributo mutable |
| created_at | ❌ NO | Metadato temporal |
| fact_id (SHA) | ✅ SÍ | Derivado de subject+predicate+object |

### ¿Qué NO resuelve la normalización de identidad?

- **Alias**: "Apple Inc." y "Apple Computer" son el mismo Fact SOLO si
  Entity Resolution los normaliza al mismo subject antes de llamar a
  `make_fact_id`. La normalización de identidad NO expande sinónimos.
- **Idiomas**: "manzana" (español) y "apple" (inglés) producen IDs
  diferentes. La fusión multilingüe se resuelve en Entity Resolution,
  no en la identidad.
- **Errores ortográficos**: "Appple" → ID diferente. La corrección
  ocurre antes (en NormalizationStage) o después (vía corrección manual).

### ¿Dónde ocurre la normalización?

```
Text raw → NormalizationStage (normalized_text)
  → EntityResolutionStage (subject canónico)
    → KnowledgeMerger (construye Fact con subject normalizado)
      → make_fact_id() con valores ya normalizados
```

### created_at y determinismo

```python
# ❌ Incorrecto (no determinista):
KnowledgeFact(created_at=field(default_factory=time.time))

# ✅ Correcto:
KnowledgeFact(created_at=ev.fetched_at)  # desde Evidence
FactVersion(created_at=timestamp_explícito)  # desde quien crea la versión
```

`created_at` **NO** participa en hashes de identidad. Participa en
`version_id` (vía timestamp externo controlado, no `time.time()`).

### IDs SHA-256 truncados

```python
def make_fact_id(subject, predicate, obj) -> str:
    raw = f"{normalize(subject)}:{normalize(predicate)}:{normalize(obj)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
```

**Justificación del truncado a 16 caracteres hex (64 bits):**

| Métrica | Valor |
|---------|-------|
| Bits de hash | 64 (16 hex × 4 bits) |
| Probabilidad de colisión (n=10⁶, N=2⁶⁴) | ~2.7 × 10⁻⁵ |
| Probabilidad de colisión (n=10⁹, N=2⁶⁴) | ~2.7% |
| Tamaño objetivo del proyecto | < 10⁸ facts |
| Riesgo aceptado para 10⁸ facts | ~5.4 × 10⁻⁵ |

**Decisión:** Mantener truncado a 16 hex. Si el proyecto supera 10⁸ facts,
migrar a 32 hex (128 bits) con un version_id compuesto (fact_id + extensión).

**Justificación formal:**
El truncado a 64 bits es suficiente para el tamaño objetivo del proyecto
(< 10⁸ facts). La probabilidad de colisión es inferior a 10⁻⁴, comparable
a la tolerancia de errores de hardware. Si se supera este umbral, se
añade un segundo segmento de 64 bits manteniendo compatibilidad hacia atrás
(IDs existentes siguen siendo válidos como prefijos).

## Consecuencias

### Inmediatas

1. `make_fact_id()` debe normalizar sus parámetros internamente
2. El orden de etapas del pipeline garantiza que Entity Resolution ocurre
   antes de la creación del Fact, por lo que subject/predicate/object
   llegan ya normalizados al Merger
3. `KnowledgeFact.created_at` no debe tener `default_factory=time.time`
   (migrar a campo obligatorio o `0.0`)

### Para R07

4. `Fact.fact_id` usa esta misma política de normalización
5. `FactVersion.version_id` usa timestamp + content_hash (no el default
   de time.time)
6. La identidad es inmutable una vez creado el Fact

### Invariantes de ID

```
H1. mismo (subject, predicate, object) normalizado → mismo fact_id
H2. fact_id no cambia aunque cambien confidence, evidence o provenance
H3. created_at no participa en fact_id (sí en version_id)
H4. La normalización de identidad NO es semántica (no expande sinónimos)
H5. La normalización semántica es responsabilidad de Entity Resolution
H6. SHA-256[:16] es suficiente para < 10⁸ facts
```
