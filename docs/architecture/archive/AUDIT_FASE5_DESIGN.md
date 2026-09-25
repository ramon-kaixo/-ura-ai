# Auditoría de diseño — Fase 5 (Extractores Reales)

> **Fecha:** 2026-07-02  
> **Documento auditado:** `FASE5_DESIGN.md` v0.1.0 → v0.2.0 (revisado)  
> **Tipo:** Auditoría de arquitectura (no de código)

---

## Resumen ejecutivo

**Resultado: Aprobado con observaciones**

El diseño original (v0.1.0) presentaba **2 defectos críticos** (SEC01: SSRF en WebExtractor, SEC02: decompression bomb en ImageExtractor) que han sido corregidos en la revisión v0.2.0 con políticas de seguridad documentadas (§9.1 y §9.2). Adicionalmente, **S01** (threads zombis en timeout) ha sido documentado como limitación conocida en la sección de concurrencia. Quedan pendientes **gaps de diseño** (A02, A03, D01, P01-P02, M01-M03) que pueden corregirse durante implementación.

---

## 1. Arquitectura

### Cumplimiento hexagonal
- ✅ `Extractor(Protocol)` es la frontera del dominio. Dependencias apuntan hacia adentro.
- ✅ `AssetStore(Protocol)` y `EventBus` se usan como interfaces, no como implementaciones concretas.
- ✅ Ningún extractor toca `compiler.py`, `scanner.py`, `parser.py`, `reader.py`, `orchestrator.py`.
- ⚠️ Los semáforos globales (`_EXTRACTION_SEMAPHORES`) son infraestructura mezclada en el servicio. Aceptable pragmáticamente pero rompe pureza hexagonal.

### Protocol-first
- ✅ `Extractor(Protocol)` no se modifica.
- ✅ `AssetStore(Protocol)` no se modifica.

### Defectos de arquitectura

| ID | Severidad | Defecto | Evidencia |
|---|---|---|---|
| **A01** | 🔴 Alto | `MetadataExtracted` no existe en `eventbus.py` | El diseño publica `EventBus.publish(MetadataExtracted)` (línea 37, 293). En `eventbus.py` solo existen `CompileCompleted`, `MemoryCreated`, `MemoryUpdated`, `MemoryLinked`, `ArchiveCompleted`, `SearchPerformed`. `MetadataExtracted` no está definido. CAPA11_INTEGRATION.md §6 usa `MetadataChanged`. **Inconsistencia**: el diseño usa un nombre, la planificación usa otro, el eventbus real no tiene ninguno. |
| **A02** | 🟡 Medio | GitExtractor sin MIME type → auto-descubrimiento roto | `supported_mime_types` es `[]` (sección 10.7, MIME: "N/A"). `ExtractorRegistry.get_for_mime()` retorna vacío. `ExtractionService._guess_mime()` solo asigna por extensión. GitExtractor **nunca será invocado automáticamente**. Debe existir un mecanismo explícito (trigger por directorio, URL scheme, o evento). |
| **A03** | 🟡 Medio | WebExtractor sin Content-Type header detection | `_guess_mime()` asigna por extensión de archivo. Una URL como `https://example.com/page` no tiene extensión → `application/octet-stream`. WebExtractor solo soporta `text/html`. **Nunca matcheará**. `_guess_mime()` necesita detectar MIME por cabecera HTTP `Content-Type`. |

---

## 2. Contratos (Extractor Protocol)

### Consistencia entre extractores

Todos los extractores definen:
```python
id: str
version: str
supported_mime_types: list[str]
cost: str
def extract(source: AssetSource) -> ExtractionResult
```
✅ Compatibles con el Protocol. No se requiere modificación.

### Defectos de contrato

| ID | Severidad | Defecto | Evidencia |
|---|---|---|---|
| **C01** | 🟡 Medio | `GitExtractor.supported_mime_types = []` es válido pero inútil | El Protocol permite `[]`. Pero el contrato implícito del Registry es que `supported_mime_types` refleje qué fuentes sabe procesar. Un extractor que nunca matchea por MIME es invisible para el pipeline automático. El diseño no define cómo se invoca GitExtractor. |
| **C02** | 🟢 Bajo | OfficeExtractor devuelve 3 AssetTypes distintos para 1 extractor | OfficeExtractor produce `OFFICE_DOC`, `OFFICE_SHEET`, u `OFFICE_SLIDE` según la extensión. Esto es correcto pero el diseño no especifica cuándo se decide el tipo: ¿en `__init__` del extractor, en el `extract()`, o en `ExtractionService` después de la extracción? |
| **C03** | 🟢 Bajo | PdfExtractor marcado como `cost = O(n)` — correcto para PDF textual. Para PDF escaneado + OCR → O(n²). | El diseño no contempla que el coste cambie si se activan pasos opcionales. Sugerencia: declarar siempre el peor caso (`O(n²)`) o no declarar coste variable. |

