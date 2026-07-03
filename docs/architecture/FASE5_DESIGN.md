# Fase 5 — Extractores Reales (Diseño técnico)

> **Versión:** 0.2.0 (diseño revisado)  
> **Fecha:** 2026-07-02  
> **Estado:** Aprobado con observaciones — Ver AUDIT_FASE5_DESIGN.md para observaciones pendientes  
> **Dependencias:** Fase 0–4 completadas, núcleo congelado v0.2.0  

---

## 1. Arquitectura general

```
Source (archivo/URL/stream)
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                  ExtractionService                           │
│  1. Detectar MIME type por extensión o cabecera              │
│  2. Buscar extractores registrados en ExtractorRegistry      │
│  3. Ejecutar extractor(es)                                   │
│     - Síncrono: pasos rápidos (metadatos técnicos)           │
│     - Background: pasos lentos (OCR, whisper, thumbnails)    │
│  4. Almacenar resultado en AssetStore                         │
│  5. Publicar evento MetadataExtracted                        │
└──────────────────────┬───────────────────────────────────────┘
                       │
          ┌────────────┼────────────┬──────────────┐
          ▼            ▼            ▼              ▼
    MarkdownExtr.  PdfExtractor  VideoExtractor  ImageExtractor
    AudioExtractor  WebExtractor  GitExtractor   OfficeExtractor
          │            │            │              │
          ▼            ▼            ▼              ▼
    ┌─────────────────────────────────────────────────────────┐
    │                   AssetStore.store()                     │
    │   → op_assets (metadatos completos)                      │
    │   → EventBus.publish(MetadataExtracted)                  │
    └─────────────────────────────────────────────────────────┘
```

### Principios

- **Ningún extractor modifica el núcleo** (compiler, scanner, parser, reader, orchestrator).
- **Degradación graceful**: toda dependencia externa es opcional. Sin ffprobe → video sin metadatos técnicos, pero asset se crea igual.
- **Determinismo**: mismo source → mismo hash → misma extracción. El timestamp de extracción no afecta al asset_id (SHA-256 del contenido).
- **Coste declarado**: cada extractor declara `O(1)`, `O(n)` o `O(n²)`.
- **Streaming**: archivos grandes (>100MB) se procesan en chunks sin cargar en memoria.

---

## 2. Extractor(Protocol) — Contrato actual

Ya existe en `knowledge/engine/extractors/base.py`. NO se modifica.

```python
class Extractor(Protocol):
    id: str                                    # "pdf", "video", "image", …
    version: str                               # "1.0.0" (SemVer)
    supported_mime_types: list[str]             # ["application/pdf", …]
    cost: str                                  # "O(1)" | "O(n)" | "O(n²)"

    def extract(self, source: AssetSource) -> ExtractionResult: ...
```

### Contratos que cada extractor debe cumplir

1. **Nunca lanzar excepción**: capturar todo y devolver `ExtractionResult(errors=[...])`.
2. **No depender del filesystem del proyecto**: el source.location es la única entrada.
3. **Debe funcionar sin internet**: web/git son excepciones documentadas.
4. **El asset_id es determinista**: SHA-256[:16] del contenido binario del source.
5. **Debe declarar sus dependencias**: en el docstring y en `requirements/extractors-*.txt`.
6. **Respetar `MAX_EXTRACTION_SIZE`**: archivos mayores entran en modo streaming.
7. **No bloquear el EventBus**: pasos lentos van a background thread.

```python
@dataclass
class ExtractionResult:
    asset: KnowledgeAsset | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
```

---

## 3. Flujo de datos — Extractor → AssetStore

### Pipeline completo

```
1. ExtractionService.extract(source)
2.   └── _guess_mime(location) → "application/pdf"
3.   └── registry.get_for_mime("application/pdf") → [PdfExtractor]
4.   └── PdfExtractor.extract(source)
5.       ├── ffprobe(path) si aplica
6.       ├── open(path, 'rb') en modo streaming
7.       ├── parse metadatos (páginas, autor, título…)
8.       ├── calcular content_sha256 (hash del contenido real)
9.       └── devolver ExtractionResult(asset=KnowledgeAsset(...))
10.  └── AssetStore.save_asset(asset)
11.      └── INSERT OR REPLACE INTO op_assets
12.  └── EventBus.publish(MetadataExtracted)
```

