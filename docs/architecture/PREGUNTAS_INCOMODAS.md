# Análisis Crítico — Knowledge Engine (Preguntas Incómodas)

> **Fecha:** 2026-07-03  
> **Versión:** 0.2.0  
> **Propósito:** Reflexión arquitectónica profunda antes de Fase 6

---

## 1. ¿Qué responsabilidad debería tener este sistema y no tiene todavía?

**Un lenguaje de consulta estructurado.** El Knowledge Engine se llama "motor
de conocimiento" pero su interfaz de búsqueda es `LIKE '%query%'` sobre título
y metadatos básicos. No hay forma de expresar:

- "Dame todos los PDFs de 2026 cuyo autor contenga 'García'"
- "Encuentra assets que REFERENCES un documento concreto"
- "¿Qué imágenes están incrustadas en qué documentos?"
- "Muéstrame la línea temporal de cambios de este asset"

Un knowledge engine sin un query language es una base de datos con metadatos.
Necesita al menos un filtro estructurado por campos (author, date, asset_type,
extractor) combinable con búsqueda de texto completo.

**Rastreo de referencias entre documentos.** El sistema extrae metadatos de
documentos individuales pero no detecta relaciones entre ellos (citas,
referencias cruzadas, assets embebidos). `AssetRelationship` existe como modelo
pero ningún extractor lo puebla.

**Garbage collection de assets huérfanos.** Cuando se elimina un archivo fuente,
el KnowledgeAsset correspondiente vive para siempre en la base de datos. No hay
mecanismo de detección ni limpieza.

---

## 2. ¿Qué echaría de menos un desarrollador que se incorpore dentro de un año?

**Una guía de incorporación para humanos.** `AGENTS.md` está optimizado para
agentes de IA. Un desarrollador humano echaría de menos:
- `CONTRIBUTING.md` con flujo de trabajo, prerequisites, cómo ejecutar tests
- `docs/tutorial.md` con un ejemplo "de principio a fin" (crear un archivo →
  compilar → extraer metadatos → buscar)
- `Makefile` o `justfile` con comandos comunes (test, lint, build-docs, etc.)

**Un suite de benchmarks.** Los tiempos de extracción solo existen como notas
sueltas en closeout reports. No hay `tests/benchmarks/` que un desarrollador
pueda ejecutar para detectar regresiones de rendimiento.

**Historial de migraciones de esquema.** Schema v12 existe pero no hay
`schemas/migrations/v01_to_v02.sql`, ningún rastro de cómo evolucionó.

**Pruebas de integración reales.** Los tests usan mocks extensivamente.
No hay forma de verificar que el sistema funciona con Ollama real, Qdrant real,
ffmpeg real, tesseract real. Un desarrollador nuevo no sabe si "funciona de
verdad" o solo "pasa los tests".

---

## 3. ¿Qué parte del diseño parece incompleta aunque no genere errores?

**`KnowledgeAsset.wraps_document()`** (`internal.py:127-130`). Es un método
que hace literalmente `pass`. Existe porque el diseño dice que KnowledgeAsset
"envuelve a Document" pero el mecanismo de wrapping nunca se implementó.
Código muerto, no llamado por nada, no testeado.

**`AssetSource.fetched_at`**. El campo existe en el modelo pero ningún
extractor lo puebla. Siempre es `""`.

**`cost` en `Extractor(Protocol)`**. Todos los extractores declaran `cost:
"O(1)" | "O(n)" | "O(n²)"`. Este atributo **nunca se lee** en ningún lado.
No hay scheduler, load balancer, o cola de prioridad que lo use.

**`AssetType.UNKNOWN`**. Existe como enumeración pero ningún extractor lo
produce. Es un placeholder sin consumidores.

**`format` ausente en PDF y Web**. Documentado en F02 de la auditoría global,
pero nunca corregido. PDF no escribe `format: "pdf"`, Web no escribe
`format: "html"`. Los demás extractores sí. Inconsistencia silenciosa.

---

## 4. ¿Qué asunción estamos haciendo que podría ser falsa?

**"SQLite es suficiente para la implementación de referencia"**. Es cierto
hoy con ~100 assets de prueba. Será falso en algún punto entre 100K y 1M de
assets. `LIKE '%query%'` sobre una tabla con 1M filas es insostenible.
`json_extract()` para filtrar por metadatos no usa índices. La deuda técnica
de Fase 7 (FTS5, lineage_edges) es crítica, no opcional.

**"El núcleo nunca necesitará modificarse"**. El muro entre el núcleo
(compiler, scanner, parser, reader) y Capa 11 es una frontera artificial. 
¿Qué ocurre cuando:
- Un nuevo asset debería disparar una recompilación?
- El scanner necesita producir KnowledgeAssets directamente?
- El compilador necesita leer assets para resolver referencias?
El EventBus es unidireccional (core → Capa 11). No hay camino de vuelta.

