# F25 — Architecture Audit (Knowledge Fusion)

**Date:** 2026-07-17
**Scope:** F25-B1 (Contracts) + F25-B2 (PipelineStage implementations)
**Tag:** Audit post-B2, pre-B3
**Objective:** Verify architecture supports multi-year evolution without API breakage.

---

## 1. Contratos (ABCs)

### 1.1 Responsabilidad Única

| ABC | Responsabilidad | Cumple SRP |
|-----|----------------|------------|
| `FusionEngine` | Orquestar pipeline completo | ✅ |
| `PipelineStage` | Ejecutar una transformación atómica en el pipeline | ✅ |
| `ConflictResolver` | Detectar y resolver conflictos entre claims | ✅ |
| `SourceScorer` | Puntuar calidad de fuentes por claim | ✅ |
| `EntityResolver` | Normalizar texto a entidad canónica | ✅ |
| `KnowledgeMerger` | Fusionar claims en facts consolidados | ✅ |
| `ChangeDetector` | Detectar cambios entre estados de conocimiento | ✅ |
| `MemoryCandidateSelector` | Seleccionar facts candidatos para memoria | ✅ |

**Veredicto:** SRP correcto. Cada ABC tiene exactamente una responsabilidad.

### 1.2 Acoplamiento

**Problema: `SourceScorer` conoce `KnowledgeClaim`.**

`SourceScorer.score(claim: KnowledgeClaim) -> SourceScore` fuerza al scorer a extraer el `Evidence` del claim. Si en el futuro el scoring necesita metadatos del `WebDocument` (dominio, fecha de publicación, reputación), el scorer tendrá que navegar por `claim.evidence` para llegar al documento fuente. Esto crea un acoplamiento indirecto con `CitationBundle`.

**Riesgo:** Bajo. El `Evidence` lleva `document_url` que permite acceso al `WebDocument` vía lookup externo.

**Problema: `ConflictResolver.resolve()` retorna `tuple[list[KnowledgeFact], list[Conflict]]`.**

La mezcla de facts y conflicts en el retorno es confusa. `KnowledgeFact` y `Conflict` son tipos distintos con ciclos de vida diferentes. El resolver debería retornar solo `list[Conflict]` (con `resolved=True/False`) y dejar la creación de `KnowledgeFact` al Merger.

**Riesgo:** Medio. La firma actual fuerza a `NaiveConflictResolver` a retornar `resolved_facts: list[KnowledgeFact]` vacío siempre — campo muerto.

### 1.3 Cohesión

| ABC | Cohesión |
|-----|----------|
| `FusionEngine` | Alta — un solo método `fuse()` |
| `PipelineStage` | Alta — `execute()` es el único método público |
| `EntityResolver` | Alta — `resolve`, `resolve_many`, `normalize` están relacionados |
| Otros | Alta — todos los métodos giran en torno al mismo concepto |

### 1.4 LSP (Liskov Substitution Principle)

Todos los ABCs usan tipos concretos en parámetros y retornos. Una implementación `NaiveConflictResolver` puede sustituir a `ConflictResolver` sin violar LSP. Correcto.

**Hallazgo:** `ConflictResolver.resolve()` espera `list[KnowledgeClaim]` como segundo argumento. Si un resolver necesita metadatos adicionales (contexto de ejecución, config), no tiene cómo recibirlos. `EntityResolver.resolve()` sí incluye `context: dict | None`. Inconsistencia.

**Riesgo:** Bajo. Se puede solventar con `FusionContext` si se pasa como parámetro adicional, pero requeriría cambiar la firma del ABC.

### 1.5 ISP (Interface Segregation)

Todos los ABCs tienen 1-3 métodos. Ninguno fuerza a implementar métodos que no se necesitan.

**Excepción:** `SourceScorer` tiene `score()` y `score_evidence()`. El segundo es un atajo de conveniencia (iterar sobre `EvidenceSet`). Una implementación que solo necesita `score_evidence()` igualmente debe implementar `score()`, y viceversa.

**Riesgo:** Mínimo. Son 2 métodos pequeños. Se podría eliminar `score_evidence()` y dejarlo como función helper externa.

### 1.6 Open/Closed

El sistema está bien diseñado para extensión:
- Nuevas etapas: implementar `PipelineStage` + registrar en `FusionPipeline.register_stage()`
- Nuevos resolvers/scorers/mergers: implementar ABC + registrar en `FusionRegistry`
- Sin modificar código existente

**Hallazgo positivo:** `FusionPipeline.__init__` acepta tanto componentes individuales como una `list[PipelineStage]`, permitiendo composición arbitraria sin herencia.

### 1.7 Métodos Innecesarios / Responsabilidades Mezcladas

| Método | Problema |
|--------|----------|
| `SourceScorer.score_evidence()` | Es un loop sobre `score()`. Factorizable como función externa. |
| `ConflictResolver.resolve()` retorna `list[KnowledgeFact]` | Siempre vacío en la práctica. El resolver no debería crear facts. |
| `EntityResolver.resolve_many()` | Es un loop de `resolve()`. Podría ser helper. |

**Recomendación:** Simplificar `ConflictResolver.resolve()` para retornar solo `list[Conflict]` con campo `resolved` actualizado. Mover creación de facts al Merger.

---

## 2. Pipeline

### 2.1 DAG (Directed Acyclic Graph)

**Estado actual:** Pipeline lineal secuencial (`FusionPipeline.run()` ejecuta `self._stages` en orden).

**¿Puede evolucionar a DAG?** La API lo permite si se añade un orquestador que reciba `list[PipelineStage]` con dependencias. `PipelineStage.execute()` recibe `FusionContext` y retorna `FusionContext` — no conoce el orden ni las dependencias, lo que es necesario para DAG.

**Cambio necesario en F27:** Añadir `depends_on: list[FusionStage]` opcional a `PipelineStage`. El orquestador lo usaría para construir el DAG sin modificar `PipelineStage.execute()`.

**¿Requiere cambios en API pública?** No. `PipelineStage` y `FusionPipeline` no se modifican. Solo se añade un `new DAGPipeline(FusionPipeline)` que herede o envuelva.

### 2.2 Ejecución Paralela

**Estado actual:** `for stage in self._stages: context = stage.execute(context)` → 100% secuencial.

**¿Puede ejecutarse en paralelo?** Sí, si:
1. Las etapas son independientes (ej: EntityResolution y SourceScoring operan sobre claims sin compartir estado mutable)
2. `FusionContext` es thread-safe (ver sección 9)
3. `KnowledgeMerger` debe esperar a EntityResolution + ConflictDetection + SourceScoring

**Limitación:** `FusionContext` usa `list` mutable compartido («context.claims»). Ejecución paralela requeriría copias o locks.

**Patrón recomendado:** `context.copy()` shallow para forks. El orquestador mergea forks al final.

### 2.3 Ejecución Distribuida