---

## 3. Dependencias

### Resumen por extractor

| Extractor | Dependencias necesarias | Dependencias opcionales | Degradación | Impacto startup |
|---|---|---|---|---|
| PDF | PyMuPDF (fitz) | pytesseract + tesseract-ocr | ✅ `_check_import("fitz")` en __init__ | Sin fitz → `_has_fitz=False`. Llamar `extract()` devuelve error |
| Image | Pillow | pytesseract + tesseract-ocr | ✅ `_check_import("PIL")` en __init__ | Sin Pillow → `_has_pillow=False`. Error |
| Video | Ninguna | ffprobe, ffmpeg, opencv-python, whisper | ✅ Todas opcionales | 0 impacto |
| Audio | Ninguna | ffprobe, whisper | ✅ Todas opcionales | 0 impacto |
| Office | python-docx, openpyxl, pptx | Ninguna | ✅ `_check_import()` por subtipo | 0 impacto (import en __init__) |
| Web | httpx, beautifulsoup4 | Ninguna | ✅ `_check_import()` | 0 impacto |
| Git | git CLI | Ninguna | ✅ `shutil.which("git")` | 0 impacto |

### Defectos de dependencias

| ID | Severidad | Defecto | Evidencia |
|---|---|---|---|
| **D01** | 🔴 Alto | PyMuPDF, Pillow, python-docx, openpyxl, pptx marcados "obligatorios" → contradicen principio de degradación graceful | Tabla sección 8: "✅ Sí" para estas librerías. Principio §1: "Toda dependencia externa es opcional". Si son obligatorias, falla la extracción. Si son opcionales, el extractor debe producir un asset mínimo. **El diseño no especifica qué metadatos contiene un asset mínimo sin librerías.** |
| **D02** | 🟡 Medio | Sin dependencia obligatoria → el extractor devuelve metadatos vacíos, pero el asset se crea | Si Pillow no está instalado, ImageExtractor aún puede extraer filename, size, y hashear el contenido → un `KnowledgeAsset` con `metadata={}`. El diseño debería definir explícitamente los metadatos mínimos que **siempre** están disponibles (size, content_sha256, title=filename). |
| **D03** | 🟢 Bajo | python-docx/openpyxl/pptx instalación parcial no contemplada | Si solo python-docx está instalado, DOCX funciona y XLSX/PPTX fallan. El diseño no dice si OfficeExtractor se registra con todos los MIME types (y falla para los que no tiene librería) o solo los que tiene. |

---

## 4. Rendimiento

| ID | Severidad | Defecto | Evidencia |
|---|---|---|---|
| **P01** | 🔴 Alto | Imagen 100MB → RAM >2GB sin protección | `Pillow.Image.open()` es lazy, pero `thumbnail()` decodifica completamente. Un PNG de 100MB puede tener dimensiones 200MPx → >2GB en RAM al decodificar. La mitigación "Carga con `Image.open()` sin `load()` + `Image.thumbnail()`" **no evita la descompresión**. `thumbnail()` llama a `load()` internamente. |
| **P02** | 🟡 Medio | PDF de 100M páginas → OOM | PyMuPDF itera páginas con `fitz.open()` → `page = doc[n]`. Cada página individual se carga, pero metadata maliciosa puede reportar 100M páginas. El bucle iteraría sin límite. |
| **P03** | 🟡 Medio | `_hash_stream()` duplicado en cada extractor | La función de streaming hash (sección 5, ~10 líneas) se replicaría en los 7 extractores. **DRY**. Debería ser un helper compartido. |
| **P04** | 🟢 Bajo | OfficeExtractor 200MB → XML expandido en RAM | Office files son ZIP. Un DOCX de 200MB contiene XML comprimido que se expande en RAM. python-docx carga todo en memoria. 200MB DOCX → puede ser >500MB en RAM. |

---

## 5. Concurrencia

