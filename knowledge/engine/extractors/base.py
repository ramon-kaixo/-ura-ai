"""Extractor Protocol — interfaz común para todos los extractores de metadatos.

Cada extractor:
  - Tiene un id y version únicos (SemVer)
  - Declara qué MIME types soporta
  - Declara su coste estimado
  - Implementa extract(source) → ExtractionResult
  - Es determinista: mismo source → mismo resultado
  - Nunca modifica el source original
"""

from __future__ import annotations

import hashlib
import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from knowledge.engine.ontology.internal import AssetSource, KnowledgeAsset

log = logging.getLogger("ura.knowledge.extractors")

# ── Shared constants ──────────────────────────────────────────────────

MAX_STREAM_CHUNK = 64 * 1024  # 64 KB chunks for streaming hash/size


# ── Shared helpers ────────────────────────────────────────────────────


def _hash_stream(path: str | Path) -> tuple[str, int]:
    """Calcula SHA-256 y tamaño de un archivo en modo streaming.

    Args:
        path: Ruta al archivo.

    Returns:
        (sha256_hex, size_bytes).

    Raises:
        FileNotFoundError: si el archivo no existe.
        OSError: si hay error de lectura.
    """
    h = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(MAX_STREAM_CHUNK)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _check_import(module_name: str, package: str | None = None) -> bool:
    """Verifica si un módulo está disponible sin importarlo globalmente.

    Args:
        module_name: Nombre del módulo (ej: "fitz", "PIL").
        package: Nombre del paquete para logging (opcional).

    Returns:
        True si el módulo está disponible.
    """
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        pkg = package or module_name
        log.debug("Optional dependency not available: %s", pkg)
        return False


@dataclass
class ExtractionResult:
    """Resultado de una extracción de metadatos.

    Attributes:
        asset: KnowledgeAsset generado (None si no se pudo generar).
        warnings: Advertencias durante la extracción.
        errors: Errores durante la extracción.
        duration_ms: Duración de la extracción en milisegundos.
    """

    asset: KnowledgeAsset | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


class Extractor(Protocol):
    """Contrato para todos los extractores de metadatos.

    Uso:
        class MyExtractor:
            id = "my_extractor"
            version = "1.0.0"
            supported_mime_types = ["text/plain"]
            cost = "O(1)"

            def extract(self, source: AssetSource) -> ExtractionResult: ...
    """

    id: str
    version: str
    supported_mime_types: list[str]
    cost: str  # "O(1)" | "O(n)" | "O(n²)"

    def extract(self, source: AssetSource) -> ExtractionResult:
        """Extrae metadatos de un source y produce un KnowledgeAsset."""
        ...


class ExtractorRegistry:
    """Registro central de extractores.

    Los extractores se registran automáticamente al importarlos.
    Se puede consultar por MIME type o ID.
    """

    def __init__(self):
        self._extractors: dict[str, Extractor] = {}

    def register(self, extractor: Extractor) -> None:
        """Registra un extractor."""
        self._extractors[extractor.id] = extractor
        mimes = extractor.supported_mime_types or []
        log.debug("Registered extractor: %s v%s (%s)", extractor.id, extractor.version, ", ".join(mimes))

    def get(self, extractor_id: str) -> Extractor | None:
        """Obtiene un extractor por ID."""
        return self._extractors.get(extractor_id)

    def get_for_mime(self, mime_type: str) -> list[Extractor]:
        """Obtiene extractores que soportan un MIME type."""
        return [e for e in self._extractors.values() if mime_type in e.supported_mime_types]

    def list(self) -> list[Extractor]:
        """Lista todos los extractores registrados."""
        return list(self._extractors.values())

    @property
    def count(self) -> int:
        return len(self._extractors)


# ── Registry singleton ──────────────────────────────────────────────────

_REGISTRY: ExtractorRegistry | None = None


def get_registry() -> ExtractorRegistry:
    """Retorna el registro global de extractores."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ExtractorRegistry()
    return _REGISTRY