**Estado actual:** Monolítica en un solo proceso.

**¿Puede distribuirse?** Sí, si:
1. `FusionContext` es serializable (ver sección 3.5)
2. Cada etapa puede ejecutarse en un worker remoto
3. El orquestador serializa/deserializa `FusionContext` entre etapas

**Limitación:** Las referencias a objetos `Evidence` y `CitationBundle` pueden no ser serializables si contienen objetos complejos o circular references. `Evidence` es `@dataclass` → serializable. `CitationBundle` también es `@dataclass` → serializable.

### 2.4 Etapas Opcionales

**Estado actual:** `FusionPipeline.__init__` permite pasar `stages: list[PipelineStage] | None`. Si es None, no se ejecuta nada.

**¿Pueden hacerse etapas individuales opcionales?** Sí. Basta con que el orquestador salte etapas marcadas como `enabled=False` o `if stage not in context.skip_stages`.

**Cambio necesario:** Añadir `enabled: bool = True` a `PipelineStage`. Coste: 0 en API existente (default=True, backward compatible).

### 2.5 Etapas Condicionales

**Estado actual:** No existe.

**¿Pueden añadirse?** Sí, manteniendo la API. Un `ConditionalStage(PipelineStage)` puede sobreescribir `execute()` para decidir si ejecuta o no basado en `context.statistics` o `context.bundle`.

**Patrón recomendado:**
```python
class ConditionalStage(BaseStage):
    def __init__(self, inner: PipelineStage, condition: Callable[[FusionContext], bool]):
        self._inner = inner
        self._condition = condition
    def _execute(self, ctx: FusionContext) -> FusionContext:
        return self._inner.execute(ctx) if self._condition(ctx) else ctx
```

### 2.6 Conclusión Pipeline

La arquitectura actual soporta todas las evoluciones futuras **sin modificar la API pública** (`PipelineStage.execute()`, `FusionPipeline.run()`, `FusionContext`). Solo se necesitan añadidos en F27 mediante wrapping o herencia.

---

## 3. Modelos

### 3.1 Redundancia de Campos

| Modelo | Campos Redundantes | Impacto |
|--------|--------------------|---------|
| `KnowledgeClaim` | `normalized_text` vs `subject/predicate/object` | Separación correcta: normalización ≠ extracción semántica |
| `KnowledgeClaim` | `evidence` + `source_score` | Ambos apuntan a info de fuente. `source_score` es un derivado calculado, no redundante. |
| `KnowledgeFact` | `evidence` (tupla) + `provenance` (tupla de claim_ids) | `provenance` contiene los claim_ids que originaron el fact. `evidence` contiene los objetos Evidence completos. Hay duplicación de información (los claim_ids también están en Evidence). |
| `SourceScore` | `url` (ya está en `Evidence.document_url`) | Correcto: es un valor copiado para desacoplar. |

**Hallazgo — `Evidence` duplicado en `KnowledgeFact`:** Si 20 claims → 1 fact, se copian 20 `Evidence` objects en `KnowledgeFact.evidence`. Cada `Evidence` contiene `fragment` (el texto completo). Esto puede disparar el uso de memoria.

**Recomendación:** En `KnowledgeFact`, almacenar solo `evidence_ids: tuple[str, ...]` en lugar de objetos `Evidence` completos. El objeto completo se resuelve vía lookup externo.

### 3.2 Mutabilidad Innecesaria

| Modelo | Mutable | Inmutable | Problema |
|--------|---------|-----------|----------|
| `KnowledgeClaim` | ✅ | ❌ | `normalized_text`, `subject`, `predicate`, `object`, `source_score` se modifican durante el pipeline. Correcto. |
| `Conflict` | ✅ | ❌ | `resolved`, `resolution` se modifican durante `resolve()`. Correcto. |
| `KnowledgeFact` | ❌ | ✅ | `frozen=True`. Correcto. |
| `KnowledgeDelta` | ✅ | ❌ | No se modifica después de creado, podría ser frozen. **Riesgo bajo.** |
| `FusionContext` | ✅ | ❌ | Es el estado compartido del pipeline. Debe ser mutable. **Pero:** compartir listas mutables entre etapas es peligroso (ver Thread Safety). |
| `FusionResult` | ❌ | ✅ | Tuples inmutables. Correcto. |

**Recomendación:** Hacer `KnowledgeDelta` frozen. No necesita mutación.

### 3.3 Datos Repetidos

**Hallazgo:** `KnowledgeClaim.created_at` usa `field(default_factory=time.time)`. Si el claim se copia o reconstruye, `created_at` se regenera con la hora actual. Esto rompe la estabilidad de IDs (ver sección 4).

**Impacto:** Si un claim se serializa y deserializa, `created_at` cambia. En `ExtractionStage`, se pasa `created_at=ev.fetched_at`, lo que evita el problema. Pero si alguien construye un `KnowledgeClaim` directamente sin pasar `created_at`, la marca de tiempo será incorrecta.

**Solución:** No usar `default_factory` para `created_at`. Debe ser un campo obligatorio o tener valor por defecto 0.0 (que se interpreta como "no establecido").

### 3.4 Posibles Ciclos

No hay ciclos en los modelos. `KnowledgeClaim` apunta a `Evidence` (sin retroreferencia a `KnowledgeClaim`). `KnowledgeFact.evidence` es tupla de `Evidence` (sin retroreferencia). `FusionContext` contiene listas de claims/facts/entities, pero no hay referencias circulares.

**Veredicto:** Sin ciclos. ✅

### 3.5 Coste de Memoria

| Objeto | Tamaño estimado (bytes) | Notas |
|--------|-------------------------|-------|
| `Evidence` | ~500 | Contiene `fragment` (texto), `document_url`, etc. |
| `KnowledgeClaim` | ~200 + text | `text` es el `fragment` del Evidence (duplicado). |
| `KnowledgeFact` | ~300 + evidence | Contiene tupla de Evidence (duplicado del claim). |
| `StageProvenance` | ~150 | |
| `FusionContext` | ~200 + sum(claims+facts+...) | |

**Hallazgo — Duplicación de texto:**
- `Evidence.fragment` → `KnowledgeClaim.text` (copia)
- `KnowledgeClaim.text` → `KnowledgeClaim.normalized_text` (copia normalizada)
- `KnowledgeFact` almacena los Evidence completos (tercera copia del fragment)

En un pipeline con 1000 claims: el mismo texto se copia 3 veces (~3x uso de memoria).

**Estimación para 10M facts:**
- 10M × KnowledgeFact (~300 bytes) = **~3 GB solo en facts**
- Más los Evidence duplicados en cada fact
- Más los Claims (que pueden ser descartados tras el merge)
- Más el FusionContext residente

**Riesgo:** Alto para 10M facts. Necesario streaming en F26+.

### 3.6 Serialización

**Problema:** `FusionContext.bundle: Any = None` — el campo es `Any`, no `CitationBundle | None`. La serialización depende de qué objeto concreto se asigne.

