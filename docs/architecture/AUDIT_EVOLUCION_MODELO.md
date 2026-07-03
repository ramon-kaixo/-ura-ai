# Auditoría Arquitectónica — Evolución del Modelo (Schema v13 + ADR-007)

> **Fecha:** 2026-07-03
> **Versión del proyecto:** 0.2.0
> **Alcance:** Exclusivamente evolución del modelo de datos y política del núcleo
> **NO cubre:** Bugs, código, tests, rendimiento

---

## 1. ¿Pertenecen `content_sha256` y `wraps` al dominio?

### Diagnóstico

**`content_sha256` — SÍ pertenece al dominio.**

`content_sha256` no es un metadato descriptivo del activo (como `title`,
`author` o `format`). Es un **identificador de integridad estructural**:

- Determina la identidad del contenido fuente (primeros 16 hex de SHA-256
  son el `asset_id`)
- Se usa para **deduplicación**: dos assets con el mismo `content_sha256`
  representan el mismo contenido
- Es parte del contrato de determinismo: mismo contenido → mismo hash →
  mismo asset_id
- Es referenciado desde el grafo: `kg_nodes.content_sha256` ya es columna;
  era incoherente que en `op_assets` estuviera enterrado en JSON

**`wraps` — SÍ pertenece al dominio, aunque con menos urgencia.**

`wraps` expresa la relación estructural "este KnowledgeAsset envuelve este
Documento fuente". Es un **vínculo ontológico** entre el modelo del núcleo
(Document) y Capa 11 (KnowledgeAsset). Es una relación, no una descripción.

### Veredicto: ✅ Correcto

Ambos campos son **estructurales**, no descriptivos. Su promoción a columna
es arquitectónicamente coherente. Permanecieron en JSON solo por omisión
en el diseño original (CAPA11_INTEGRATION.md ya los definía como columnas;
ver discrepancia documentada, sección 10 del informe de exploración).

### Contraste con campos que SÍ deben permanecer en JSON

| Campo | Naturaleza | Columna propia | Justificación |
|-------|------------|----------------|---------------|
| `title` | Descriptivo | ❌ No | Es un metadato del contenido, no del asset. Varios formatos (Dublin Core, EXIF, PDF metadata). Meterlo como columna forzaría un esquema rígido sobre datos heterogéneos. |
| `author` | Descriptivo | ❌ No | Misma razón. Sin indexar, no hay beneficio de columna. |
| `format` | Descriptivo | ❌ No | Ya existe `asset_type` como columna. `format` (pdf, docx, mp4) es redundante con el extractor que lo produjo. |
| `content_sha256` | **Estructural** | ✅ Sí | Identidad, dedup, determinismo, integridad. |
| `wraps` | **Estructural** | ✅ Sí | Relación ontológica Document → KnowledgeAsset. |

---

## 2. Criterio arquitectónico para promoción a columna

Para que un campo actualmente en `metadata` JSON pueda promocionarse a
columna física en `op_assets`, debe cumplir **al menos dos** de estos
tres criterios:

| # | Criterio | Ejemplo |
|---|----------|---------|
| A | **Consultado con WHERE/filter en SQL** sin `json_extract`. Si se filtra por este campo, debe ser columna. | `content_sha256` se consultaría para dedup: `WHERE content_sha256 = ?` |
| B | **Estructural, no descriptivo**. El campo expresa identidad, integridad, relación o jerarquía, no una propiedad del contenido. | `wraps` expresa relación; `title` es propiedad. |
| C | **Referenciado desde otra tabla o subsistema**. Si otro componente (el grafo, otro store, un servicio externo) necesita este campo, debe ser columna. | `kg_nodes.content_sha256` ya es columna en el grafo. |

### Checklist para futuras promociones

```text
¿El campo se consulta con WHERE?       → criterio A
¿Es estructural (no descriptivo)?      → criterio B
¿Es referenciado externamente?         → criterio C
Resultado: ¿cumple ≥2?                 → promocionar a columna
```

### Ejemplos de aplicación

| Campo hipotético | A (WHERE) | B (Estructural) | C (Referenciado) | ¿Columna? |
|------------------|-----------|-----------------|-------------------|-----------|
| `extracted_by` | No | Sí (traza de proceso) | No | ❌ (1/3) |
| `source_mtime` | Posible (filtrar por fecha) | Sí (trazabilidad) | No | ⚠️ (2/3, solo si hay casos de uso) |
| `language` | Sí (filtrar por idioma) | No (descriptivo) | No | ❌ (1/3) |

**Regla de oro**: Si dudas, quédate en JSON. Promocionar es fácil
(migración aditiva, como v12→v13). Des-promocionar es imposible sin
romper compatibilidad.

---

## 3. Revisión de ADR-007: ¿Barrera suficientemente alta?

### Diagnóstico

ADR-007 sustituye "nunca modificar el núcleo" (regla absoluta) por
"modificable solo con ADR y backward-compatible". El riesgo es que esta
flexibilización se convierta en una puerta abierta.