### Determinismo del asset_id

```python
asset_id = hashlib.sha256(content_bytes).hexdigest()[:16]
```

- El hash se calcula sobre el contenido binario **real** del archivo (no sobre el path ni los metadatos extraídos).
- Si dos sources tienen el mismo contenido binario pero distinto path → mismo asset_id.
- Si el contenido cambia → distinto asset_id → nuevo asset (el anterior no se modifica).

### Metadatos mínimos (todos los extractores)

```python
metadata = {
    "title": str,              # extraído o filename
    "content_sha256": str,     # SHA-256 completo (no truncado)
    "size": int,               # bytes
    "extracted_at": str,       # ISO 8601
    "_extractor": str,         # id del extractor
    "_extractor_version": str, # SemVer
    "wraps": str,              # "source:{path}" | "url:{url}"
}
```

---

## 4. Estrategia de gestión de errores

### Categorías

| Categoría | Ejemplo | Acción |
|---|---|---|
| **Error transitorio** | Timeout de red, ffprobe no responde | Reintentar 3 veces con backoff (5s, 30s, 120s) |
| **Error permanente** | Archivo corrupto, formato no soportado | No reintentar. Devolver `ExtractionResult(errors=[...])` |
| **Dependencia faltante** | whisper no instalado | Degradación graceful: omitir paso, log warning |
| **Archivo no encontrado** | source.location no existe | Devolver `ExtractionResult(errors=["File not found"])` |
| **Archivo demasiado grande** | >MAX_EXTRACTION_SIZE | Activar modo streaming |

### Propagación

```python
# El extractor NUNCA lanza:
def extract(self, source: AssetSource) -> ExtractionResult:
    try:
        data = self._read(source)
        asset = self._build_asset(data)
        return ExtractionResult(asset=asset)
    except FileNotFoundError:
        return ExtractionResult(errors=[f"File not found: {source.location}"])
    except Exception as exc:
        return ExtractionResult(errors=[f"Extraction error: {exc}"])

# ExtractionService maneja errores del store:
saved = store.save_asset(result.asset)
if not saved:
    log.warning("Asset %s not saved (duplicate or DB error)", asset_id)
```

---

## 5. Estrategia de streaming para archivos grandes

### Límites

| Tipo | MAX_EXTRACTION_SIZE | Modo streaming |
|---|---|---|
| PDF | 500 MB | ✅ Por página |
| Video | 4 GB | ✅ Por paquete ffprobe (cabeceras) |
| Audio | 500 MB | ✅ Cabeceras ffprobe + chunks |
| Imagen | 100 MB | ✅ Carga redimensionada si excede |
| Office | 200 MB | ✅ Por hoja/slide |
| Git | N/A | Shallow clone (`--depth 1`) |
| Web | 10 MB | ✅ Límite httpx + stream |

### Implementación

```python
MAX_EXTRACTION_SIZE = 500 * 1024 * 1024  # 500 MB

def _read_stream(self, path: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    size = Path(path).stat().st_size
    if size > MAX_EXTRACTION_SIZE:
        log.info("Streaming large file: %s (%d MB)", path, size // (1024 * 1024))
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk
```

Para hashing de archivos grandes sin cargar en memoria:

```python
def _hash_stream(self, path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
```

---

## 6. Gestión de memoria y recursos

### Límites por extractor

| Extractor | RAM estimada | Límite |
|---|---|---|
| PdfExtractor | <200 MB por documento | 500 MB max |
| ImageExtractor (EXIF) | <100 MB por imagen | Memmap para grandes |
| ImageExtractor (OCR) | <300 MB por imagen | Semáforo (3 max) |
| VideoExtractor | <500 MB + 2-8 GB (whisper) | Semáforo (1 whisper) |
| AudioExtractor | <50 MB + 1-4 GB (whisper) | Semáforo (1 whisper) |
| OfficeExtractor | <200 MB por archivo | 500 MB max |
| GitExtractor | <500 MB por repo | Shallow clone |
| WebExtractor | <50 MB por página | 10 MB body limit |

### Semáforos globales (en extraction_service.py)