**Problema:** `FusionContext.statistics: dict[str, Any]` — valores `Any` no son serializables de forma predecible (ej: tipos numpy, objetos personalizados).

**Problema:** `Evidence` contiene `Evidence.fetched_at: float` y `Evidence.quality_score: float` — serializables. Pero `Evidence` está en `motor/core/web/citation/citation.py`, fuera del módulo fusion. Para distribuir el pipeline, `Evidence` debe estar disponible en todos los workers.

**Recomendación:**
1. Reemplazar `bundle: Any` por `bundle: CitationBundle | None` (tipado estricto)
2. Limitar `statistics` a tipos serializables estándar (str, int, float, bool, list, dict)
3. En `KnowledgeFact`, guardar `evidence_ids` en lugar de objetos `Evidence` completos

---

## 4. Provenance

### 4.1 Cobertura Actual

| Componente | ¿Se registra? | Dónde |
|-----------|---------------|-------|
| Pipeline version | ✅ | `FusionProvenance.pipeline_version` |
| Config hash | ✅ | `FusionProvenance.config_hash` |
| Entity resolver name/version | ✅ | `FusionProvenance.resolver_name/version` |
| Conflict resolver name/version | ✅ | `FusionProvenance.conflict_resolver_name/version` |
| Merger name/version | ✅ | `FusionProvenance.merger_name/version` |
| Source scorer name/version | ✅ | `FusionProvenance.source_scorer_name/version` |
| Stages (nombres+versiones) | ✅ | `context.transforms: list[StageProvenance]` |
| Input/output claims por etapa | ✅ | `StageProvenance.input_claims/output_claims` |
| Timestamp por etapa | ✅ | `StageProvenance.timestamp` |

### 4.2 Lo que NO se registra

| Vacío | Impacto |
|-------|---------|
| **Evidence original** que generó cada claim | No hay un mapa `claim_id → evidence_id` en el resultado. El claim tiene `evidence.evidence_id`, pero al convertir a `FusionResult` se pierde la relación. |
| **Configuración completa** usada en la ejecución | Solo se guarda `config_hash`. Para reconstruir la ejecución exacta se necesita el `FusionConfig` original. |
| **Documentos de entrada** (CitationBundle) | No se almacena qué documentos se fusionaron. |
| **Versión del change detector y selector** | Faltan campos en `FusionProvenance`. |
| **Tiempo por etapa** | `FusionPipeline._stage_times` existe pero nunca se rellena. |
| **Decisiones de conflicto** | `Conflict.resolution` almacena texto libre, pero no hay un campo estructurado para registrar qué regla/algoritmo resolvió. |

### 4.3 Capacidad de Reconstrucción

Pregunta: ¿Podemos reconstruir exactamente qué dato llegó, qué algoritmo lo modificó, qué versión, qué configuración, qué etapa, qué evidencia?

| Criterio | ¿Cumple? |
|----------|----------|
| ¿Qué dato llegó? | Parcial — `CitationBundle` original no se preserva en `FusionResult` |
| ¿Qué algoritmo lo modificó? | ✅ — `stage_name` + `version` en cada `StageProvenance` |
| ¿Qué versión? | ✅ — cada etapa reporta su versión |
| ¿Qué configuración? | Parcial — `config_hash` permite verificar si la config cambió, pero no reconstruirla |
| ¿Qué etapa? | ✅ — `StageProvenance.stage_name` |
| ¿Qué evidencia? | Parcial — `KnowledgeClaim.evidence.evidence_id` se preserva, pero `KnowledgeFact` solo guarda el objeto `Evidence` (no es fácilmente indexable) |

**Recomendaciones:**
1. Añadir `evidence_ids: tuple[str, ...]` a `KnowledgeFact` (además o en lugar de `evidence: tuple[Evidence, ...]`)
2. Añadir `bundle_id: str` a `FusionProvenance` para trackear el CitationBundle original
3. Añadir `change_detector_name`, `change_detector_version`, `selector_name`, `selector_version` a `FusionProvenance`
4. Rellenar `FusionPipeline._stage_times` en `run()`
5. Almacenar `FusionConfig` serializado en `FusionProvenance` (no solo el hash)

---

## 5. Entity Resolution

### 5.1 Limitaciones de `RuleBasedEntityResolver`

| Problema | Ejemplo | Impacto |
|----------|---------|---------|
| **Polisemia** | Apple (empresa) vs Apple (fruta) | `RuleBasedEntityResolver.resolve("apple")` siempre retorna empresa. No hay desambiguación por contexto. |
| **Persona vs Empresa** | Tesla (persona) vs Tesla (empresa) | Ídem. |
| **Nombres geográficos** | Amazon (río) vs Amazon (empresa) | Ídem. |
| **Múltiples entidades mismas siglas** | "IBM" es única — sin problema hoy, pero `_KNOWN_ENTITIES` no escala. | |
| **Idiomas** | "Manzana" (fruta, español) vs "Apple" (empresa, inglés) | No hay soporte multi-idioma. |
| **Contexto temporal** | "Apple" en 1976 (startup) vs 2026 (gigante tech) | Misma entidad, diferente contexto histórico. |
| **Alias dinámicos** | "X" (antes Twitter) | El diccionario estático no captura cambios temporales. |
| **Nombres compuestos** | "Berkshire Hathaway" vs "Berkshire" vs "BRK.A" | `EntityResolutionStage` opera palabra por palabra, no sobre frases. |

### 5.2 Arquitectura Necesaria para F26/F27

```
Texto
  ↓
Embedding (text → vector)
  ↓
Vector DB (qdrant) — nearest neighbor contra entidades conocidas
  ↓
ContextualDisambiguator — usa el claim completo (no solo la palabra)
  ↓
ResolvedEntity con status=AMBIGUOUS si no alcanza umbral
```

**Requerimientos arquitectónicos (no implementar ahora):**
1. `EntityResolver` debe recibir el claim completo (no solo `text: str`) — la firma actual `resolve(text: str, context: dict)` lo permite vía `context`.
2. El `EntityResolutionStage` actual opera palabra por palabra. Debe cambiarse para pasar frases enteras al resolver.
3. Se necesita un `EntityResolver` que soporte:
   - Embeddings semánticos (cosine similarity contra entidades conocidas)
   - Desambiguación contextual (BERT/Reranker sobre el claim completo)
   - Umbral de confianza configurable
   - Retorno `AMBIGUOUS` para casos dudosos (ya existe en `ResolutionStatus`)
   - Cache LRU de resoluciones frecuentes

**Riesgo:** `RuleBasedEntityResolver` es aceptable para prototipado pero inútil en producción con polisemia real.

---

## 6. Conflict Detection

### 6.1 Conflictos No Cubiertos por `NaiveConflictResolver`