| ID | Severidad | Defecto | Evidencia |
|---|---|---|---|
| **S01** | 🟡 Medio | `asyncio.wait_for` no cancela el thread subyacente — **Documentado como limitación conocida** en v0.2.0 §7 | `run_in_executor` + `wait_for` produce `TimeoutError` pero el thread sigue ejecutándose. v0.2.0 documenta mitigación actual (semáforos estrictos) y plan de mejora (Fase 7: procesos independientes). Aceptado como trade-off de diseño. |
| **S02** | 🟡 Medio | ThreadPoolExecutor workers bloqueados por semáforos | Si OCR semáforo es 3 y hay 10 PDFs con OCR, 8 workers del pool se lanzan, 3 adquieren OCR, 5 esperan el semáforo. Los 5 workers están bloqueados, no procesan otros archivos (PDF sin OCR, imágenes, etc.). |
| **S03** | 🟡 Medio | Sin `_EXECUTOR.shutdown()` documentado | En caso de `SIGTERM`, el pool no se limpia. Los threads en ejecución pueden dejar archivos temporales. |
| **S04** | 🟢 Bajo | Semáforos no protegidos contra uso concurrente en `__init__` | `_EXTRACTION_SEMAPHORES` es un `dict` literal (sección 6). Si dos extractores se inicializan simultáneamente (imports concurrentes), el dict se construye secuencialmente por el GIL. Seguro en CPython. |

---

## 6. Seguridad

| ID | Severidad | Defecto | Evidencia |
|---|---|---|---|
| **SEC01** | 🔴 Crítico | ~~WebExtractor sin protección SSRF~~ ✅ Corregido en v0.2.0 §9.1 | El diseño original no mencionaba bloqueo de IPs privadas. v0.2.0 añade política completa: solo http/https, bloqueo IPs privadas, validación post-DNS y post-redirects, timeouts. |
| **SEC02** | 🔴 Alto | ~~ImageExtractor sin protección contra decompression bomb~~ ✅ Corregido en v0.2.0 §9.2 | El diseño original no configuraba `Image.MAX_IMAGE_PIXELS`. v0.2.0 añade límite 100MP, validación previa con `verify()` sin `load()`, captura de `DecompressionBombError`. |
| **SEC03** | 🟡 Medio | PDF de 100M páginas → denial of service | Sin límite de páginas documentado. Un PDF malicioso con 100M páginas (metadatos, 0 contenido) agota RAM al iterar. |
| **SEC04** | 🟡 Medio | ZIP bomb en DOCX/XLSX/PPTX | Office files son ZIP. Sin límite de ratio de compresión. Un DOCX de 1KB puede expandirse a >1GB. `openpyxl` y `python-docx` no limitan descompresión. |
| **SEC05** | 🟢 Bajo | Git clone en `/tmp` sin control de espacio | Si `TMPDIR` no está configurado, git clone va a `/tmp`. Repos enormes pueden llenar el disco. Documentar destino controlado. |

---

## 7. Escalabilidad

| ID | Severidad | Defecto | Evidencia |
|---|---|---|---|
| **E01** | 🟡 Medio | 1000 extracciones → cuello de botella en AssetStore | Cada extracción hace `AssetStore.save_asset()` → `INSERT OR REPLACE`. SQLite serializa escrituras con `BEGIN IMMEDIATE`. Para 1000 docs, el tiempo de escritura se acumula. El diseño no menciona batch insert ni cola de escritura. |
| **E02** | 🟡 Medio | Semaphore-starvation con workers bloqueados | Ver S02. Con `cpu_count=20` → 10 workers. 3 hacen OCR. 7 esperan. Si los 7 están esperando OCR, 0 procesan otros archivos. El throughput se colapsa a 3 extracciones concurrentes independientemente del pool size. |
| **E03** | 🟢 Bajo | OfficeExtractor: DOCX de 200MB poco realista | Office files >50MB son extremadamente raros. El límite de 200MB es seguro. |

---

## 8. Mantenibilidad

| ID | Severidad | Defecto | Evidencia |
|---|---|---|---|
| **M01** | 🟢 Bajo | `_check_import()` duplicado en 7 extractores | Método estático idéntico en cada extractor. Mover a `knowledge/engine/extractors/base.py` como helper. |
| **M02** | 🟢 Bajo | `_hash_stream()` duplicado en 7 extractores | Misma función de hashing replicada. Mover a helper compartido en `base.py` o `utils.py`. |
| **M03** | 🟢 Bajo | Límites de tamaño (100MB, 200MB, 500MB, 4GB) definidos como literales | Cada extractor define su `MAX_*_SIZE` como constante inline. Centralizar en `extraction_service.py` o `config.py`. |

---

## 9. Mejoras recomendadas (ordenadas por impacto)