**"Los extractores pueden ejecutarse secuencialmente sin bloquear"**. Con
whisper (minutos por archivo), OCR (segundos por página), git clone (segundos
por repo), la ejecución secuencial en `MetadataExtractionService.extract()`
es un cuello de botella garantizado en cuanto haya más de unos pocos archivos.

**"El LLM es solo consumidor, nunca productor"**. GraphRAG envía contexto a
LLMs para responder preguntas, pero si el LLM produce una respuesta valiosa
(análisis, resumen, clasificación), no hay forma de almacenarla como
KnowledgeAsset. En un sistema que evolucione, el LLM debería poder
*producir* nuevos assets.

**"Schema v12 es congelado"**. Cada nueva fase añade requisitos. Vectores
(Fase 6) requiere almacenarlos. Lineage optimizado (Fase 7) requiere
`op_lineage_edges`. En algún momento el schema v12 se rompe.

---

## 5. ¿Qué funcionalidad esperaría encontrar por coherencia y no existe?

**Endpoint REST `/assets/search`**. Existe `/metadata/retrieve` y
`/metadata/lineage` pero no un endpoint simple que busque assets por
cualquier campo. "Buscar todos los PDFs sobre machine learning" no es
posible vía REST.

**Eliminación de assets**. `AssetStore.delete_asset()` existe pero no hay
endpoint REST ni CLI para eliminar un asset.

**Exportación/importación masiva**. No hay forma de exportar toda la base
de conocimiento a un formato portable e importarla en otra instancia.
El git bundle existe para las fuentes Markdown, no para los assets.

**Validación de integridad**. No hay comando `doctor` o `validate` que
verifique: ¿todos los assets tienen su archivo fuente? ¿Todas las
relaciones apuntan a assets existentes? ¿Todos los extractores están
registrados?

**Batch operations**. No hay forma de re-extraer todos los assets de un
tipo, o re-indexar todo tras un cambio de schema.

---

## 6. Si este proyecto fuera a soportar 100 millones de documentos, ¿qué decisión de hoy lamentaríamos?

**Metadatos como JSON blob en SQLite** (`op_assets.metadata`). Es la
decisión más impactante. Hace imposible:
- Indexar campos individuales de metadatos
- Consultar eficientemente por autor, fecha, extractor, etc.
- Migrar el schema de metadatos incrementalmente
- Usar `CHECK` constraints para validar metadatos en la DB

Con 100M filas, cualquier consulta que filtre por un campo dentro del
JSON requeriría scans completos. El `json_extract()` no usa índices
nativos. Sería catastrófico.

**`LIKE '%query%'` como mecanismo de búsqueda**. Ya está documentado como
riesgo. Con 100M assets, una búsqueda de texto LIKE tardaría minutos.
Aunque FTS5 está planificado para Fase 7, las búsquedas sobre metadatos
(author, title) seguirían usando LIKE.

**Assets globales sin particionamiento**. Todo en `op_assets`. Sin
sharding, sin particionamiento por tipo, fecha, o tenant. `COUNT(*)`
sería una operación pesada. Las migraciones de tabla requerirían
copiar 100M filas.

**Single-node architecture**. El engine entero asume un solo proceso,
una sola máquina. Qdrant y Ollama son externos, pero el engine no escala
horizontalmente. Para 100M documentos, se necesitaría al menos:
- Workers de extracción paralelos
- Réplicas de AssetStore
- Cache distribuida

---

## 7. ¿Qué pieza parece provisional aunque no esté marcada como tal?

**`ExtractorRegistry` como singleton global**. `_REGISTRY` es una variable
de módulo, `get_registry()` lo retorna. Funciona para un solo proceso,
pero en escenarios multi-thread o multi-process habría que repensarlo.
No hay tests de concurrencia sobre el registro.

**`_hash_stream()` en `base.py`**. Es una utilidad de hashing streams que
vive en `base.py` por proximidad a los extractores, no por organización.
Debería estar en `knowledge/engine/utils.py` o similar. Su ubicación es
conveniente, no arquitectónica.

**El atributo `cost` en `Extractor(Protocol)`**. Declarado, documentado,
implementado por los 8 extractores... y nunca usado. Es infraestructura
preparada para un scheduler que aún no existe. Es provisional con
aspiraciones de futuro.

**`AssetType.UNKNOWN` y `AssetType.ARCHIVE`**. Existen en el enum pero
ningún extractor los produce ni ningún consumidor los espera. Son espacio
reservado.

---

## 8. ¿Qué contrato o interfaz parece demasiado débil o demasiado fuerte?

**DEMASIADO DÉBIL — `Extractor.extract()`**: El contrato no especifica:
- ¿Es segura la llamada concurrente sobre la misma instancia?
- ¿Hay límite de tiempo? (no hay mecanismo de cancelación en el Protocol)
- ¿Qué campos del `KnowledgeAsset` devuelto son guaranteed vs optional?
- ¿Puede el extractor tener estado mutable? (algunos usan singleton patterns)