| Tipo | ¿Cubierto? | Ejemplo |
|------|-----------|---------|
| Contradicción exacta | ✅ | "Apple sells oranges" vs "Apple does NOT sell oranges" |
| Temporal | ❌ | "Rainfall was 100mm in 2020" vs "Rainfall was 200mm in 2024" |
| Granularidad | ❌ | "GDP grew 5%" vs "GDP grew 4.8%" |
| Unidades | ❌ | "Distance is 100 miles" vs "Distance is 160 km" |
| Idiomas | ❌ | "Apple vende naranjas" vs "Apple sells oranges" |
| Sinónimos | ❌ | "Apple sells oranges" vs "Apple distributes citrus fruit" |
| Ambigüos | ❌ | "The bank raised rates" vs "The river bank eroded" (mismo sujeto, diferente entidad) |
| Opiniones | ❌ | "The movie is great" vs "The movie is terrible" |
| Estimaciones | ❌ | "Cost ~$100" vs "Cost $97" |
| Rangos | ❌ | "Temperature 20-25°C" vs "Temperature 22°C" |
| Citas textuales vs paráfrasis | ❌ | "He said 'yes'" vs "He confirmed agreement" |

### 6.2 Limitaciones Arquitectónicas

1. `NaiveConflictResolver._check_pair()` usa `subject.lower() == subject.lower()` — no hay normalización semántica.
2. No usa `normalized_text` para la comparación — usa `subject/predicate/object` directamente.
3. `ConflictType` enum tiene los tipos correctos (`TEMPORAL_UPDATE`, `DIFFERENT_GRANULARITY`, `OPINION`) pero `NaiveConflictResolver` solo emite `CONTRADICTION`.
4. El detector no explota `ConflictType` — todos los conflictos se marcan como `CONTRADICTION`.

**Recomendación:** En B3+, un resolver real debe:
1. Usar `normalized_text` como base de comparación
2. Detectar patrones temporales (fechas, años)
3. Normalizar unidades (km ↔ miles, C ↔ F)
4. Detectar sinónimos vía embeddings o WordNet
5. Clasificar conflictos según `ConflictType` enum

---

## 7. Knowledge Merge

### 7.1 1 Claim → 1 Fact

**Estado actual:** `SimpleKnowledgeMerger` crea exactamente 1 fact por claim, con split naive del texto en subject/predicate/object.

**¿Seguirá siendo válido?** Para B2 sí. Para producción:
- **Múltiples claims sobre la misma entidad** (20 claims sobre Apple) deben fusionarse en 1 fact consolidado
- **Un claim con múltiples afirmaciones** ("Apple sells oranges and bananas") genera varios hechos independientes
- **Claims contradictorios** no resueltos deben excluirse del fact

### 7.2 Casos No Soportados

| Caso | Ejemplo | Lo que debería pasar |
|------|---------|---------------------|
| 20 claims → 1 fact | 20 fuentes dicen "Apple sells oranges" | 1 fact con confidence combinado y 20 evidence_ids |
| 1 claim → varios facts | "Apple sells oranges and bananas" | 2 facts: (Apple, sells, oranges) + (Apple, sells, bananas) |
| Claim sin sujeto/predicado | "Hello world" | No debería generar fact. `SimpleKnowledgeMerger` genera fact basura. |

### 7.3 Hallazgo: `conflicts` no se usa

`KnowledgeMerger.merge(claims, conflicts)` recibe `conflicts` pero ni `SimpleKnowledgeMerger` ni ningún merger futuro obvio lo usa. Los conflictos son relevantes para decidir qué claims incluir/excluir.

**Recomendación:** El merger debe filtrar claims que estén en conflictos no resueltos. Actualmente `conflicts` se ignora.

### 7.4 Hallazgo: `object.__setattr__` en frozen dataclass

```python
object.__setattr__(f, "id", make_fact_id(f.subject, f.predicate, f.object))
```

Esto es necesario porque `KnowledgeFact` es frozen y el ID no se conoce hasta después de construir el fact. Es un code smell — el ID debería calcularse antes de construir.

**Recomendación:** Calcular `make_fact_id()` antes de construir `KnowledgeFact` y pasarlo como argumento.

---

## 8. Escalabilidad

### 8.1 Simulación por Tamaño

| Tamaño | Claims | Facts | Problemas Identificados |
|--------|--------|-------|------------------------|
| 100 | ~100 | ~100 | ✅ Sin problemas |
| 1.000 | ~1.000 | ~1.000 | ✅ Conflictos O(n) bucket-based (~1k buckets) |
| 100.000 | ~100.000 | ~100.000 | ⚠️ Conflictos O(n) (~100k buckets). EntityResolution O(n×m) |
| 10 millones | ~10M | ~10M | ⚠️ Conflictos O(n). Memoria: ~3GB en facts (sin Evidence duplicado) |

### 8.2 Cuellos de Botella

1. **`ConflictResolver.detect()` — O(n²) → ✅ O(n) bucket-based:**
   ```python
   buckets: dict[tuple[str, str], list[KnowledgeClaim]] = {}
   for c in claims:
       key = (c.subject.lower(), c.predicate.lower())
       buckets.setdefault(key, []).append(c)
   for bucket in buckets.values():
       for i, a in enumerate(bucket):
           for b in bucket[i + 1:]:
   ```
   Comparación solo dentro del mismo bucket `(subject, predicate)`.
   Para 100.000 claims con distribución uniforme → coste efectivo O(n).

2. **`EntityResolutionStage` — O(n×m) palabra por palabra:**
   ```python
   for claim in context.claims:  # n claims
       for word in words:  # m palabras por claim
           entity = self._resolver.resolve(word)
   ```
   Cada `resolve()` es O(1) (hash lookup), pero el número total de llamadas = n×m. Para 100.000 claims con 20 palabras cada uno → 2 millones de llamadas.

3. **Copias de listas:**
   - `FusionPipeline.stages` property retorna `list(self._stages)` — copia O(n) en cada acceso
   - `_context_to_result()` copia tuples de facts/claims/conflicts — O(n) al final del pipeline
   - `FusionPipeline._stage_times` property retorna `dict(self._stage_times)` — copia O(1)

4. **`KnowledgeMergerStage` merge secuencial:**
   No hay paralelismo en el merge. 100k claims → 100k operaciones secuenciales.

### 8.3 Objetos Gigantes

- `FusionContext` con 100k claims contiene una `list` de 100k objetos. La copia de `FusionContext` (si se necesita para paralelismo) copia las referencias (shallow), pero la serialización para distribución sería costosa.
- `KnowledgeFact.evidence` — tupla de Evidence con el fragment de texto. 100k facts → 100k copias del texto original.

### 8.4 Listas O(n) y Algoritmos O(n²)

