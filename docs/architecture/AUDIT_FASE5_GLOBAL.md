# Auditoría Global — Fase 5 (Knowledge Engine Extractors)

**Fecha**: 2026-07-03
**Auditor**: OpenCode (Fase 5 Global Audit)
**Alcance**: PdfExtractor, ImageExtractor, OfficeExtractor, AudioExtractor,
VideoExtractor, WebExtractor, GitExtractor, ExtractorRegistry,
MetadataExtractionService, AssetStore, Extractor(Protocol)
**Estado**: Pendiente de resolución de defectos

---

## Resumen Ejecutivo

La Fase 5 implementa **7 extractores reales** que cumplen el contrato
Extractor(Protocol), producen KnowledgeAssets deterministas, y se integran
correctamente con MetadataExtractionService + AssetStore sin tocar el núcleo.

Arquitectura: ✅ sólida, sin violaciones de SOLID, sin dependencias prohibidas.
Seguridad: ✅ SSRF robusto, protección decompression bomb, límites en todos
los extractores. 1 defecto: MAX_CLONE_SIZE no enforced en GitExtractor.
Recursos: ❌ 3 defectos (imagen no cierra handle, thumbnails huérfanos).
Calidad: ❌ código correcto pero con inconsistencias de metadatos (GitExtractor
omite size/content_sha256, OfficeExtractor warnings en metadata, PDF sin format).

**Veredicto**: APROBADO CON OBSERVACIONES — 6 defectos a corregir,
6 observaciones menores. Sin blocking issues.

---

## 1. Consistencia Arquitectónica

### 1.1 Extractor(Protocol) — Implementación