### Evaluación de la versión actual

La versión escrita en `ADR-007-REGLA_NUCLEO.md` dice:

| Aspecto | Evaluación |
|---------|------------|
| ✅ Permite añadir campos opcionales a config | Correcto — es backward-compatible |
| ✅ Permite nuevos topics de eventos | Correcto — no rompe suscriptores existentes |
| ✅ Permite hooks/callbacks | Correcto — extensión, no modificación |
| ❌ **Prohíbe refactor/renombrado** | Correcto pero insuficiente |
| ❌ **No exige plan de rollback** | Ausencia |
| ❌ **No exige migración demostrable** | Ausencia |
| ❌ **No exige revisión por segunda parte** | Ausencia |

### Endurecimientos necesarios

Para mantener la barrera alta, ADR-007 debe añadir:

**1. Justificación de necesidad**: El ADR debe demostrar que el cambio no
puede lograrse mediante un nuevo Protocol, un nuevo suscriptor de EventBus,
o un adaptador externo. Si existe alternativa sin tocar el núcleo, esa es
la respuesta correcta.

**2. Plan de migración y rollback**: Toda modificación al núcleo debe
incluir:
- Migración de datos si aplica (ej: nueva columna en schema)
- Procedimiento de rollback (ej: `ke init --restore` o script revert)
- Verificación de que el sistema funciona sin la modificación (degradación)

**3. Revisión obligatoria**: Toda modificación al núcleo debe ser revisada
por un segundo agente/humano antes de aplicarse. No puede hacerse en una
sesión autónoma.

**4. Congelación semántica**: El ADR no solo prohíbe refactor de símbolos.
También prohíbe cambiar el **comportamiento observado** de cualquier función
del núcleo, incluso si la firma no cambia.

### Propuesta de texto endurecido

```diff
- ❌ Prohibited: Refactoring/renaming existing symbols, changing method signatures, deleting functionality
+ ❌ Prohibited:
+    - Refactoring/renaming existing symbols
+    - Changing method signatures
+    - Deleting functionality
+    - Changing observable behavior (even with same signature)
+    - Any modification that lacks a rollback plan
+    - Any modification achievable via Protocol/EventBus adapter instead
```

Aplico este endurecimiento a continuación en el documento ADR-007.

---

## 4. Justificación de `op_memory` como entidad independiente

`op_memory` no es un KnowledgeAsset. Es un modelo diferente con
responsabilidades distintas:

### Diferencia ontológica

| Eje | `op_assets` (KnowledgeAsset) | `op_memory` (Memoria) |
|-----|------------------------------|----------------------|
| **Origen** | Extracción determinista de documentos fuente | Interacciones, decisiones, incidentes |
| **Fuente** | Archivo (PDF, MD, imagen, video...) | Conversación, evento, alerta, razonamiento |
| **Determinismo** | ✅ Mismo input → mismo output siempre | ❌ No determinista (depende del contexto) |
| **Ciclo de vida** | Creado por extractor, persiste hasta delete | Creado por agente, consultado, eventualmente archivado |
| **Estructura** | metadata JSON variable, source, relationships | title+content fijos, tags, related_assets |
| **Índice** | B-Tree + FTS5 (planificado) | FTS5 (content + title) |
| **Tamaño** | metadata ligera (< 1KB) | content puede ser largo (> 10KB) |
| **Caso de uso** | "¿Qué documentos hablan de X?" | "¿Qué decidimos sobre X la semana pasada?" |

### Diferencia de query pattern

- **KnowledgeAssets** se buscan por tipo, metadata, extractor, rango de
  fechas. Las queries son estructuradas (`asset_type = 'pdf'`,
  `extracted_at > ?`).
- **Memorias** se buscan por contenido semántico o título. Las queries
  son búsqueda de texto libre (`content LIKE ?` o FTS5 match).
- Mezclarlos en la misma tabla obligaría a compromisos de esquema que
  perjudicarían a ambos casos de uso.

### Coherencia con el diseño original

`memory_store.py` línea 70 documenta explícitamente:
> "Tabla: op_memory (existente en schema v13)."

La tabla ya existía en el schema completo (`knowledge_graph.sql`) pero
sin migración propia. La migración v12→v13 simplemente la asegura para
bases migradas incrementalmente. No es una nueva entidad, es la
regularización de una entidad que siempre debió existir.

### Veredicto: ✅ Correcto

`op_memory` como tabla independiente es arquitectónicamente sólida.
Los dos modelos tienen orígenes, ciclos de vida, patrones de consulta
y garantías de determinismo diferentes. Unificarlos sería un error de
diseño (violación del principio de responsabilidad única).

---

## 5. ¿Deriva hacia un modelo acoplado a SQLite?

### Riesgo real

El proyecto usa SQLite como implementación de referencia (decisión
explícita en AGENTS.md). Sin embargo, tres decisiones recientes
incrementan el acoplamiento:

**🔴 Riesgo 1: Sistema de migraciones específico de SQLite.**
`migrations.py` usa `executescript`, `PRAGMA user_version`, `BEGIN/COMMIT`
directamente en SQLite. Si el proyecto migrara a PostgreSQL:
- `PRAGMA user_version` no existe (habría que usar tabla `schema_migrations`)
- `executescript` no tiene equivalente directo
- Las migraciones SQL usan sintaxis SQLite (`ALTER TABLE ADD COLUMN` sin
  `IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, etc.)

**🟡 Riesgo 2: FTS5 es SQLite-specific.**
`kg_nodes_fts` es una `VIRTUAL TABLE USING fts5`. PostgreSQL usa
`tsvector`/`tsquery`. La migración requeriría reescribir la capa de
búsqueda de texto completo.

**🟢 Riesgo 3: Columnas JSON en SQLite.**
`op_assets.metadata TEXT` almacena JSON como texto. PostgreSQL tiene
`JSONB` que es más eficiente. Pero el modelo de datos es conceptualmente
el mismo — solo cambia el tipo de columna.

### Mitigaciones existentes

| Riesgo | Mitigación | Efectividad |
|--------|------------|-------------|
| SQLite migrations | Los stores usan `Protocol`. El migration system es SQLite pero la lógica de negocio no. | 🟡 Parcial — migrations.py tendría que reescribirse |
| FTS5 | La búsqueda FTS está encapsulada en `sqlite_writer.py`. El resto del sistema usa `search()` abstracto. | 🟢 Alta — solo un archivo tocar |
| JSON columns | El acceso a metadata es vía Python `json.loads()`. PostgreSQL requeriría `json.loads()` igual. | 🟢 Alta — transparente |

### Evaluación filosófica

> "El conocimiento es el producto principal; la IA únicamente lo consume."

Esta filosofía se mantiene intacta. La evolución v12→v13:

- **No añade dependencias de IA**: `content_sha256` y `wraps` son
  deterministas. `op_memory` almacena memorias, no inferencias.
- **No depende de SQLite para su modelo de dominio**: Los Protocols
  (AssetStore, MemoryStore, Embedder, VectorStore) desacoplan el
  dominio de la implementación.
- **Qdrant para vectores es externo**: No hay vectors en SQLite.
  La Fase 6 refuerza la separación: vectores fuera, metadatos dentro.

### Riesgo de deriva: evaluación global

| Factor | ¿Deriva? | Notas |
|--------|----------|-------|
| Schema SQLite-specific | ⚠️ Leve | `PRAGMA`, `executescript`, FTS5 son SQLite. Pero el modelo conceptual es portable. |
| Dependencia de sqlite3 stdlib | ⚠️ Leve | `sqlite3` es parte de la stdlib. No es dependencia externa. PostgreSQL requeriría `asyncpg` o `psycopg`. |
| Protocol desacopladores | ✅ Fuerte | `AssetStore(Protocol)`, `MemoryStore(Protocol)`, `Embedder(Protocol)`, `VectorStore(Protocol)` |
| Qdrant externo | ✅ Fuerte | Los vectores están fuera del engine. |
| Sistema de migraciones | 🔴 Débil | `migrations.py` es puro SQLite. Sería el archivo más costoso de migrar. |

### Recomendación

Documentar en `INVARIANTS.md` (o archivo similar) que `migrations.py` y
el sistema FTS5 son las dos dependencias SQLite más profundas, y que una
hipotética migración a PostgreSQL requeriría:

1. Reescribir `migrations.py` con un backend abstracto (similar a Alembic)
2. Reemplazar FTS5 por `tsvector`/`tsquery` en `sqlite_writer.py`
3. Migrar `PRAGMA user_version` a tabla `schema_migrations`

No se requiere acción ahora. Solo documentación del riesgo para
mantenerlo visible.

---

## Veredicto Final

### Schema v13: ✅ Evolución coherente del diseño

- `content_sha256` y `wraps` como columnas es correcto (criterio
  estructural, ≥2/3 del checklist)
- `op_memory` como tabla independiente es correcto (responsabilidad
  única, patrones de consulta diferentes)
- Migración aditiva (no destructiva) — respeta compatibilidad
- El criterio de promoción a columna (sección 2) evita futuras
  promociones arbitrarias

### ADR-007: ✅ Aprobado con endurecimiento

Se ha añadido justificación de necesidad, plan de rollback, revisión
obligatoria y congelación semántica. La barrera sigue siendo alta:
modificar el núcleo requiere más justificación que crear un nuevo
Protocol.

### SQLite lock-in: ⚠️ Riesgo documentado, no bloqueante

El proyecto mantiene su filosofía de plataforma universal de conocimiento.
El acoplamiento a SQLite es real pero localizado (migrations.py, FTS5).
Los Protocols desacoplan el dominio de la implementación. El riesgo está
documentado para decisiones futuras.

---

*Auditoría arquitectónica — Evolución del modelo — 2026-07-03*
*Schema v13 + ADR-007 + op_memory + SQLite lock-in*