| Operación | Complejidad | 100 claims | 100k claims |
|-----------|-------------|-----------|-------------|
| `detect()` conflictos | O(n) (bucket-based) | ~5k pares (~5k buckets) | ~100k pares (~100k buckets) |
| `resolve()` conflictos | O(c) | O(conflictos) | O(conflictos) |
| EntityResolution (palabras) | O(n×m) | ~1k llamadas | ~2M llamadas |
| `KnowledgeMerger.merge()` | O(n) | 100 | 100k |
| `_context_to_result()` | O(n) | 300 | 300k |
| `register_stage()` | O(1) | 1 inserción | 1 inserción |

**Recomendaciones para escalabilidad:**
1. **Conflict detection:** ✅ **HEALED** — bucket-based O(n) (agrupado por `(subject, predicate)`).
2. **Memory:** FactStream iterable en lugar de `list[KnowledgeFact]`. Procesar facts en lotes (batch processing).
3. **Distribución:** `FusionContext` serializable para pasar entre workers.
4. **Lazy provenance:** No construir `StageProvenance` hasta que se necesite (reducir presión de memoria).

---

## 9. Thread Safety

### 9.1 Estado Compartido Mutable

| Objeto | Thread-Safe? | Razón |
|--------|-------------|-------|
| `FusionContext` | ❌ | `claims`, `entities`, `conflicts`, `facts` son `list` mutables compartidos |
| `FusionPipeline._stages` | ⚠️ | `list` mutable, pero solo se escribe en `__init__` y `register_stage()` |
| `FusionPipeline._stage_times` | ❌ | `dict` mutable, se escribe en `run()` si se implementa timing |
| `KnowledgeClaim` | ❌ | `normalized_text`, `source_score` se mutan en pipeline |
| `Conflict` | ❌ | `resolved`, `resolution` se mutan en `resolve()` |
| `FusionRegistry._*` (dicts) | ❌ | Dicts mutables compartidos sin locks |

### 9.2 Race Conditions Potenciales

1. **Dos threads ejecutando `FusionPipeline.run()` simultáneamente:**
   - Comparten `self._stages` (solo lectura, OK)
   - Cada uno tiene su propio `FusionContext` (no compartido, OK)
   - Pero si las etapas modifican estado global (ej: cache compartido), hay race condition

2. **`FusionRegistry` usado desde múltiples pipelines:**
   - `register_engine()` y `get_engine()` sin locks → race condition si un thread registra mientras otro lee

3. **Etapas con estado interno:**
   ```python
   class MyStage(BaseStage):
       def __init__(self):
           self.counter = 0  # mutable shared state
       def _execute(self, ctx):
           self.counter += 1  # race condition
   ```

### 9.3 Locks Innecesarios

No hay locks en el código actual. Esto es correcto para la arquitectura single-thread actual.

### 9.4 Recomendaciones

1. **Para F27/F28 (paralelismo):** Hacer `FusionRegistry` thread-safe con `threading.Lock` o `copy-on-write`.
2. **Documentar** que `PipelineStage._execute()` no debe tener efectos secundarios en estado compartido entre etapas.
3. **`FusionContext` debe ser owned por un solo thread** — no compartir entre threads.
4. **Patrón fork-join:** Si se paralelizan etapas, cada fork recibe `context.copy()` (copia shallow) y los resultados se mergean al final.

---

## 10. API Pública — Congelación para v2.x

### 10.1 API Pública Actual

La API pública se define en `motor/core/fusion/__init__.py`:

```python
# ABCs
ChangeDetector, ConflictResolver, EntityResolver, FusionEngine,
KnowledgeMerger, MemoryCandidateSelector, PipelineStage, SourceScorer

# Modelos (exportados)
Conflict, ConflictType, EvidenceSet, FusionContext, FusionProvenance,
FusionResult, KnowledgeClaim, KnowledgeDelta, KnowledgeFact,
ResolutionStatus, ResolvedEntity, SourceScore, StageProvenance

# Funciones
make_claim_id, make_conflict_id, make_fact_id

# Config
FusionConfig

# Pipeline
FusionPipeline, FusionStage

# Registry
FusionRegistry
```

### 10.2 ¿Puede Congelarse?

| Componente | ¿Congelable? | Riesgo |
|-----------|-------------|--------|
| ABCs | ✅ | Interfaces estables. Nuevas capacidades vía nuevos ABCs. |
| Modelos (dataclasses) | ✅ | Añadir campos opcionales es backward compatible. No eliminar campos existentes. |
| `FusionPipeline` | ⚠️ | `register_stage()` y `stages` property pueden necesitar `depends_on`, `enabled`, `conditional`. |
| `FusionRegistry` | ✅ | Registro get/set/list estable. |
| `FusionConfig` | ✅ | Nuevos campos opcionales (defaults backward compatible). |
| Funciones ID | ✅ | Algoritmo SHA-256 fijo. El ID no cambiará. |

**Riesgo:** `FusionProvenance` necesitará nuevos campos (change_detector, selector, evidence_ids). Añadir campos con `""` o `0` como default es backward compatible.

### 10.3 Lo Que NO Debe Cambiar

- Firmas de ABCs (modificar = breaking change)
- Nombres de modelos exportados
- Algoritmo de IDs deterministas (cambiarlo rompe referencias externas)
- Formato de `FusionResult` (consumidores externos dependen de él)

### 10.4 Lo Que Puede Cambiar (backward compatible)

- Añadir campos opcionales a dataclasses
- Nuevos ABCs (nuevas interfaces, no modificar existentes)
- Nuevos `ConflictType` enum values
- Nuevos `FusionStage` enum values
- Implementaciones concretas en `stages/`

**Veredicto:** La API puede congelarse para v2.x con cambios mínimos (añadir campos opcionales a `FusionProvenance` y `FusionContext`).

---

## 11. Código Muerto

### 11.1 Campos Nunca Usados

| Archivo | Campo/Objeto | Estado |
|---------|-------------|--------|
| `base.py:12` | `from __future__ import annotations` duplicado | ❌ Duplicado. Línea 10 y 12. Eliminar. |
| `engine.py:68` | `self._stage_times` | ⚠️ Inicializado pero nunca escrito (solo leído vía property). Dead code si no se implementa el timing. |
| `engine.py:112-113` | `self._engine.fuse()` | ⚠️ `FusionEngine.fuse()` no tiene implementaciones concretas. El branch nunca se ejecuta. |
| `stages/conflict_detection.py:44` | `resolved_facts: list[KnowledgeFact] = []` | ❌ `NaiveConflictResolver.resolve()` siempre retorna lista vacía. |

### 11.2 Interfaces Sobrantes

| Interface | Uso actual | ¿Necesaria? |
|-----------|-----------|-------------|
| `FusionEngine` | No tiene implementaciones. Nunca se usa en B2. | ⚠️ Puede eliminarse hasta B3/B4. Mantener por diseño. |
| `MemoryCandidateSelector` | `ThresholdSelector.select()` acepta `FusionResult` pero `MemoryCandidateSelectionStage._execute()` no lo llama. | ⚠️ Placeholder. No implementado realmente. |

