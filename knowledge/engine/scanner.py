"""Scanner — descubre SourceObjects en source/ y produce Snapshot.

El Scanner descubre objetos de conocimiento, no solo archivos .md.
El kind se determina por extensión (markdown, yaml, json, drawio, mermaid...).

El scanner lee el contenido y lo almacena en SourceObject.content.
El parser NUNCA vuelve a abrir el archivo — elimina el TOCTOU.
"""

from __future__ import annotations

import datetime
import hashlib
from typing import TYPE_CHECKING

from knowledge.engine.models import MAX_PARSE_SIZE, CompileError, Snapshot, SourceObject

if TYPE_CHECKING:
    from pathlib import Path


def scan_source(source_dir: Path) -> tuple[list[SourceObject], list[CompileError]]:
    """Escanea source/ recursivamente y descubre todos los SourceObjects.

    Retorna (sources, skipped) donde skipped son los archivos > MAX_PARSE_SIZE.
    """
    if not source_dir.is_dir():
        return [], []

    sources: list[SourceObject] = []
    skipped: list[CompileError] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            skipped.append(
                CompileError(
                    code="KE210",
                    document=str(path.relative_to(source_dir)),
                    stage="scanner",
                    message=f"Enlace simbólico omitido: {path.name}",
                    category="permanent",
                ),
            )
            continue
        stat = path.stat()
        rel = str(path.relative_to(source_dir))
        if stat.st_size > MAX_PARSE_SIZE:
            skipped.append(
                CompileError(
                    code="KE205",
                    document=rel,
                    stage="scanner",
                    message=f"Archivo omitido por tamaño ({stat.st_size} > {MAX_PARSE_SIZE}): {rel}",
                    category="permanent",
                ),
            )
            continue
        if stat.st_size == 0:
            continue
        raw = path.read_bytes()
        sources.append(
            SourceObject(
                id=rel,
                path=rel,
                kind=SourceObject.kind_for(path),
                content_sha256=hashlib.sha256(raw).hexdigest(),
                size=len(raw),
                content=raw,
            ),
        )
    return sources, skipped


def scan_source_stream(source_dir: Path):
    """Generador: descubre SourceObjects sin acumularlos en RAM.

    yield SourceObject individualmente.
    Cada SourceObject contiene content bytes para el parser.
    El parser consume y libera — nunca se acumulan N objetos en RAM.
    """
    if not source_dir.is_dir():
        return
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            continue
        stat = path.stat()
        rel = str(path.relative_to(source_dir))
        if stat.st_size > MAX_PARSE_SIZE:
            yield CompileError(
                code="KE205",
                document=rel,
                stage="scanner",
                message=f"Archivo omitido por tamaño ({stat.st_size} > {MAX_PARSE_SIZE}): {rel}",
                category="permanent",
            )
            continue
        if stat.st_size == 0:
            continue
        raw = path.read_bytes()
        yield SourceObject(
            id=rel,
            path=rel,
            kind=SourceObject.kind_for(path),
            content_sha256=hashlib.sha256(raw).hexdigest(),
            size=len(raw),
            content=raw,
        )


def take_snapshot(source_dir: Path) -> Snapshot:
    """Toma un snapshot lógico completo de source/.

    Los SourceObjects en el snapshot NO contienen content bytes
    (solo metadatos para detección de cambios). El snapshot
    es ligero y no replica el contenido en RAM.
    """
    if not source_dir.is_dir():
        return Snapshot(sources=(), taken_at=datetime.datetime.now(datetime.UTC).isoformat())
    sources: list[SourceObject] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            continue
        stat = path.stat()
        rel = str(path.relative_to(source_dir))
        if stat.st_size == 0 or stat.st_size > MAX_PARSE_SIZE:
            continue
        raw = path.read_bytes()
        sources.append(
            SourceObject(
                id=rel,
                path=rel,
                kind=SourceObject.kind_for(path),
                content_sha256=hashlib.sha256(raw).hexdigest(),
                size=len(raw),
                content=b"",  # snapshot no necesita content bytes
            ),
        )
    return Snapshot(
        sources=tuple(sources),
        taken_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )


def scan_incremental(
    previous: Snapshot | None,
    source_dir: Path,
) -> tuple[list[SourceObject], Snapshot, list[CompileError], list[SourceObject]]:
    """Compara con snapshot anterior y devuelve solo los objetos que cambiaron.

    Retorna (cambiados, snapshot_nuevo, skipped, deleted).
    La detección incremental usa SOLO content_sha256 (sin mtime).
    Si previous es None, escanea todo.

    NOTA: take_snapshot() NO se llama por separado; el snapshot
    se construye a partir de los resultados de scan_source()
    para evitar leer cada archivo dos veces.
    """
    current_sources, skipped = scan_source(source_dir)

    new_snapshot = Snapshot(
        sources=tuple(
            SourceObject(
                id=s.id,
                path=s.path,
                kind=s.kind,
                content_sha256=s.content_sha256,
                size=s.size,
                content=b"",
            )
            for s in current_sources
        ),
        taken_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )

    if previous is None:
        return current_sources, new_snapshot, skipped, []

    prev_map: dict[str, SourceObject] = {s.id: s for s in previous.sources}
    changed: list[SourceObject] = []
    for src in current_sources:
        prev = prev_map.get(src.id)
        if prev is None or prev.content_sha256 != src.content_sha256:
            changed.append(src)

    deleted = new_snapshot.deleted(previous)

    return changed, new_snapshot, skipped, deleted
