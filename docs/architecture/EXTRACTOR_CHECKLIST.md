# Extractor Checklist — Validación obligatoria

> **Propósito:** Garantizar que todo extractor (presente y futuro) cumple los mismos estándares de arquitectura, funcionalidad, rendimiento, seguridad, calidad y observabilidad.  
> **Uso:** Marcar cada ítem como ✅ antes de considerar un extractor «completado».  
> **Referencia:** `FASE5_DESIGN.md` v0.2.0, `Extractor(Protocol)` en `extractors/base.py`.

---

## 1. Arquitectura

| # | Ítem | Validación |
|---|------|------------|
| 1.1 | Implementa `Extractor(Protocol)` (no hereda, solo cumple el protocolo) | ✅ |
| 1.2 | No modifica ningún módulo del núcleo (`compiler`, `scanner`, `parser`, `reader`, `orchestrator`, `connection`, `eventbus`) | ✅ |
| 1.3 | No accede directamente a SQLite (ni `open_db()`, ni `begin_immediate()`) | ✅ |
| 1.4 | Solo interactúa con `AssetStore` a través del servicio, o devuelve `ExtractionResult` | ✅ |
| 1.5 | Se auto-registra en `ExtractorRegistry` al importarse | ✅ |
| 1.6 | Se exporta desde `extractors/__init__.py` | ✅ |
| 1.7 | `id` única (sin colisiones con otros extractores) | ✅ |
| 1.8 | `version` en SemVer | ✅ |
| 1.9 | `supported_mime_types` coincide con las extensiones que parsea realmente | ✅ |
| 1.10 | `cost` declarado (`O(1)`, `O(n)`, `O(n²)`) | ✅ |

---

## 2. Funcionalidad

| # | Ítem | Validación |
|---|------|------------|
| 2.1 | `extract(source)` devuelve siempre `ExtractionResult` (nunca lanza excepción) | ✅ |
| 2.2 | `KnowledgeAsset.asset_id` es determinista (SHA-256[:16] del contenido binario real) | ✅ |
| 2.3 | `KnowledgeAsset.asset_type` es correcto | ✅ |
| 2.4 | Metadatos mínimos siempre presentes (`content_sha256`, `size`, `extracted_at`, `_extractor`, `_extractor_version`, `wraps`) | ✅ |
| 2.5 | Metadatos específicos del tipo extraídos correctamente (ver tabla por extractor en FASE5_DESIGN.md) | ✅ |
| 2.6 | `quality` computada (0.0–1.0) con criterio documentado | ✅ |
| 2.7 | Errores devueltos como `ExtractionResult(errors=[...])`, no como excepción | ✅ |
| 2.8 | Warnings devueltos como `ExtractionResult(warnings=[...])` | ✅ |
| 2.9 | `duration_ms` siempre poblado | ✅ |

### Degradación graceful

| # | Ítem | Validación |
|---|------|------------|
| 2.10 | Sin dependencias → asset mínimo con metadatos básicos (size, sha256, filename) | ✅ |
| 2.11 | Dependencia opcional ausente → no error, metadatos incompletos (con warning) | ✅ |
| 2.12 | `_check_import()` para cada dependencia en `__init__` | ✅ |

---

## 3. Rendimiento

| # | Ítem | Validación |
|---|------|------------|
| 3.1 | Archivos > `MAX_EXTRACTION_SIZE` → streaming (no carga completa en RAM) | ✅ |
| 3.2 | Límite de memoria documentado por extractor | ✅ |
| 3.3 | Límite de tamaño de archivo documentado | ✅ |
| 3.4 | Timeout de extracción documentado | ✅ |
| 3.5 | Streaming hash SHA-256 mediante `_hash_stream()` helper (no carga completa) | ✅ |
| 3.6 | Sin dependencias opcionales → metadatos básicos en <100ms | ✅ |

---

## 4. Seguridad

| # | Ítem | Validación |
|---|------|------------|
| 4.1 | Validación de entradas: `source.location` no es vacío ni malicioso | ✅ |
| 4.2 | Path traversal bloqueado: no se permite `../` ni rutas absolutas no esperadas (aplica a extractores locales) | ✅ |
| 4.3 | Protección frente a archivos maliciosos (decompression bomb, páginas infinitas, ZIP bomb) | ✅ |
| 4.4 | Protección SSRF si el extractor hace peticiones HTTP (WebExtractor) | ✅ |
| 4.5 | Logging de eventos de seguridad (intentos de path traversal, IP bloqueada, bomb detectada) | ✅ |
| 4.6 | Errores de seguridad devueltos como `ExtractionResult(errors=[...])` | ✅ |

---

## 5. Calidad (Pruebas)

| # | Ítem | Validación |
|---|------|------------|
| 5.1 | Tests unitarios para cada ruta feliz | ✅ |
| 5.2 | Tests unitarios para cada error esperado (archivo no encontrado, corrupto, sin permisos) | ✅ |
| 5.3 | Tests de integración con `AssetStore` (flujo completo: extract → save → retrieve) | ✅ |
| 5.4 | Casos límite: archivo vacío, extensión incorrecta, dependencia ausente | ✅ |
| 5.5 | Archivos corruptos: el extractor no lanza excepción, devuelve errors | ✅ |
| 5.6 | Archivos grandes: verificar streaming y límite de tamaño | ✅ |
| 5.7 | Determinismo: mismo source → mismo `asset_id` siempre | ✅ |
| 5.8 | Degradación: monkeypatch de imports para simular dependencia ausente | ✅ |
| 5.9 | 0 regresiones en los 175 tests existentes | ✅ |
| 5.10 | Benchmark de tiempo documentado (opcional, recomendado) | ✅ |

---

## 6. Observabilidad

| # | Ítem | Validación |
|---|------|------------|
| 6.1 | Logging informativo en inicio/fin de extracción | ✅ |
| 6.2 | Logging de warnings en degradación graceful | ✅ |
| 6.3 | Logging de errores con traceback en fallos | ✅ |
| 6.4 | Logging de eventos de seguridad (ver §4.5) | ✅ |
| 6.5 | Métricas: `extractions_total`, `extraction_duration_seconds`, `extraction_errors_total` (vía `knowledge/engine/metrics.py`) | ✅ |
| 6.6 | Evento en EventBus: `MetadataExtracted` (cuando esté definido en eventbus.py) | ✅ |
| 6.7 | `correlation_id` propagado en logs si está disponible | ✅ |

---

## 7. Auto-registro y exportación

| # | Ítem | Validación |
|---|------|------------|
| 7.1 | Archivo del extractor en `knowledge/engine/extractors/<nombre>.py` | ✅ |
| 7.2 | `_registry.register(NombreExtractor())` al final del archivo | ✅ |
| 7.3 | Exportado desde `extractors/__init__.py` | ✅ |
| 7.4 | Dependencias documentadas en `requirements/extractors-*.txt` | ✅ |

---

## 8. Auditoría post-implementación

| # | Ítem | Validación |
|---|------|------------|
| 8.1 | El código pasa `ruff check . && ruff format .` sin errores nuevos | ✅ |
| 8.2 | Los 175 tests existentes siguen pasando | ✅ |
| 8.3 | Los nuevos tests del extractor pasan | ✅ |
| 8.4 | Revisión de pares (o auto-revisión documentada) completada | ✅ |
| 8.5 | Checklist firmado y pegado en el acta de auditoría del extractor | ✅ |

---

*Documento generado para Fase 5 — 2026-07-02. Obligatorio para todos los extractores.*