### 11.3 Duplicación

| Archivo | Problema |
|---------|----------|
| `stages/__init__.py` | Re-exporta todas las clases. Código de importación repetitivo pero necesario para la API. |
| `__init__.py` y `stages/__init__.py` | Ambos exportan clases, a diferentes niveles. Solapamiento parcial. |

### 11.4 Constantes

| Constante | Valor | ¿Se usa? |
|-----------|-------|----------|
| `FusionConfig.authority_weight` | 0.4 | ❌ `QualitySourceScorer` usa pesos hardcodeados (0.5, 0.5), no lee de `FusionConfig` |
| `FusionConfig.freshness_weight` | 0.3 | ❌ Ídem |
| `FusionConfig.relevance_weight` | 0.3 | ❌ Ídem |

**Recomendación:** `QualitySourceScorer` debería aceptar `FusionConfig` o al menos leer los pesos de configuración. Actualmente los ignora.

---

## 12. Preparación para F26

### 12.1 ¿Soporta la arquitectura actual...?

| Requisito F26 | ¿Soportado? | Notas |
|--------------|------------|-------|
| **Memoria histórica** | Parcial | `FusionContext` no tiene campo para facts históricos. `KnowledgeDeltaStage` recibe `existing_facts` vía `statistics` (hack). |
| **Versionado** | ✅ | `KnowledgeFact.version`, `superseded_by`, y `KnowledgeDelta.snapshot_support` están diseñados para versionado. |
| **Aprendizaje** | ❌ | No hay mecanismo para que el pipeline aprenda de ejecuciones anteriores. `EntityResolver` y `ConflictResolver` son estáticos. |
| **Embeddings** | ✅ | `EntityResolver.resolve(text, context)` permite pasar embeddings vía `context`. `SourceScorer` puede usar embeddings para relevance. |
| **Reindexación** | ⚠️ | Requiere que los IDs deterministas (`make_fact_id`) sean estables. Lo son. Pero no hay un proceso de reindexación definido. |
| **Feedback** | ❌ | No hay `FusionFeedback` ni mecanismo para incorporar feedback de usuarios/agentes. `FusionResult` no tiene campo para feedback. |
| **Config dinámica** | ⚠️ | `FusionConfig` es estática. No hay reload en caliente. |

### 12.2 Lo Que Habría Que Añadir Sin Refactorizar F25

1. **Memoria histórica:** Añadir `field existing_facts: list[KnowledgeFact] = field(default_factory=list)` a `FusionContext`. Backward compatible.
2. **Feedback:** Añadir `field feedback: dict[str, Any] = field(default_factory=dict)` a `FusionResult`. Backward compatible.
3. **Aprendizaje:** Nuevo ABC `FusionLearner` que reciba `list[FusionResult]` y emita sugerencias de configuración. No modifica F25.
4. **Reindexación:** Script externo que lea facts almacenados, ejecute `make_fact_id()` con nueva configuración, y detecte cambios.
5. **Config dinámica:** Añadir `FusionConfig.reload()` que lea de fuente externa. No rompe API.

### 12.3 Riesgos para F26

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| `FusionContext.statistics` como `dict[str, Any]` | F26 necesitará campos tipados. Migrar a dataclass estructurada rompe API. | Añadir campos tipados a `FusionContext` (backward compatible) y deprecar `statistics` gradualmente. |
| `KnowledgeFact.evidence` como `tuple[Evidence, ...]` | F26 necesitará referencias a evidence sin cargar el objeto completo. | Añadir `evidence_ids: tuple[str, ...]` y marcar `evidence` como deprecated. |
| Sin soporte de streaming | F26 con 10M facts no puede cargar todo en memoria. | Implementar `FactStream` como iterador lazy (ABC aparte, no modifica KnowledgeFact). |

---

## 13. Índice Interno de Hechos (Diseño para F26)

### 13.1 Problema

Cuando el sistema acumula miles de `KnowledgeFact`, F26 necesitará responder preguntas como:

- ¿Qué sabes sobre **NVIDIA**?
- ¿Qué sabes sobre **Jensen Huang**?
- ¿Qué sabes sobre **CUDA**?

Recorrer `list[KnowledgeFact]` linealmente no escala. Sin un índice, cada consulta es O(n).

### 13.2 Arquitectura Propuesta

```
entity_id ──→ [fact_id_1, fact_id_2, ...]
predicate ──→ [fact_id_3, fact_id_5, ...]
(subject, predicate) ──→ [fact_id_1, fact_id_2]
```

Tres índices invertidos (tipo posting list):

```python
@dataclass
class FactIndex:
    by_entity: dict[str, list[str]]          # entity_id → [fact_ids]
    by_predicate: dict[str, list[str]]        # predicate → [fact_ids]
    by_subject_predicate: dict[tuple[str, str], list[str]]  # (subject, predicate) → [fact_ids]
```

### 13.3 Operaciones Soportadas

| Consulta | Índice | Complejidad |
|----------|--------|-------------|
| Facts sobre entidad X | `by_entity[X]` | O(1) |
| Facts con predicado Y | `by_predicate[Y]` | O(1) |
| Facts con (sujeto=X, predicado=Y) | `by_subject_predicate[(X,Y)]` | O(1) |
| Hechos actualizados en ventana temporal | Fecha almacenada en `KnowledgeFact.created_at` + filtro | O(k) sobre resultado |
| Conflicts que involucran a X | Resolver `by_entity[X]` + lookup en Conflict.conflict_ids | O(k) |

### 13.4 Integración con F25 (Sin Romper API)

```python
@dataclass
class FactIndex:
    by_entity: dict[str, list[str]] = field(default_factory=dict)
    by_predicate: dict[str, list[str]] = field(default_factory=dict)
    by_subject_predicate: dict[tuple[str, str], list[str]] = field(default_factory=dict)

    def index(self, fact: KnowledgeFact) -> None:
        self.by_entity.setdefault(fact.subject.lower(), []).append(fact.id)
        self.by_predicate.setdefault(fact.predicate.lower(), []).append(fact.id)
        self.by_subject_predicate.setdefault(
            (fact.subject.lower(), fact.predicate.lower()), []
        ).append(fact.id)

    def facts_about(self, entity: str) -> list[str]:
        return self.by_entity.get(entity.lower(), [])

    def facts_with_predicate(self, predicate: str) -> list[str]:
        return self.by_predicate.get(predicate.lower(), [])
```

**No se añade a `FusionContext` ni a `FusionResult`** — es un componente interno de F26 que consume `KnowledgeFact` sin modificar el pipeline.

### 13.5 Estado para F25

No implementar ahora. Solo diseño. Este índice se construirá en F26 cuando exista un `FactStore` que persista facts y los indexe al vuelo.

### 13.6 Relación con D01 (Bucket-based Conflict Detection)

