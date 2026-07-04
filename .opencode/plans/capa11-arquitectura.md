# CAPA 11 — Diseño Arquitectónico

## Principios rectores

1. **El núcleo no conoce Neo4j, PostgreSQL ni Kafka.**  
   Se relaciona con ellos mediante `Protocol`s. Las implementaciones por defecto son SQLite e InMemory.

2. **compiler.py no contiene OpenLineage.**  
   El compilador emite eventos internos vía `EventBus`. Los suscriptores traducen a OpenLineage.

3. **Cada tipo de activo (doc, vídeo, imagen, PDF, Git, conversación) tiene su propio Extractor.**  
   No hay un `metadata_extractor.py` monolítico.

4. **KnowledgeAsset extiende el modelo actual sin romper compatibilidad.**  
   `Document`, `SourceObject`, `CompileResult` siguen funcionando. `KnowledgeAsset` los envuelve.

5. **La ontología es un paquete, no un archivo.**  
   `ontology/` con submódulos para Schema.org, mapeo interno, registry.

6. **Determinismo, API, esquema y 175 tests no se rompen.**  
   Capa 11 es additiva: nuevos módulos, cero cambios en los existentes salvo adaptadores explícitos.

---

## 1. Modelo base: KnowledgeAsset

```
KnowledgeAsset (Protocol)
├── asset_id: str
├── asset_type: AssetType (markdown | video | image | audio | pdf | conversation | git_repo | …)
├── content_sha256: str
├── metadata: AssetMetadata (dict[str, Any] con Schema.org JSON-LD)
├── source: AssetSource (github | filesystem | api | upload | …)
├── relationships: list[AssetRelationship]
├── quality: float         # 0.0 - 1.0 (derivado de confidence, feedback, freshness)
├── created_at: str
└── updated_at: str
```

`KnowledgeAsset` NO reemplaza a `Document` ni `SourceObject`.  
`SourceObject` sigue siendo el modelo interno del scanner/compiler.  
`KnowledgeAsset` es el modelo de la capa de metadatos, creado por extractores y persistido en el grafo.

```python
@dataclass(frozen=True)
class AssetType(StrEnum):
    MARKDOWN = "markdown"
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    PDF = "pdf"
    CONVERSATION = "conversation"
    GIT_REPO = "git_repo"
    API_REFERENCE = "api_reference"
    BUG_REPORT = "bug_report"
    INCIDENT = "incident"
    DECISION = "decision"

@dataclass(frozen=True)
class AssetSource:
    kind: str          # "github" | "filesystem" | "api" | "upload" | "compile"
    location: str      # URL, path, o identificador
    fetched_at: str    # ISO datetime

@dataclass(frozen=True)
class AssetRelationship:
    target_id: str
    relation: str      # "fixes" | "depends_on" | "references" | "generates" | …
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Compatibilidad con modelo actual

| Modelo actual | Relación con KnowledgeAsset |
|---|---|
| `SourceObject` | Un extractor `SourceExtractor` produce `KnowledgeAsset` desde `SourceObject` |
| `Document` | `Document` sigue siendo el DTO del compiler. `KnowledgeAsset` lo envuelve con metadatos adicionales |
| `CompileResult` | `CompileResult` no cambia. Un `EventBus` suscriptor genera `KnowledgeAsset` desde el resultado |
| `AuditEvent` | `AuditEvent` sigue igual. Un extractor de auditoría produce assets de tipo `DECISION` / `INCIDENT` |

---

## 2. Extractor(Protocol)

```python
class Extractor(Protocol):
    """Extrae metadatos de una fuente y produce KnowledgeAssets."""
    
    asset_type: AssetType
    supported_sources: list[str]  # ["github", "filesystem", "api", …]

    def can_handle(self, source: AssetSource) -> bool: ...
    def extract(self, source: AssetSource) -> ExtractionResult: ...

@dataclass
class ExtractionResult:
    asset: KnowledgeAsset | None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    lineage_events: list[dict] = field(default_factory=list)  # OpenLineage opcional