| # | ID | Acción | Esfuerzo |
|---|---|---|---|
| 1 | **SEC01** | Añadir protección SSRF a WebExtractor (bloquear IPs privadas, usar `notify.py:WebhookNotifier._block_private_ip` como referencia) | 15min |
| 2 | **SEC02** | Configurar `Image.MAX_IMAGE_PIXELS` y documentar límite de resolución (100MP máx) | 5min |
| 3 | **S01** | Reemplazar `wait_for` por `subprocess` con group kill para whisper/ffmpeg/OCR | 30min |
| 4 | **A01** | Definir `MetadataExtracted` (o `MetadataChanged`) en `eventbus.py`. Alinear nombre con CAPA11_INTEGRATION.md | 5min |
| 5 | **A02** | Definir mecanismo de trigger para GitExtractor (por directorio `.git/`, por URL scheme `git+https://`, o por CLI explícito) | Diseño |
| 6 | **A03** | Añadir detección de MIME por cabecera HTTP en `_guess_mime()` o en `ExtractionService` | 10min |
| 7 | **D01** | Especificar metadatos mínimos para cada extractor sin dependencias. Actualizar tabla de dependencias | 15min |
| 8 | **P01** | Documentar límite de 100MP en ImageExtractor y usar `Image.DecompressionBombError` | 10min |
| 9 | **P02** | Añadir límite de 10.000 páginas en PdfExtractor | 5min |
| 10 | **SEC03** | Añadir límite de páginas a PdfExtractor | 5min |
| 11 | **SEC04** | Documentar límite de ratio de compresión ZIP en OfficeExtractor (rechazar >100:1) | 10min |
| 12 | **S02** | Separar ThreadPoolExecutor en pool rápido + pool lento (o usar semáforo como único limitador) | Diseño |
| 13 | **S03** | Documentar cleanup con `atexit.register(_EXECUTOR.shutdown)` | 5min |
| 14 | **M01-M03** | Centralizar helpers duplicados (`_check_import`, `_hash_stream`, constantes de tamaño) | 30min |

---

## 10. Validación por categoría

| Categoría | Resultado |
|---|---|
| 1. Arquitectura | ⚠️ Aprobado con observaciones — A01, A02, A03 |
| 2. Contratos | ✅ Aprobado — C01-C03 son menores |
| 3. Dependencias | ⚠️ Aprobado con observaciones — D01 (obligatorio vs degradación) |
| 4. Rendimiento | ⚠️ Aprobado con observaciones — P01 (bombas descompresión), P02 (páginas infinitas) |
| 5. Concurrencia | ⚠️ Aprobado con observaciones — S01 documentado como limitación conocida, mejora planificada para Fase 7 |
| 6. Seguridad | ✅ Aprobado — SEC01 y SEC02 corregidos en v0.2.0 (§9.1, §9.2) |
| 7. Escalabilidad | ✅ Aprobado — los cuellos de botella son conocidos y aceptables |
| 8. Mantenibilidad | ✅ Aprobado — M01-M03 son DRY menores |

---

## 11. Veredicto final

> **Aprobado con observaciones** — SEC01 y SEC02 corregidos en v0.2.0. S01 documentado como limitación conocida.

Los defectos **SEC01 (SSRF en WebExtractor)** y **SEC02 (decompression bomb en ImageExtractor)** han sido mitigados en el diseño v0.2.0 con políticas de seguridad documentadas (§9.1, §9.2). La limitación **S01 (threads zombis en timeout)** ha sido documentada como trade-off aceptable, con mejora planificada para Fase 7.

Se recomienda:
1. **Aprobar diseño** condicionalmente.
2. Resolver A02 (trigger GitExtractor) y A03 (MIME por HTTP header) antes de implementar esos extractores.
3. El resto (A01, D01, P01-P02, M01-M03) pueden corregirse durante implementación.

### Defectos corregidos en v0.2.0

| ID | Defecto | Solución en el diseño |
|---|---|---|
| SEC01 | SSRF en WebExtractor | §9.1: política SSRF (esquemas, IPs bloqueadas, validación post-DNS y post-redirects, timeouts) |
| SEC02 | Decompression bomb en ImageExtractor | §9.2: MAX_IMAGE_PIXELS=100MP, validación previa con `verify()`, captura `DecompressionBombError` |
| S01 | Threads zombis en timeout | §7: documentado como limitación conocida, semáforos estrictos como mitigación, Fase 7 planificada |

### Observaciones post-aprobación (corregir durante implementación)

| ID | Defecto | Cuándo corregir |
|---|---|---|
| A01 | MetadataExtracted no existe | Antes de implementar ExtractionService |
| A02 | GitExtractor sin trigger | Antes de implementar GitExtractor |
| A03 | WebExtractor sin MIME por HTTP | Antes de implementar WebExtractor |
| D01 | Dependencias "obligatorias" vs degradación | Durante implementación de cada extractor |
| P01 | Imagen >RAM (ya mitigado, verificar §9.2) | Durante implementación de ImageExtractor |
| P02 | Páginas infinitas PDF | Durante implementación de PdfExtractor |
| M01-M03 | Helpers duplicados | Al inicio de implementación (antes de cualquier extractor) |

---

*Documento generado por auditoría de diseño — Knowledge Engine v0.2.0 — 2026-07-02*