El bucket actual `(subject, predicate)` en `NaiveConflictResolver` es un precursor del índice `by_subject_predicate`. Cuando exista `FactIndex`, `ConflictResolver.detect()` podrá consultar `index.by_subject_predicate[(s, p)]` en lugar de reconstruir los buckets cada vez.

---

## Resumen de Hallazgos

### Fortalezas

1. **Separación clara de responsabilidades** en 8 ABCs
2. **Pipeline extensible** sin modificar el orquestador
3. **IDs deterministas** (SHA-256) — reproducibilidad garantizada
4. **Modelos documentados** con reglas explícitas (frozen fact, mutable claim)
5. **Provenance por etapa** — cada transformación deja registro
6. **FusionRegistry** desacopla implementaciones concretas
7. **API pública limpia** en `__init__.py` con `__all__`

### Debilidades

| # | Debilidad | Prioridad | Área |
|---|-----------|-----------|------|
| D01 | `ConflictResolver.detect()` O(n²) | 🔴 Alta → ✅ **FIXED** | Escalabilidad |
| D02 | Duplicación de texto (Evidence → Claim → Fact) 3x | 🔴 Alta → ✅ **FIXED** | Memoria |
| D03 | `FusionProvenance` incompleto (faltan change_detector, selector, evidence_ids) | 🟡 Media → ✅ **FIXED** | Provenance |
| D04 | `EntityResolutionStage` palabra por palabra sin contexto | 🟡 Media | Entity Resolution |
| D05 | `NaiveConflictResolver` solo detecta CONTRADICTION | 🟡 Media | Conflict Detection |
| D06 | `KnowledgeMerger.merge()` ignora `conflicts` | 🟡 Media | Merge |
| D07 | `FusionConfig` no se usa en `QualitySourceScorer` (pesos hardcodeados) | 🟢 Baja | Config |
| D08 | `object.__setattr__` en frozen dataclass | 🟢 Baja | Code Smell |
| D09 | `from __future__ import annotations` duplicado | 🟢 Baja | Código muerto |
| D10 | `SourceScorer.score_evidence()` innecesario | 🟢 Baja | ISP |

### Riesgos

| # | Riesgo | Probabilidad | Impacto |
|---|--------|-------------|---------|
| R01 | `FusionContext` con 100k+ claims satura RAM | Alta | 🔴 Crítico |
| R02 | `ConflictResolver.detect()` O(n²) bloquea pipeline >10k claims | ✅ **MITIGATED** (bucket-based O(n)) | 🔴 Crítico |
| R03 | F26 requiere campos tipados en `FusionContext` que rompan API actual | Media | 🟡 Alto |
| R04 | Serialización distribuida falla por `bundle: Any` | Baja | 🟡 Medio |
| R05 | Pipeline no thread-safe para F28 paralelo | Media | 🟡 Medio |

### Deuda Técnica

| ID | Deuda | Esfuerzo | Prioridad |
|----|-------|----------|-----------|
| TD01 | Implementar hash-based conflict dedup (O(n) en lugar de O(n²)) | ✅ **DONE** (bucket-based) | 🔴 Alta |
| TD02 | Añadir `evidence_ids: tuple[str, ...]` a KnowledgeFact | ✅ **DONE** | 🟡 Media |
| TD03 | Completar `FusionProvenance` con todos los componentes | ✅ **DONE** (change_detector, selector) | 🟡 Media |
| TD04 | Añadir `FusionConfig` a `QualitySourceScorer` | 1h | 🟢 Baja |
| TD05 | Eliminar `from __future__ import annotations` duplicado | ✅ **DONE** | 🟢 Baja |
| TD06 | Reemplazar `object.__setattr__` con pre-cálculo de ID | ✅ **DONE** | 🟢 Baja |

---

---

## Addendum: Post-Audit Strategic Feedback (2026-07-17)

Tras la auditoría, se recibió feedback estratégico que redefine la prioridad real de F25. Se incorpora aquí como guía para B3+.

### Prioridad Real de F25 (Reordenada)

| Área | Peso | Razón |
|------|------|-------|
| **Entity Resolution** | **40%** | Si resuelve mal entidades, todo lo demás opera sobre información incorrecta. Es el módulo más difícil de todo URA — más que implementar un proveedor LLM. |
| **Conflict Detection** | **25%** | Conflictos temporales, por granularidad, alcance, unidades, opiniones, estimaciones. Necesita dejar de ser un algoritmo y convertirse en un motor. |
| **Source Scoring** | **15%** | Será el corazón del sistema. No solo TLD+freshness, sino: authority, precision, agreement, citation chain, domain expertise, cross validation, timestamp decay, internal consistency, entity confidence. |
| **Knowledge Merge** | **10%** | No debe decidir. Solo materializar hipótesis. ConflictResolver genera hipótesis → Merger materializa. |
| **Delta Detection** | **5%** | Estable, cambios menores. |
| **Memory Selection** | **5%** | Placeholder hasta F26. |

### Riesgo Central: Representación del Conocimiento

El problema actual no es de código — es de representación del conocimiento. Ejemplo:

```python
"Apple bought Beats."
"Apple adquirió Beats Electronics."
"Apple compra Beats."
```

Hoy son 3 claims distintos. No hay fusión semántica. F25 debe dedicar más esfuerzo a la representación que a añadir nuevas clases.

### Cambios Realizados Inmediatamente (Audit-Fix Round)

| ID | Cambio | Archivos | Impacto |
|----|--------|----------|---------|
| **D01** | `ConflictResolver.detect()` → bucket-based | `stages/conflict_detection.py` | O(n²) → O(n). Agrupación por `(subject, predicate)`. |
| **D02** | Eliminar duplicación texto | `models.py`, `stages/extraction.py`, `stages/merger.py` | `text_id` en KnowledgeClaim. `evidence_ids` en KnowledgeFact (sin Evidence duplicado). `object.__setattr__` eliminado. |
| **D03** | Completar FusionProvenance | `models.py`, `stages/delta.py`, `stages/selector.py`, `stages/source_scorer.py`, `stages/merger.py` | 4 campos nuevos (change_detector, selector). Cada stage registra su nombre+versión. |
| **D08** | Pre-cálculo de ID en merger | `stages/merger.py` | `make_fact_id()` antes de construir KnowledgeFact. |
| **D09** | Duplicado `from __future__` | `base.py` | Línea 12 eliminada. |

### Lo Que NO Se Debe Tocar Todavía

- ❌ Optimizaciones prematuras
- ❌ Índices y bases de datos
- ❌ Paralelización
- ❌ GPU
- ❌ Embeddings avanzados

La representación del conocimiento es mucho más importante que cualquier optimización en este punto.

### Próximos Pasos Recomendados (B3+)