```python
_EXTRACTION_SEMAPHORES: dict[str, Semaphore] = {
    "ocr": Semaphore(3),
    "whisper": Semaphore(1),
    "ffmpeg": Semaphore(2),
    "git": Semaphore(2),
    "web": Semaphore(5),
}
```

### Cleanup forzado

Todo extractor que genere archivos temporales (thumbnails, transcripts) debe:

```python
import tempfile

class VideoExtractor:
    def extract(self, source):
        tmp_dir = tempfile.mkdtemp(prefix="ura_extract_")
        try:
            # ... trabajo con thumbnails en tmp_dir ...
            return result
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
```

---

## 7. Estrategia de concurrencia

### Pool de extractores

```python
from concurrent.futures import ThreadPoolExecutor

_EXECUTOR = ThreadPoolExecutor(
    max_workers=max(1, os.cpu_count() // 2),
    thread_name_prefix="extractor",
)
```

- Máximo `cpu_count // 2` extractores simultáneos.
- Extractores lentos (whisper, OCR, Git) se lanzan como background jobs.
- El pipeline principal espera solo por extractores rápidos (<1s).

### Prioridad

| Prioridad | Extractores | Comportamiento |
|---|---|---|
| Alta (síncrono) | Markdown, Office, EXIF, ffprobe | Bloquea el pipeline |
| Baja (background) | whisper, OCR, git clone, scene detection | Se ejecuta en background, publica evento al terminar |

### Cola de background

Los extractores lentos se encolan en `op_extraction_queue` (Fase 7) o se ejecutan via `asyncio.create_task` (simplificado):

```python
async def extract_background(self, source: AssetSource, extractor_id: str):
    extractor = self._registry.get(extractor_id)
    result = await asyncio.get_event_loop().run_in_executor(
        _EXECUTOR, extractor.extract, source
    )
    if result.asset:
        self._store.save_asset(result.asset)
    get_bus().publish(MetadataExtracted(
        asset_id=result.asset.asset_id if result.asset else "",
        extractor=extractor_id,
        success=result.asset is not None,
    ))
```

### Limitación conocida: S01 — Threads no cancelables

`asyncio.wait_for` + `run_in_executor` no puede cancelar threads en ejecución.
Cuando un timeout expira, el thread sigue ejecutándose hasta completar o ser interrumpido
internamente (ej: lectura de socket). Esto puede dejar "threads zombis" que consumen
recursos sin supervisión.

**Impacto**: En condiciones normales (timeout >> tiempo real de extracción) es irrelevante.
Bajo carga extrema o fallos de red, puede haber N threads zombies simultáneos donde
N = tamaño del pool.

**Mitigación actual**: Semáforos estrictos (OCR=3, whisper=1, ffmpeg=2, git=2, web=5)
limitan el número máximo de threads concurrentes. Extractores colgados liberan su
slot del semáforo al expirar su timeout individual.

**Mejora futura**: Fase 7 introducirá procesos independientes (`multiprocessing.Process`)
para lograr cancelación real mediante `SIGTERM` + `Process.join(timeout)`.

---

## 8. Dependencias opcionales y degradación graceful

### Mapa completo

| Extractor | Dependencia | Obligatoria | Fallback | Metadatos perdidos |
|---|---|---|---|---|
| PDF | `PyMuPDF` (fitz) | ✅ Sí | — | Asset sin metadatos |
| PDF | `pytesseract` + `tesseract-ocr` | ❌ No | Sin OCR | Sin texto en páginas escaneadas |
| Imagen | `Pillow` | ✅ Sí | — | Asset sin metadatos |
| Imagen | `pytesseract` + `tesseract-ocr` | ❌ No | Sin OCR | Sin texto en imágenes |
| Video | `ffprobe` | ❌ No | Sin metadatos técnicos | Sin duración/códecs/resolución |
| Video | `ffmpeg` | ❌ No | Sin thumbnails | Sin thumbnails |
| Video | `opencv-python` | ❌ No | Sin scene detection | Sin scene_count |
| Video | `openai-whisper` | ❌ No | Sin transcript | Sin transcripción |
| Audio | `ffprobe` | ❌ No | Sin metadatos técnicos | Asset mínimo |
| Audio | `openai-whisper` | ❌ No | Sin transcript | Sin transcripción |
| Office | `python-docx` | ❌ No | Sin texto | Asset mínimo |
| Office | `openpyxl` | ❌ No | Sin texto | Asset mínimo |
| Office | `pptx` | ❌ No | Sin texto | Asset mínimo |
| Git | `git` (CLI) | ❌ No | Sin metadata | Asset mínimo |
| Web | `httpx` | ❌ No | Sin contenido | Asset mínimo |
| Web | `beautifulsoup4` | ❌ No | Sin parseo | Solo raw HTML |