```

### Extractores específicos

| Extractor | asset_type | Fuente |
|---|---|---|
| `MarkdownExtractor` | MARKDOWN | Filesystem (source/), GitHub |
| `VideoExtractor` | VIDEO | Filesystem, URL |
| `ImageExtractor` | IMAGE | Filesystem, URL |
| `PDFExtractor` | PDF | Filesystem, upload |
| `ConversationExtractor` | CONVERSATION | Slack export, API |
| `GitExtractor` | GIT_REPO | GitHub API, local clone |
| `AuditExtractor` | INCIDENT / DECISION | op_audit, feedback |
| `CompileExtractor` | API_REFERENCE | compile pipeline output |

### Registry

```python
_EXTRACTORS: dict[AssetType, list[Extractor]] = {}

def register_extractor(extractor: Extractor) -> None: ...
def get_extractors(asset_type: AssetType | None = None) -> list[Extractor]: ...
def extract_all(source: AssetSource) -> list[ExtractionResult]: ...
```

---

## 3. Ontology como paquete

```
knowledge/engine/ontology/
├── __init__.py          # re-exports
├── registry.py          # AssetType → Schema.org mapping
├── schema_org.py        # Templates: software_version, bug_report, person, organization
├── internal.py          # Modelos internos (AssetType, AssetRelationship, KnowledgeAsset)
└── mapping.py           # knowledge_asset → Schema.org JSON-LD, knowledge_asset → DCAT
```

`ontology/schema_org.py` contiene los templates que producen JSON-LD válido:
```python
def software_version(name, version, release_date, description, bugs=None) -> dict: ...
def bug_report(identifier, description, status, severity, affected_versions=None) -> dict: ...
def person(name, email, url) -> dict: ...
def dcat_dataset(name, description, format, access_url, creator, issued) -> dict: ...
```

---

## 4. EventBus como único punto de integración

### Flujo actual (sin cambios):

```
compile_source()
    ↓
EventBus.publish(CompileCompleted(...))
    ↓
Subscriber: enqueue_archive_job (existente)
Subscriber: get_audit().log_compile (existente)
Subscriber: record_compile (existente)
```

### Flujo nuevo (Capa 11):

```
compile_source()
    ↓
EventBus.publish(CompileCompleted(...))
    ↓
Subscriber: OpenLineageSubscriber  ← NUEVO
    ↓
OpenLineageSubscriber.handle(event)
    ├── Construye evento OpenLineage
    ├── Lo envía al LineageStore
    └── LineageStore (Protocol) → SQLiteLineageStore | Neo4jLineageStore
```

**compiler.py NO cambia.** Solo se añade un suscriptor nuevo.

```python
class OpenLineageSubscriber:
    """Convierte eventos internos a OpenLineage y los persiste."""
    
    def __init__(self, store: LineageStore):
        self._store = store
    
    def on_compile_completed(self, event: CompileCompleted) -> None:
        ol_event = {
            "eventType": "COMPLETE",
            "eventTime": datetime.now(UTC).isoformat(),
            "run": {"runId": event.correlation_id},
            "job": {"namespace": "knowledge.engine", "name": "compile"},
            "inputs": [{"namespace": "source", "name": event.reason}],
            "outputs": [{"namespace": "knowledge.db", "name": "kg_nodes"}],
        }
        self._store.store(ol_event)