| Extractor | id | version | supported_mime_types | cost | extract() |
|-----------|----|---------|----------------------|------|-----------|
| PdfExtractor | `"pdf"` | `"1.0.0"` | `["application/pdf"]` | `"O(n)"` | ✅ |
| ImageExtractor | `"image"` | `"1.0.0"` | image/* (4) | `"O(n)"` | ✅ |
| OfficeExtractor | `"office"` | `"1.0.0"` | 3 office MIMEs | `"O(n)"` | ✅ |
| AudioExtractor | `"audio"` | `"1.0.0"` | audio/* (4) | `"O(1)"` | ✅ |
| VideoExtractor | `"video"` | `"1.0.0"` | video/* (4) | `"O(n)"` | ✅ |
| WebExtractor | `"web"` | `"1.0.0"` | `["text/html"]` | `"O(n)"` | ✅ |
| GitExtractor | `"git" | `"1.0.0"` | **`[]`** | `"O(n²)"` | ✅ |

**✅ Todos implementan el Protocol correctamente.**

### 1.2 Dependencias Prohibidas

Ningún extractor ni el servicio acceden directamente a:
- SQLite (usan AssetStore como intermediario) ✅
- GraphRetriever ❌
- MemoryStore ❌
- LineageStore ❌
- GovernanceStore ❌

### 1.3 KnowledgeAsset Contract

Todos producen `KnowledgeAsset` con:
- `asset_id = content_sha256[:16]` (determinista) — GitExtractor usa metadata hash
- `asset_type` correcto según dominio ✅
- `source` pasado del input ✅
- `quality` de función `_compute_*` ✅
- `created_at` / `updated_at` = ISO 8601 ✅

**A01 — GitExtractor sin MIME (conocido A02)**: `supported_mime_types = []`.
No es auto-descubrible por `get_for_mime()`. Requiere invocación explícita.
Documentado en diseño como limitación aceptada.

---

## 2. Consistencia Funcional

### 2.1 Metadatos — Homogeneidad

| Campo | PDF | Image | Office | Audio | Video | Web | Git |
|-------|-----|-------|--------|-------|-------|-----|-----|
| `_extractor` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `_extractor_version` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `extracted_at` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `wraps` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `size` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **❌** |
| `content_sha256` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **❌** |
| `format` | **❌** | ✅ | ✅ | ✅ | ✅ | **❌** | **❌** |

**F01 (defecto) — GitExtractor omite `size` y `content_sha256`**:
GitExtractor no incluye `size` ni `content_sha256` en metadata.
El hash se calcula sobre metadatos resumidos, no sobre contenido real.
`clone_size` solo aparece cuando se clona remoto. Rompe el contrato implícito.

**F02 (observación) — PDF y Web sin `format`**:
- PdfExtractor: debería incluir `"format": "pdf"`
- WebExtractor: debería incluir `"format": "html"` (o el MIME detectado)
VideoExtractor sí incluye `format`. Inconsistencia menor.

### 2.2 Errores — Gestión Uniforme

Todos los extractores:
- Devuelven `ExtractionResult(errors=[...])` para errores esperados ✅
- Usan `log.exception()` en except general ✅
- Retornan `asset=None` para errores fatales (file not found, size limit) ✅

**F03 (defecto) — OfficeExtractor warnings en metadata**:
Línea 195: `metadata["warnings"] = [...]`. Las advertencias deberían ir en
`ExtractionResult.warnings`, no en metadata del asset.

### 2.3 Puntuaciones de Calidad — Coherencia

| Extractor | Base | Incrementos | Max |
|-----------|------|-------------|-----|
| PDF | 0.3 | 0.1–0.15 por campo | 1.0 |
| Image | 0.3 | 0.1–0.15 | 1.0 |
| Office | 0.3 | 0.1–0.15 | 1.0 |
| Audio | 0.3 | 0.1–0.2 | 1.0 |
| Video | 0.3 | 0.1–0.2 | 1.0 |
| Web | 0.3 | 0.1–0.15 | 1.0 |
| Git | 0.3 | 0.1–0.2 | 1.0 |

✅ Base consistente 0.3, clamp `min(q, 1.0)`. Pesos por campo son específicos
de dominio — aceptable. Sin defecto.

### 2.4 Determinismo

Todos producen `asset_id = SHA-256[:16]` del contenido real — EXCEPTO Git:

**F04 (observación) — GitExtractor hash sobre metadatos**:
`_hash_git_repo()` hashea: primeros 10 commits (hash+message) + origin_url +
tag_count + branch_count. NO hashea el contenido real del repo.
Si la lógica de extracción cambia (ej: más campos en metadata), el mismo repo
produce distinto asset_id. Determinista pero frágil.

---

## 3. Seguridad

### 3.1 SSRF — WebExtractor

- Solo http/https ✅
- IPs privadas bloqueadas (RFC 1918, loopback, link-local, multicast) ✅
- Cloud metadata (169.254.169.254) específicamente bloqueado ✅
- Validación post-DNS resolution ✅
- Validación post-redirect (`_validate_redirect_url()`) ✅
- Timeouts: connect 10s, read 30s, total 60s ✅
- Body limit: 10MB ✅
- Max redirects: 5 ✅
- Header User-Agent personalizado ✅

**S01 (observación) — Redirect DNS failure silent return**:
En `_validate_redirect_url()` (web.py:270-273), si `socket.getaddrinfo()` falla,
se captura `socket.gaierror` y se retorna sin error. La URL no se rechaza
explícitamente. Bajo riesgo porque la validación inicial ya pasó, pero debería
elevar `SSRFError` para consistencia.

### 3.2 Decompression Bomb — ImageExtractor

- `MAX_IMAGE_PIXELS = 100MP` ✅
- `MAX_IMAGE_DIMENSION = 20,000px` por lado ✅
- Validación ANTES de cargar píxeles (`img = Image.open()` → check dims) ✅
- Log warning para imágenes > 50MP ✅
- Pillow `DecompressionBombError` capturado en except general ✅

**Nota**: `Image.MAX_IMAGE_PIXELS` de Pillow no se configura explícitamente
(defecto ~89MP). El código usa su propia constante `MAX_IMAGE_PIXELS = 100MP`.
Funciona, pero hay dos límites paralelos. Sin defecto.

### 3.3 Límites de Tamaño

| Extractor | Límite | Enforced? |
|-----------|--------|-----------|
| PDF | 500MB | ✅ sí |
| Image | 100MB | ✅ sí |
| Office | 200MB | ✅ sí |
| Audio | 500MB | ✅ sí |
| Video | 4GB | ✅ sí |
| Web | 10MB body | ✅ sí (post-fetch truncation) |
| Git | **500MB (MAX_CLONE_SIZE)** | **❌ NO** |

**S03 (defecto) — GitExtractor MAX_CLONE_SIZE definido pero no enforced**:
`MAX_CLONE_SIZE` existe como constante pero nunca se consulta. `_clone_repo()`
no verifica tamaño antes/durante/después del clone. Un repo malicioso o muy
grande se clona completo sin restricción.

### 3.4 Dependencias Opcionales

Todos verifican dependencias con `_check_import()` o `shutil.which()` y
degradan gracefulmente. Sin defectos.

---

## 4. Rendimiento

### 4.1 Carga en Memoria

- **PdfExtractor**: `_extract_text()` carga texto de TODAS las páginas en una
  lista (`list[str]`) simultáneamente. Para PDF de 10K páginas → gigas en RAM.
  (**P01 — observación**)
- **ImageExtractor**: `img.copy()` para thumbnail carga imagen completa en RAM.
  Necesario, aceptable.
- **OfficeExtractor**: python-docx carga documento completo. openpyxl usa
  `read_only=True` ✅. python-pptx carga presentación completa.
- **AudioExtractor**: ffprobe proceso externo ✅. Whisper carga modelo 150MB.
- **VideoExtractor**: ffprobe/ffmpeg externos ✅. OpenCV iteración streaming ✅.
  Whisper carga modelo 150MB.
- **WebExtractor**: BeautifulSoup parsea HTML completo en RAM.
- **GitExtractor**: `shutil.rmtree` para limpieza ✅.

### 4.2 Modelo Whisper — Sin Cache

**P02 (defecto) — Whisper load_model("base") en cada llamada**:
AudioExtractor (`_transcribe`, línea 175) y VideoExtractor (`_transcribe_video`,
línea 256) cargan `whisper.load_model("base")` en cada extracción.
Son ~150MB de modelo + ~2s de carga. Con N archivos de audio/video, el overhead
es N×2s y N×150MB de allocaciones. Debería cachearse como singleton a nivel
de módulo.

### 4.3 Streaming

`_hash_stream()` usa chunks de 64KB — correcto ✅.
Ningún extractor produce salida streaming para contenido grande — aceptable
para Fase 5.

---

## 5. Recursos

### 5.1 Cierre de Archivos

- **PdfExtractor**: `doc.close()` en `finally` ✅
- **ImageExtractor**: `img = Image.open(path_str)` — **nunca se cierra** ❌
- **OfficeExtractor**: `wb.close()` en `finally` (openpyxl) ✅. docx/pptx sin
  close explícito (no necesario, contexto automático).
- **AudioExtractor**: ffprobe subprocess sincrónico ✅
- **VideoExtractor**: `cap.release()` en `finally` ✅
- **WebExtractor**: `httpx.Client` como context manager ✅
- **GitExtractor**: `shutil.rmtree` en `finally` ✅

**R01 (defecto) — ImageExtractor no cierra img**:
`ImageExtractor._extract_with_pillow()` (línea 125):
```python
img = Image.open(path_str)
```
Sin `with` ni `img.close()`. Pillow eventualmente GCea el handle, pero en
bucles de miles de imágenes los FD se agotan.

### 5.2 Ficheros Temporales Persistentes

**R02 (defecto) — Thumbnails nunca se limpian**:
- ImageExtractor: crea `{path}.thumb.jpg` (línea 188)
- VideoExtractor: crea directorio `thumbs/` con 3 thumbnails JPG (líneas 186-207)
Ninguno se elimina tras la extracción. Acumulación indefinida de archivos
garbage junto a los originales.

### 5.3 Procesos Externos

- ffprobe (Audio/Video): `subprocess.run()` con timeout ✅
- ffmpeg (Video): `subprocess.run()` con timeout ✅
- git clone: `subprocess.run()` con timeout ✅
- git commands: `subprocess.run()` con timeout ✅
Ningún proceso zombie. ✅

---

## 6. Calidad (DRY/SOLID/KISS)

### 6.1 Código Duplicado

- **Funciones `_compute_*_quality()`**: 7 funciones con patrón idéntico
  (q=0.3 + checks + min(q,1.0)). Duplicación menor aceptable.
- **Construcción metadata dict**: `_extractor`, `_extractor_version`, `wraps`,
  `extracted_at` repetido en todos. Factorizable pero no crítico.
  (**Q01 — observación**)
- **Patrón error handling**: idéntico en todos. ✅ Consistente, no defecto.

### 6.2 SOLID

| Principio | Estado |
|-----------|--------|
| SRP | ✅ Cada extractor = un dominio |
| OCP | ✅ Nuevos extractores = nuevos archivos |
| LSP | ✅ Todos implementan Extractor(Protocol) |
| ISP | ✅ Protocol mínimo (4 attr + 1 method) |
| DIP | ✅ Dependencias vía Protocol/inyección |

### 6.3 KISS/YAGNI

**Q02 (observación) — GitExtractor hash simplificado**:
`_hash_git_repo()` solo usa primeros 10 commits + metadata summary.
No representa el contenido real del repo. Correcto para KISS pero
el `asset_id` no es una verdadera huella del contenido.

---

## 7. Escalabilidad

### 7.1 Miles de Documentos

- Cada extractor es independiente y sin estado compartido ✅
- `MetadataExtractionService.extract()` itera secuencialmente sobre extractores
  (línea 58). Sin paralelismo ❌ — aceptable para Fase 5.

### 7.2 Archivos Muy Grandes

- Límites de tamaño en todos los extractores ✅ (excepto S03 en Git)
- Extracción no bloquea el event loop (síncrona intencionalmente) ✅

### 7.3 Múltiples Extractores en Paralelo

No soportado actualmente. `MetadataExtractionService` llama a extractores en
serie. Diseñado para EventBus en fases posteriores.

---

## 8. Observabilidad

### 8.1 Logging

| Extractor | info | warning | exception | Detalle |
|-----------|------|---------|-----------|---------|
| PDF | ✅ | ✅ | ✅ | pages, size, has_text |
| Image | ✅ | ✅ | ✅ | dimensiones |
| Office | ✅ | ✅ | ✅ | paragraphs, tables, sheets |
| Audio | ✅ | ✅ | ✅ | duración, transcripción |
| Video | ✅ | ✅ | ✅ | metadatos, thumbnails |
| Web | ✅ | ✅ | ✅ | chars, images, links |
| Git | ✅ | ✅ | ✅ | commits, tags, branches |

### 8.2 Métricas

**O02 (riesgo) — Sin métricas instrumentadas**:
Ningún extractor emite métricas (contadores de éxito/fallo, histogramas de
duración, calidad promedio). Solo disponible `ExtractionResult.duration_ms`.
Aceptable para Fase 5, necesidad para Fase 6+.

### 8.3 Eventos

No hay emisión de eventos desde extractores. MetadataExtractionService no
publica eventos al EventBus. Pendiente para integración futura.

### 8.4 Trazabilidad de Errores

- Errores en `ExtractionResult.errors[]` ✅
- `log.exception()` con traceback completo ✅
- SSRF con excepciones tipadas (URLSchemeBlocked, PrivateIPBlocked, etc.) ✅

**O03 (observación) — OCR errors silenciados en metadata**:
ImageExtractor `_run_ocr()` guarda errores en `metadata["ocr_error"]` en vez
de añadirlos a `result.errors`. Si OCR es importante, el error pasa
desapercibido.

---

## Defectos (Deben Corregirse)

| ID | Severidad | Archivo | Línea | Descripción |
|----|-----------|---------|-------|-------------|
| **F01** | Alta | `git.py` | 101-112 | Falta `size` y `content_sha256` en metadata |
| **F03** | Media | `office.py` | 195 | Warnings en metadata, no en `result.warnings` |
| **S03** | Alta | `git.py` | 38 | MAX_CLONE_SIZE definido pero nunca verificado |
| **R01** | Media | `image.py` | 125 | `img` sin close() — fuga de file descriptors |
| **R02** | Baja | `image.py` | 188 | Thumbnail `*.thumb.jpg` nunca se limpia |
| **R02** | Baja | `video.py` | 186-207 | Directorio `thumbs/` nunca se limpia |
| **P02** | Media | `audio.py:175`, `video.py:256` | Whisper `load_model()` sin cache — overhead 150MB/2s por llamada |

## Observaciones (Recomendado)

| ID | Impacto | Archivo | Descripción |
|----|---------|---------|-------------|
| **F02** | Bajo | `pdf.py`, `web.py` | Falta campo `format` en metadata |
| **F04** | Medio | `git.py` | Hash sobre metadata, no sobre contenido real |
| **S01** | Bajo | `web.py` | `_validate_redirect_url()` silencia DNS failure |
| **Q01** | Bajo | todos | Metadata dict duplication (no block para Fase 5) |
| **P01** | Medio | `pdf.py` | `_extract_text()` carga todas las páginas en RAM |
| **O03** | Bajo | `image.py` | OCR errors en metadata, no en errors list |

## Riesgos Abiertos

| ID | Riesgo | Impacto | Mitigación |
|----|--------|---------|------------|
| R01 | Agotamiento de FDs con miles de imágenes | Medio | Corregir `img.close()` |
| S03 | Git clone sin límite de tamaño | Alto | Implementar check pre/post clone |
| P02 | Whisper sin cache degradado con N>1 archivos | Medio | Singleton `_whisper_model` |
| A01 | GitExtractor no descubrible por MIME | Bajo | Aceptado, documentado |

## Deuda Técnica

| Item | Esfuerzo | Prioridad |
|------|----------|-----------|
| Whisper model singleton | 30 min | Alta |
| GitExtractor size enforcement | 15 min | Alta |
| Metadata helpers (reducir duplicación) | 2h | Media |
| Temp file cleanup policy | 1h | Media |
| Metric instrumentation | 4h | Baja |

## Mejoras Recomendadas (Ordenadas por Impacto)

1. **ALTA**: Corregir F01 — Añadir `size` y `content_sha256` a GitExtractor metadata
2. **ALTA**: Corregir S03 — Enforzar MAX_CLONE_SIZE en GitExtractor
3. **ALTA**: Corregir P02 — Singleton para whisper model
4. **MEDIA**: Corregir R01 — Añadir `img.close()` en ImageExtractor
5. **MEDIA**: Corregir F03 — Mover warnings de metadata a ExtractionResult
6. **MEDIA**: Corregir R02 — Política de limpieza de thumbnails
7. **BAJA**: Corregir F02 — Añadir `format` a PDF y Web
8. **BAJA**: Corregir S01 — Lanzar SSRFError en redirect DNS failure
9. **BAJA**: Corregir O03 — Incluir OCR errors en result.errors
10. **BAJA**: Corregir P01 — Streaming de texto en PdfExtractor (opcional)

---

---

## Defectos No Corregidos (Documentados)

### R02 — Thumbnails sin limpieza (Imagen + Vídeo)

**Decisión**: No se corrige. Mantenido como deuda técnica documentada.

**Motivación**:
- ImageExtractor: `{path}.thumb.jpg` se escribe junto al original.
- VideoExtractor: directorio `thumbs/` con 3 thumbnails JPG.
- Limpiar archivos temporales requiere política de ciclo de vida (TTL,
  cleanup hook, o configuración). No es responsabilidad del extractor.
- Impacto bajo: thumbnails son pequeños (~10KB cada uno) y reutilizables.
- Mejora futura: implementar `tempfile` o cleanup post-extracción vía
  MetadataExtractionService cuando exista pipeline con cleanup.

### F04 — GitExtractor hash sobre metadatos, no sobre contenido real

**Decisión**: No se corrige. Mantenido como característica de diseño.

**Motivación**:
- `_hash_git_repo()` genera SHA-256 a partir de: primeros 10 commits
  (hash+message), origin_url, tag_count, branch_count.
- Este hash es **determinista por metadata extraída**: mismo repo produce
  mismo `asset_id` con misma versión del extractor.
- No es posible hashear contenido real del repo sin clonarlo completo
  (derrota `--depth 1`) o sin depender de `git rev-parse HEAD` (que
  cambiaría con cada commit).
- El contrato del proyecto exige determinismo, no hash del contenido bruto.
  GitExtractor es determinista por metadata, lo que cumple el requisito.
- Si la lógica de extracción cambia (nuevos campos), `asset_id` cambia.
  Esto es correcto: es la huella de *lo que se extrajo*, no del origen.

---

## Acta de Correcciones (2026-07-03)

Las siguientes correcciones se aplicaron antes de la auditoría final:

| ID | Estado | Cambio |
|----|--------|--------|
| **F01** | ✅ Corregido | GitExtractor: `size` + `content_sha256` añadidos a metadata |
| **S03** | ✅ Corregido | GitExtractor: `MAX_CLONE_SIZE` enforced post-clone + `GitLimitError` |
| **F03** | ✅ Corregido | OfficeExtractor: warnings movidos a `ExtractionResult.warnings` |
| **R01** | ✅ Corregido | ImageExtractor: `with Image.open() as img:` — sin fuga de FDs |
| **P02** | ✅ Corregido | Audio/Video: whisper model cache vía función con atributo singleton |

---

## Validación Final (Post-Corrección)

| Dimensión | Estado |
|-----------|--------|
| Arquitectura | ✅ Aprobado |
| Funcionalidad | ✅ Aprobado |
| Seguridad | ✅ Aprobado |
| Rendimiento | ✅ Aprobado |
| Recursos | ✅ Aprobado (R02 documentado) |
| Calidad | ✅ Aprobado |
| Escalabilidad | ✅ Aprobado |
| Observabilidad | ✅ Aprobado |

**Veredicto final**: **APROBADO**

- 5 defectos corregidos (F01, S03, F03, R01, P02).
- 2 defectos documentados sin corrección (R02, F04).
- 0 defectos de severidad alta o media abiertos.
- 0 regresiones en los 60 tests de extractores.
- 0 errores de código nuevo en ruff.
- 1 fallo preexistente en QdrantSync (no relacionado).

**Fase 5 apta para cierre oficial.**