### Detección en `__init__`

```python
class PdfExtractor:
    def __init__(self):
        self._has_fitz = self._check_import("fitz")
        self._has_ocr = self._check_import("pytesseract")

    @staticmethod
    def _check_import(name: str) -> bool:
        try:
            __import__(name)
            return True
        except ImportError:
            return False
```

---

## 9. Seguridad

### 9.1 Protección SSRF — WebExtractor

WebExtractor es el único extractor que realiza peticiones HTTP a URLs arbitrarias. Todos los demás extractores operan sobre el sistema de archivos local. Esta sección define la política de seguridad que debe implementar `WebExtractor._validate_url()`.

#### Esquemas permitidos

| Esquema | ¿Permitido? | Notas |
|---|---|---|
| `http://` | ✅ Sí | Solo tras validación de IP |
| `https://` | ✅ Sí | Solo tras validación de IP |
| `ftp://` | ❌ No | Riesgo de FTP bounce attack |
| `file://` | ❌ No | Acceso a sistema de archivos local |
| `data://` | ❌ No | Posible vector de ataques |
| `gopher://` | ❌ No | Protocolo obsoleto, riesgo SSRF |
| `dict://` | ❌ No | Protocolo obsoleto |
| Otros | ❌ No | Cualquier esquema no listado explícitamente |

#### IPs y rangos bloqueados (tanto en IPv4 como IPv6)

| Rango | Motivo |
|---|---|
| `127.0.0.0/8` | Loopback IPv4 |
| `::1/128` | Loopback IPv6 |
| `10.0.0.0/8` | Red privada RFC 1918 |
| `172.16.0.0/12` | Red privada RFC 1918 |
| `192.168.0.0/16` | Red privada RFC 1918 |
| `169.254.0.0/16` | Link-local (incluye metadata cloud) |
| `fe80::/10` | Link-local IPv6 |
| `fc00::/7` | Unique local address IPv6 |
| `0.0.0.0/8` | Zero-config / non-routable |
| `100.64.0.0/10` | Carrier-grade NAT (posible conflicto) |
| `198.18.0.0/15` | Benchmarking |
| `240.0.0.0/4` | Reserved / future use |

**Casos especiales:**

| Dirección | Motivo |
|---|---|
| `169.254.169.254` | Metadata cloud AWS/GCP/Azure |
| `0.0.0.0` | No es una IP válida para peticiones |
| `localhost` | Hostname → loopback |
| `127.*.*.*` | Loopback en cualquiera de sus formas |

#### Timing de las validaciones

```
1. Validar esquema (antes de cualquier resolución DNS)
2. Parsear URL → hostname
3. Si hostname es IPv4/IPv6 literal → validar IP inmediatamente
4. Resolver DNS → lista de IPs
5. Para cada IP resuelta → SI alguna es privada → RECHAZAR
6. Realizar petición HTTP
7. Tras cada redirección → re-validar paso 1-5
   (el servidor redirige a localhost o IP privada)
```

#### Timeouts

| Límite | Valor |
|---|---|
| `connect_timeout` | 10s |
| `read_timeout` | 30s (descarga body) |
| `total_timeout` | 60s (petición completa) |
| DNS resolution timeout | 5s |

#### Tamaños y redirecciones

| Límite | Valor |
|---|---|
| `MAX_BODY_SIZE` | 10 MB |
| `MAX_REDIRECTS` | 5 saltos |
| `MAX_HEADER_SIZE` | 64 KB |

#### Comportamiento ante incumplimiento

```python
class SSRFError(ValueError):
    """URL rechazada por política SSRF."""
    pass

class URLSchemeBlocked(SSRFError):
    """Esquema no permitido."""
    pass

class PrivateIPBlocked(SSRFError):
    """IP privada o no ruteable."""
    pass

class CloudMetadataBlocked(SSRFError):
    """Posible endpoint de metadata cloud."""
    pass
```