```

---

## 5. Almacenes (Protocol + implementaciones default)

| Almacén | Protocol | Default | Alternativa |
|---|---|---|---|
| AssetStore | `store(asset)`, `get(asset_id)`, `search(query)` | `SQLiteAssetStore` (tabla `op_assets`) | `Neo4jAssetStore` |
| LineageStore | `store(event)`, `get_lineage(asset_id)` | `SQLiteLineageStore` (tabla `op_lineage`) | `Neo4jLineageStore` |
| GovernanceStore | `store(policy)`, `check(asset_id, action)` | `InMemoryGovernanceStore` | `PostgreSQLGovernanceStore` |
| MemoryStore | `store(conversation)`, `search(query)` | `SQLiteMemoryStore` | `VectorMemoryStore` |

Todos los `*Store` son `Protocol`s. El núcleo nunca importa Neo4j ni Kafka.

---

## 6. Integración con el núcleo existente — tabla de cambios

| Archivo actual | ¿Cambia? | ¿Cómo? |
|---|---|---|
| `models.py` | ✅ Añade | `KnowledgeAsset`, `AssetType`, `AssetSource`, `AssetRelationship` (nuevas clases, no modifican las existentes) |
| `eventbus.py` | ❌ No cambia | Se usa tal cual |
| `subscribers.py` | ✅ Añade | `OpenLineageSubscriber`, `AssetIndexSubscriber` |
| `compiler.py` | ❌ No cambia | Solo emite eventos vía `EventBus` (ya lo hace) |
| `reader.py` | ❌ No cambia | |
| `cli.py` | ✅ Añade | Comandos: `ke metadata extract`, `ke metadata query`, `ke ontology list` |
| `api.py` | ✅ Añade | Endpoints: `/metadata/assets`, `/metadata/lineage/{asset_id}`, `/metadata/governance/check` |
| `scanner.py` | ❌ No cambia | |
| `parser.py` | ❌ No cambia | |
| `__init__.py` | ✅ Añade | Exporta `KnowledgeAsset`, `Extractor`, `ontology` |
| `pyproject.toml` | ❌ No cambia | Sin nuevas dependencias externas |

---

## 7. Roadmap rediseñado (sin romper nada)

### Fase 0 — Modelo de activos + Ontology (1 semana)
```
□ knowledge/engine/ontology/internal.py    — KnowledgeAsset, AssetType, AssetSource, AssetRelationship
□ knowledge/engine/ontology/schema_org.py  — Schema.org templates
□ knowledge/engine/ontology/registry.py    — AssetType ↔ Schema.org mapping
□ knowledge/engine/ontology/mapping.py     — KnowledgeAsset → JSON-LD
□ knowledge/engine/ontology/__init__.py    — re-exports
□ knowledge/engine/models.py               — Añade import de ontology (sin modificar nada existente)
□ Tests: KnowledgeAsset creación, serialización, compatibilidad con Document
```

### Fase 1 — Extraction layer (1 semana)
```
□ knowledge/engine/extractors/__init__.py       — Extractor(Protocol), ExtractionResult, register_extractor
□ knowledge/engine/extractors/markdown.py       — MarkdownExtractor (desde SourceObject)
□ knowledge/engine/extractors/audit.py          — AuditExtractor (desde op_audit → INCIDENT/DECISION)
□ knowledge/engine/extractors/compile.py        — CompileExtractor (desde CompileCompleted event)
□ knowledge/engine/asset_store.py               — AssetStore(Protocol) + SQLiteAssetStore
□ knowledge/engine/subscribers.py               — Añade AssetIndexSubscriber
□ Tests: cada extractor, AssetStore CRUD
```

### Fase 2 — Lineage + Governance (1 semana)
```
□ knowledge/engine/lineage_store.py        — LineageStore(Protocol) + SQLiteLineageStore
□ knowledge/engine/governance_store.py     — GovernanceStore(Protocol) + InMemoryGovernanceStore
□ knowledge/engine/subscribers.py          — Añade OpenLineageSubscriber
□ CLI: ke metadata extract, ke metadata query
□ Tests: lineage events, governance checks
```

### Fase 3 — Memory + API (1 semana)
```
□ knowledge/engine/memory_store.py          — MemoryStore(Protocol) + SQLiteMemoryStore
□ knowledge/engine/api.py                   — Endpoints /metadata/assets, /metadata/lineage/{id}
□ knowledge/engine/cli/metadata.py          — CLI commands
□ Tests: API endpoints, memory CRUD
```

### Fase 4 — GraphRAG integration (1 semana)
```
□ knowledge/engine/graphrag.py              — GraphRAG query builder
□ GraphRAG: LLM → consulta AssetStore + LineageStore + MemoryStore → contexto enriquecido
□ Tests: GraphRAG con datos mock
```

---

## 8. Garantías

| Invariante | Protección |
|---|---|
| 175 tests existentes pasan | ✅ Capa 11 no modifica ningún archivo existente del núcleo |
| Determinismo no se altera | ✅ `KnowledgeAsset` es frozen. El hash de determinismo sigue en `kg_active_version` |
| API pública no cambia | ✅ Solo se añaden endpoints, no se modifican los existentes |
| Reader no escribe | ✅ Los Stores son módulos nuevos, no tocan reader.py |
| sqlite3.connect() solo en connection.py | ✅ Los Stores usan `open_db()` existente |
| Sin dependencias circulares | ✅ `ontology/` importa solo `models.py`. Extractors importan `ontology/` y `eventbus.py` |
| Compatibilidad Python 3.10-3.13 | ✅ Mismo approach que el núcleo |