**DEMASIADO DÉBIL — Errores como strings**: `ExtractionResult.errors:
list[str]`. Sin códigos de error, sin estructura. El único consumidor
(ExtractionService) itera sobre ellos y loggea. Si en el futuro alguien
quiere manejar "file not found" diferente de "SSRF blocked", tendrá que
parsear strings.

**DEMASIADO FUERTE — `KnowledgeAsset` como frozen dataclass**: La
inmutabilidad es buena para determinismo, pero el método `wraps_document()`
que hace `pass` (literalmente no implementado) muestra que a veces
necesitamos mutación post-creación y la restricción es incómoda.

**DEMASIADO FUERTE — Extractor como Protocol concreto**: `Extractor` es
un `Protocol` structural, no una clase base. Esto es bueno para
flexibilidad, pero el Protocol exige `id`, `version`, `supported_mime_types`,
`cost`, y `extract()`. Cualquier clase con esos atributos y método es
un Extractor. No hay validación en tiempo de importación de que el
extractor realmente funciona.

---

## 9. ¿Qué decisión dificulta más la evolución futura?

**La regla de "nunca modificar el núcleo" como absoluto moral.** La
intención es buena (proteger la estabilidad). Pero crea un tabú que
impide:
- Añadir hooks en el scanner para que produzca KnowledgeAssets
- Permitir que el compilador lea assets para resolver referencias
- Hacer que el orquestador dispare re-extracción cuando un archivo cambia
- Integrar la extracción en el pipeline de compilación

El EventBus es unidireccional. Los eventos van del núcleo a Capa 11.
No hay mecanismo para que Capa 11 influencie al núcleo. Esto es una
decisión consciente, pero limitará la evolución.

**Los metadatos como JSON blob.** Ya analizado en #6. Es la deuda
técnica más cara que estamos acumulando.

**No tener migraciones de esquema automatizadas.** `init_db()` crea
tablas desde cero. Cuando el schema cambie (v12 → v13), no hay
mecanismo para migrar datos existentes. La primera migración real
será traumática.

---

## 10. ¿Qué no hemos implementado porque nadie se acordó de preguntarlo?

**Congelar/descongelar assets.** Poder marcar un asset como "no
re-extraer" (congelado). Actualmente, la extracción siempre es
idempotente y siempre sobrescribe. Si un asset fue curado manualmente,
la próxima extracción lo sobrescribe.

**Puntuación de confianza por campo.** Más allá de `quality` (global),
no hay confianza individual por metadata. El título extraído por OCR
tiene menos confianza que el título de metadatos PDF. Esto no se
refleja. Sería útil para consumidores del grafo.

**Notificaciones de fallo de extracción.** Si un extractor falla, se
loggea y se devuelve `ExtractionResult(errors=...)`. Pero no hay forma
de que un operador reciba una alerta. No hay webhook, no hay cola de
errores, no hay panel de "extracciones fallidas".

**Proveniencia por campo.** `_extractor` dice qué extractor produjo el
asset, pero no qué subsistema produjo cada campo individual. "El título
vino de metadatos PDF, el text_preview vino de PyMuPDF, el OCR vino de
tesseract." Esto sería valioso para depuración y confianza.

**Asset dependency graph explícito.** Si el asset A referencia al asset
B (ej: una presentación que incluye un PDF), no hay forma de expresar
esta dependencia. `AssetRelationship` existe pero nadie lo usa.

**Test de no-regresión visual.** Si el extractor de PDF cambia su salida
para un PDF conocido, ¿cómo detectamos que los metadatos cambiaron?
No hay tests de snapshot/regresión sobre la salida de extractores.

---

## Resumen de Hallazgos

| # | Tipo | Impacto | ¿Acción? |
|---|------|---------|----------|
| 1 | Ausencia | Alto | Necesitamos un query language mínimo para assets |
| 2 | Ausencia | Alto | No hay `CONTRIBUTING.md` para humanos |
| 3 | Incompleto | Bajo | `wraps_document()` es dead code |
| 4 | Asunción falsa | 🔴 Crítico | JSON metadata en SQLite no escala |
| 5 | Ausencia | Medio | No hay endpoint REST de búsqueda de assets |
| 6 | Error futuro | 🔴 Crítico | Sin particionamiento, 100M assets colapsan SQLite |
| 7 | Provisional | Bajo | `cost` se declara pero no se usa |
| 8 | Contrato débil | Medio | Errores como strings sin estructura |
| 9 | Barrera evolutiva | Alto | La regla "no tocar el núcleo" es demasiado rígida |
| 10 | Olvido | Medio | No hay congelación de assets, ni notificaciones de fallo |

---

*Análisis crítico post-Fase 5 — Knowledge Engine v0.2.0 — 2026-07-03*

> Este documento no bloquea ninguna fase. Identifica riesgos y deuda para
> decisiones informadas. Algunos hallazgos (como el JSON metadata) deberían
> tener un plan de mitigación antes de escalar.