En todos los casos el WebExtractor devuelve `ExtractionResult(errors=[str(exc)])`.

#### Plan de pruebas (SSRF)

| Prueba | Descripción |
|---|---|
| Esquema file:// rechazado | Verificar `URLSchemeBlocked` |
| Esquema data:// rechazado | Verificar `URLSchemeBlocked` |
| Esquema ftp:// rechazado | Verificar `URLSchemeBlocked` |
| http://127.0.0.1 rechazado | Verificar `PrivateIPBlocked` |
| http://localhost rechazado | Verificar `PrivateIPBlocked` |
| http://10.0.0.1 rechazado | Verificar `PrivateIPBlocked` |
| http://192.168.1.1 rechazado | Verificar `PrivateIPBlocked` |
| http://169.254.169.254 rechazado | Verificar `CloudMetadataBlocked` |
| DNS que resuelve a 127.0.0.1 rechazado | Verificar tras resolución |
| Redirección a IP privada bloqueada | Verificar tras redirección |
| Hostname legítimo permitido | Verificar que pasa |
| Subdominio con "localhost" en nombre (no loopback) | Permitido si IP no es privada |
| Timeout total 60s | Verificar httpx.TimeoutException |
| Body >10MB truncado | Verificar error o truncamiento |

### 9.2 Protección contra decompression bombs — ImageExtractor

#### Límites

| Parámetro | Valor | Notas |
|---|---|---|
| `MAX_IMAGE_PIXELS` | 100 MP | 100 megapíxeles máx (suficiente para 99.9% de imágenes reales) |
| `MAX_IMAGE_DIMENSION` | 20.000 px | Ningún lado puede exceder 20.000 px |
| `MAX_EXTRACTION_SIZE` | 100 MB | Tamaño de archivo antes de streaming |
| `DECOMPRESSION_RATIO_MAX` | 50:1 | Ratio compresión/descompresión (ZIP bomb mitigation) |

#### Validaciones previas a la carga

```
1. stat() del archivo: size > MAX_EXTRACTION_SIZE? → Rechazar
2. Pillow Image.open() → solo cabeceras (lazy)
3. Verificar Image.format es uno de los soportados
4. Verificar Image.size (width, height):
     - width > MAX_IMAGE_DIMENSION? → Rechazar
     - height > MAX_IMAGE_DIMENSION? → Rechazar
     - width * height > MAX_IMAGE_PIXELS? → Rechazar
5. Si todo OK → Image.load() (descompresión real)
```

#### Estrategia de memoria

```python
from PIL import Image

Image.MAX_IMAGE_PIXELS = 100 * 1024 * 1024  # 100 MP

def _safe_load(self, path: str) -> Image.Image | None:
    try:
        img = Image.open(path)
        w, h = img.size
        if w > 20_000 or h > 20_000 or w * h > 100_000_000:
            raise Image.DecompressionBombError(
                f"Image too large: {w}x{h} = {w*h}px (limit 100MP)"
            )
        img.load()
        return img
    except Image.DecompressionBombError:
        raise
    except Exception as exc:
        log.warning("Cannot load image %s: %s", path, exc)
        return None
```

#### Excepciones esperadas

| Excepción | Cuándo | Acción |
|---|---|---|
| `PIL.Image.DecompressionBombError` | Imagen > MAX_IMAGE_PIXELS | ExtractionResult(errors=["Image too large"]) |
| `PIL.UnidentifiedImageError` | Formato no soportado | ExtractionResult(errors=["Unsupported format"]) |
| `OSError` (truncado) | Archivo corrupto | ExtractionResult(errors=["Corrupted image"]) |

#### Logging

```python
if w * h >= MAX_IMAGE_PIXELS // 2:
    log.warning("Large image: %s (%dx%d = %dpx)", path, w, h, w * h)
```

#### Casos de prueba

| Prueba | Descripción |
|---|---|
| Imagen normal (1920x1080) | Extracción exitosa |
| Imagen 200MP (sin load) | `DecompressionBombError` en validación previa |
| Imagen 25.000x25.000px | `DecompressionBombError` por dimensión |
| Imagen corrupta (truncada) | `OSError` → ExtractionResult(errors) |
| Formato no soportado (.bmp) | `UnidentifiedImageError` → ExtractionResult(errors) |
| Imagen 95MB (cerca del límite) | Extracción exitosa (streaming) |
| Imagen con EXIF GPS | Extracción correcta de coordenadas |