1. **Entity Resolution (prioridad #1):**
   - `EntityResolver` debe recibir el claim completo (contexto), no solo palabras sueltas
   - Desambiguación contextual (Apple empresa vs fruta, Tesla persona vs empresa, Washington ciudad/estado/gobierno/persona)
   - Embeddings semánticos + Vector DB lookup
   - Cache LRU de resoluciones frecuentes

2. **Conflict Detection (prioridad #2):**
   - Dejar de ser un algoritmo de reglas fijas
   - Conflictos temporales (CEO=A, CEO=B — ambos verdaderos en distinto tiempo)
   - Granularidad (Europa vs España — no contradictorio)
   - Alcance (coches vs vehículos eléctricos)
   - Probabilístico (90% vs 80% vs 95%)
   - Opiniones ("es el mejor" vs "es excelente" — no son hechos)

3. **KnowledgeMerger (riesgo arquitectónico):**
   - No debe decidir qué versión es correcta
   - `ConflictResolver` genera hipótesis → `KnowledgeMerger` solo materializa
   - Si el Merger empieza a decidir, mezcla responsabilidades

 4. **Scoring (corazón del sistema):**
   - No solo reglas, sino scoring multicriterio
   - source_authority, historical_precision, agreement, citation_chain, domain_expertise, author_credibility, publisher, cross_validation, timestamp_decay, document_quality, internal_consistency, retrieval_confidence, entity_confidence

### Retos Arquitectónicos Emergentes (Post-Audit)

Tres retos que la auditoría identificó pero que merecen atención específica por su impacto estructural:

| # | Reto | Naturaleza | Implicación para F26 |
|---|------|-----------|---------------------|
| R06 | **Índice interno de hechos** | Arquitectónico (no mejora) | Sin índice, consultas sobre 100k+ facts requieren O(n). Necesario `FactIndex` con `by_entity`, `by_predicate`, `by_subject_predicate`. Ver sección 13. |
| R07 | **Versionado temporal en cadena** | Arquitectónico | `KnowledgeFact.superseded_by` (1 nivel) es insuficiente. F26 necesitará `Fact → Version → Version → Version` para responder "qué sabía el sistema hace dos semanas". |
| R08 | **Entity Resolution** | El módulo más complejo de URA | Mezcla: aliases, contexto, embeddings, conocimiento previo, scoring, desambiguación. `RuleBasedEntityResolver` es válido para prototipado pero debe reemplazarse antes de producción. |

### Métricas de Calidad (F25+)

A partir de F25, el número de tests deja de ser el indicador principal de avance. Un sistema de fusión puede superar el 100% de los tests y, aun así, tomar malas decisiones semánticas. Estas métricas son criterios de aceptación con la misma importancia que `pytest`, `ruff` o `py_compile`.

Organizadas por capas:

#### Calidad Semántica

| Métrica | Target | Cómo se mide |
|---------|--------|-------------|
| **Entity resolution accuracy** | >95% | Claims de prueba con entidades conocidas vs resueltas |
| **Conflict precision** | >98% | Conflictos detectados que son conflictos reales |
| **Conflict recall** | >95% | Conflictos reales que fueron detectados |
| **False merge rate** | <1% | Facts mal fusionados sobre total de facts |
| **Duplicate fact rate** | <0.5% | Facts duplicados sobre total de facts |

#### Rendimiento

| Métrica | Target | Cómo se mide |
|---------|--------|-------------|
| **Resolution latency p50** | <50ms | Tiempo medio del pipeline completo |
| **Resolution latency p99** | <500ms | Tiempo del percentil 99 |
| **Fact lookup p50** | <5ms | Búsqueda de fact por entity_id una vez indexado |
| **Fact lookup p99** | <50ms | Búsqueda de fact por entity_id en el percentil 99 |

#### Reproducibilidad

| Métrica | Target | Cómo se mide |
|---------|--------|-------------|
| **Knowledge Stability** | >99.9% | Mismo corpus + misma configuración → mismo conjunto de KnowledgeFact. Detectar no determinismo en el pipeline. |
| **Provenance completeness** | 100% | Cada hecho tiene toda la información necesaria para reconstruir su origen. |
| **Provenance coverage** | 100% | Todos los hechos tienen procedencia. No solo algunos. |

#### Escalabilidad

| Métrica | Target | Cómo se mide |
|---------|--------|-------------|
| **Incremental update cost** | O(Δ) | Facts actualizados ÷ total facts ∝ evidence cambiada. Si 1 evidence nueva → 200k facts recalculados, hay problema de diseño. |
| **Peak RAM por millón de hechos** | TBD | Monitorizar tras primera carga realista. |
| **Index build time** | TBD | Tiempo de construcción del FactIndex sobre corpus de referencia. |

Estas métricas deben incorporarse en CI y medirse contra un corpus de referencia antes de cada release (adaptación de `ADR-012-01` para F25).

### Dependencia Vertical (F25 → F26 → F27)

A diferencia de F1–F24 (fases independientes), a partir de F25 existe una cadena de dependencia:

```
F24 Web Intelligence
        │
        ▼
F25 Knowledge Fusion      ← Estamos aquí
        │
        ▼
F26 Historical Memory
        │
        ▼
F27 Autonomous Agents
```

Cualquier defecto conceptual en F25 se propagará a F26 y F27. Esto tiene dos implicaciones:

1. **F25 debe tener criterios de aceptación más exigentes** que cualquier fase anterior. No es solo "funciona en el caso feliz" — necesita garantías de estabilidad, reproducibilidad y escalabilidad desde el inicio.
2. **Una vez cerrada F25, no deberían hacerse cambios retroactivos** salvo errores críticos. Toda nueva capacidad debe añadirse en F26 o F27, no modificando F25.

Esto refuerza la política de congelación de API (sección 10) y la necesidad de las métricas de calidad como criterio de aceptación.

---

## Conclusión

**Veredicto: APROBADO con condiciones.**

La arquitectura de F25-B1/B2 es sólida y soporta la evolución a F26/F27/F28 sin romper la API pública. Los problemas identificados son principalmente de implementación (B2) más que de diseño (B1). El reto, a partir de ahora, ya no es de ingeniería de software sino de **ingeniería del conocimiento**.

**Condiciones para continuar a B3:**
1. ✅ D01 (bucket-based conflict) — **FIXED**
2. ✅ D02 (text duplication) — **FIXED**
3. ✅ D03 (provenance completeness) — **FIXED**
4. Entity Resolution como prioridad #1 (~40% del esfuerzo)
5. Conflict Detection como prioridad #2 (~25%), dejando de ser algoritmo de reglas
6. KnowledgeMerger no debe decidir — solo materializar hipótesis
7. No añadir más campos a `statistics: dict` — usar campos tipados en `FusionContext`
8. Índice interno de hechos como pieza arquitectónica obligatoria para F26 (no mejora)
9. Versionado temporal en cadena (Fact → Version → Version) planificado para F26
10. Incorporar cuadro de métricas (calidad semántica, rendimiento, reproducibilidad, escalabilidad) en CI como criterios de aceptación al mismo nivel que pytest/ruff