---

## 10. Inventario de extractores a implementar

### 10.1 PdfExtractor

| Aspecto | Detalle |
|---|---|
| MIME | `application/pdf` |
| Dependencias | PyMuPDF (fitz), pytesseract (opcional) |
| Metadatos | páginas, título, autor, subject, keywords, creación, texto completo |
| Coste | O(n) |
| Streaming | Por página (fitz.open → page by page) |
| OCR | Páginas sin texto → tesseract (opcional, semáforo 3) |
| AssetType | `AssetType.PDF` |

### 10.2 ImageExtractor

| Aspecto | Detalle |
|---|---|
| MIME | `image/jpeg`, `image/png`, `image/webp`, `image/gif` |
| Dependencias | Pillow, pytesseract (opcional) |
| Metadatos | EXIF, GPS, device, date_taken, dimensiones, formato, thumbnail, orientación |
| Coste | O(n) sin OCR, O(n²) con OCR |
| OCR | pytesseract (opcional, semáforo 3) |
| Thumbnail | Pillow resize (256px máximo lado mayor) |
| Protección | Decompression bomb: MAX_IMAGE_PIXELS=100MP, validación previa (ver §9.2) |
| Límite | 100 MB; mayor → streaming con memmap |
| AssetType | `AssetType.IMAGE` |

### 10.3 VideoExtractor

| Aspecto | Detalle |
|---|---|
| MIME | `video/mp4`, `video/webm`, `video/avi`, `video/mov` |
| Dependencias | ffprobe, ffmpeg, opencv-python (opcionales), whisper (opcional) |
| Metadatos técnicos | duración, resolución, fps, bitrate, codec video/audio, sample rate, canales |
| Thumbnails | ffmpeg (3 thumbnails: 10%, 50%, 90%) |
| Scene detection | opencv (opcional) |
| Transcripción | whisper (background, semáforo 1) |
| Coste | O(n) técnico, O(n²) con whisper |
| Límite | 4 GB; cabeceras ffprobe no requieren lectura completa |
| AssetType | `AssetType.VIDEO` |

### 10.4 AudioExtractor

| Aspecto | Detalle |
|---|---|
| MIME | `audio/mp3`, `audio/wav`, `audio/flac`, `audio/ogg` |
| Dependencias | ffprobe, whisper (opcional) |
| Metadatos técnicos | duración, bitrate, codec, sample rate, canales |
| Transcripción | whisper (background, semáforo 1) |
| Coste | O(1) técnico, O(n) con whisper |
| Límite | 500 MB |
| AssetType | `AssetType.AUDIO` |

### 10.5 OfficeExtractor

| Aspecto | Detalle |
|---|---|
| MIME | DOCX, XLSX, PPTX |
| Dependencias | python-docx, openpyxl, pptx |
| Metadatos | título, autor, created_at, modified_at, párrafos, tablas, hojas, diapositivas |
| Coste | O(n) |
| Límite | 200 MB |
| AssetType | `AssetType.OFFICE_DOC`, `.OFFICE_SHEET`, `.OFFICE_SLIDE` |

### 10.6 WebExtractor

| Aspecto | Detalle |
|---|---|
| MIME | `text/html` |
| Dependencias | httpx, beautifulsoup4 |
| Metadatos | title, description, texto, imágenes, enlaces, publication_date |
| Coste | O(n) |
| Protección | SSRF: solo http/https, bloqueo IPs privadas, validación post-DNS y post-redirects (ver §9.1) |
| Límite | 10 MB body, timeout 30s, max 5 redirects |
| Concurrencia | Semáforo 5 |
| Respeto | robots.txt (opcional) |
| AssetType | `AssetType.API_REFERENCE` o `UNKNOWN` |

### 10.7 GitExtractor

| Aspecto | Detalle |
|---|---|
| MIME | N/A (clona repositorio) |
| Dependencias | git CLI |
| Metadatos | commits recientes, autores, branches, tags, release_notes, changelog |
| Coste | O(n²) |
| Clone | `--depth 1 --single-branch` por defecto |
| Concurrencia | Semáforo 2 |
| AssetType | `AssetType.GIT_REPO` |

---

## 11. Plan de pruebas

### Estrategia

| Tipo | Herramienta | Objetivo |
|---|---|---|
| Unitarias (cada extractor) | pytest + hypothesis | Verificar extracción con archivos de prueba pequeños |
| Integración (store + extractor) | pytest con temp file | Verificar flujo completo → op_assets |
| Degradación | Monkeypatch de imports | Verificar que sin dependencias opcionales el extractor produce metadatos mínimos |
| Archivos grandes | hypothesis + strategy | Generar archivos grandes sintéticos y verificar streaming |
| Concurrencia | pytest + ThreadPoolExecutor | Lanzar 10 extracciones simultáneas y verificar semáforos |
| Error handling | Archivos corruptos | Verificar ExtractionResult(errors) sin excepciones |
| Determinismo | SHA-256 repeat | Mismo archivo → mismo asset_id siempre |

### Cobertura mínima por extractor

| Prueba | PdfExtractor | ImageExtractor | VideoExtractor | AudioExtractor | OfficeExtractor | WebExtractor | GitExtractor |
|---|---|---|---|---|---|---|---|
| Extracción feliz | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Degradación graceful | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Archivo no encontrado | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Archivo corrupto | ✅ | ✅ | ✅ | N/A | ✅ | N/A | N/A |
| Archivo grande (>límite) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | N/A |
| Determinismo (hash) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Metadatos mínimos | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Estimación de tests

| Extractor | Tests unitarios | Tests integración | Total |
|---|---|---|---|
| PdfExtractor | 5 | 2 | 7 |
| ImageExtractor | 5 | 2 | 7 |
| VideoExtractor | 6 | 2 | 8 |
| AudioExtractor | 4 | 2 | 6 |
| OfficeExtractor | 4 | 2 | 6 |
| WebExtractor | 4 | 2 | 6 |
| GitExtractor | 3 | 2 | 5 |
| **Total** | **31** | **14** | **45** |

---

## 12. Riesgos técnicos

| Riesgo | Impacto | Probabilidad | Mitigación |
|---|---|---|---|
| **whisper muy lento** (10min por hora de audio) | Extracción bloqueada minutos | Alta | Background queue + timeout 30min + `asyncio.wait_for` |
| **ffprobe no instalado** en servidor | Video/audio sin metadatos técnicos | Alta en entornos sin ffmpeg | Degradación graceful documentada |
| **PDF de 1000+ páginas** | PyMuPDF lento, RAM >500MB | Baja | Streaming por página + límite 500MB |
| **Imagen de 100MP+** (RAW/decompression bomb) | Pillow OOM | Baja | `DecompressionBombError` capturado, validación previa con `verify()` sin `load()` (ver §9.2) |
| **Video 4K 60fps largo** | ffmpeg lento, thumbnails tardan | Baja | Thumbnails con `-ss` (seek) no `-i` |
| **Web scraping bloqueado** | HTTP 403/429 | Media | Timeout + user-agent configurable + respeto `robots.txt` |
| **Git clone de repo enorme** | Disco lleno, timeout | Baja | `--depth 1 --single-branch` por defecto |
| **Office corrompido** | python-docx/openpyxl lanzan excepción | Baja | Captura general en cada extractor |

---

## 13. Criterios de aceptación

Para dar por cerrada la Fase 5, deben cumplirse todos:

1. ✅ 7 extractores implementados (PDF, Image, Video, Audio, Office, Web, Git)
2. ✅ Cada extractor sigue `Extractor(Protocol)` sin modificarlo
3. ✅ Degradación graceful: sin dependencias opcionales → asset mínimo (no error)
4. ✅ Asset_id determinista: mismo source → mismo id siempre
5. ✅ Archivos grandes (>límite) → streaming, no OOM
6. ✅ Sin dependencias circulares ni modificaciones al núcleo
7. ✅ 45+ tests nuevos pasando
8. ✅ Sin regresiones en los 175 tests existentes
9. ✅ API `/metadata/assets` devuelve assets de todos los tipos
10. ✅ Documentación de dependencias opcionales en `requirements/extractors-*.txt`

---

*Documento de diseño — Knowledge Engine v0.2.0 — Fase 5 — 2026-07-02*
