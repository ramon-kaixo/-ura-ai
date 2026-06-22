#!/usr/bin/env python3
"""transfer.py — Export/import scraped document batches as tar.gz.

Format:
  ura_batch_<timestamp>.tar.gz
  ├── manifest.json       # metadata (count, timestamp, source_urls)
  ├── key.txt             # SHA-256 of manifest
  └── documents/
      ├── 0001.json       # {url, text, metadata, chunks}
      ├── 0002.json
      └── ...
"""

import hashlib
import io
import json
import logging
import tarfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("ura.transfer")

BATCH_DIR = Path("/tmp/ura_batches")


def _doc_id(doc: dict) -> str:
    return hashlib.sha256((doc.get("url", "") + doc.get("text", "")[:100]).encode()).hexdigest()[:12]


def export_batch(
    documents: list[dict],
    output_path: str | Path | None = None,
    compress: bool = True,
) -> Path:
    """Export scraped documents as a tar.gz archive.

    Each document dict must have at least:
      - url: source URL
      - text: scraped text content
    Optional: metadata dict with source, indexed_at, idioma, fiabilidad, etc.

    Args:
        documents: list of document dicts
        output_path: output file or directory (auto-named if None/directory)
        compress: whether to gzip (default True)

    Returns:
        Path to the created archive

    """
    if not documents:
        msg = "No documents to export"
        raise ValueError(msg)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    ext = ".tar.gz" if compress else ".tar"
    basename = f"ura_batch_{timestamp}{ext}"

    if output_path is None:
        BATCH_DIR.mkdir(parents=True, exist_ok=True)
        output_path = BATCH_DIR / basename
    else:
        output_path = Path(output_path)
        # If path doesn't exist, check if parent is a dir (user probably meant directory)
        if not output_path.suffix:
            output_path.mkdir(parents=True, exist_ok=True)
            output_path = output_path / basename
        elif output_path.is_dir():
            output_path = output_path / basename

    output_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "exported_at": datetime.now(UTC).isoformat(),
        "count": len(documents),
        "source_urls": [d.get("url", "") for d in documents],
        "version": 1,
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode()
    key = hashlib.sha256(manifest_bytes).hexdigest()

    mode = "w:gz" if compress else "w"
    with tarfile.open(output_path, mode) as tar:
        # manifest
        m_info = tarfile.TarInfo(name="manifest.json")
        m_info.size = len(manifest_bytes)
        tar.addfile(m_info, io.BytesIO(manifest_bytes))

        # key
        key_bytes = key.encode()
        k_info = tarfile.TarInfo(name="key.txt")
        k_info.size = len(key_bytes)
        tar.addfile(k_info, io.BytesIO(key_bytes))

        # documents
        for i, doc in enumerate(documents):
            entry = {
                "url": doc.get("url", ""),
                "text": doc.get("text", ""),
                "metadata": doc.get("metadata", {}),
                "id": _doc_id(doc),
            }
            doc_bytes = json.dumps(entry, indent=2, sort_keys=True).encode()
            d_info = tarfile.TarInfo(name=f"documents/{i:04d}.json")
            d_info.size = len(doc_bytes)
            tar.addfile(d_info, io.BytesIO(doc_bytes))

    log.info("Exported %d documents to %s (key=%s)", len(documents), output_path, key[:16])
    return output_path


def import_batch(tarball: str | Path) -> Iterator[dict]:
    """Yield documents from a tar.gz batch archive.

    Each yielded dict has keys: url, text, metadata, id.

    Args:
        tarball: path to .tar.gz file

    Yields:
        document dicts

    """
    tarball = Path(tarball)
    if not tarball.exists():
        msg = f"Batch not found: {tarball}"
        raise FileNotFoundError(msg)

    with tarfile.open(tarball, "r:gz") as tar:
        manifest_data = None
        try:
            mf = tar.extractfile("manifest.json")
            if mf:
                manifest_data = json.loads(mf.read())
        except (KeyError, json.JSONDecodeError) as e:
            log.warning("No valid manifest in %s: %s", tarball, e)

        if manifest_data:
            log.info(
                "Importing batch: %d docs, exported %s",
                manifest_data.get("count", "?"),
                manifest_data.get("exported_at", "?"),
            )

        members = sorted(
            (m for m in tar.getmembers() if m.name.startswith("documents/") and m.name.endswith(".json")),
            key=lambda m: m.name,
        )
        for m in members:
            try:
                f = tar.extractfile(m)
                if f:
                    doc = json.loads(f.read())
                    yield doc
            except (json.JSONDecodeError, KeyError) as e:
                log.warning("Skipping corrupt doc %s: %s", m.name, e)


def verify_batch(tarball: str | Path) -> bool:
    """Verify integrity of a batch archive.

    Checks SHA-256 of manifest against key.txt.

    Args:
        tarball: path to .tar.gz file

    Returns:
        True if valid, False otherwise

    """
    tarball = Path(tarball)
    if not tarball.exists():
        return False
    try:
        with tarfile.open(tarball, "r:gz") as tar:
            try:
                mf = tar.extractfile("manifest.json")
                kf = tar.extractfile("key.txt")
                if not mf or not kf:
                    return False
                manifest_bytes = mf.read()
                stored_key = kf.read().decode().strip()
                computed_key = hashlib.sha256(manifest_bytes).hexdigest()
                return computed_key == stored_key
            except (KeyError, json.JSONDecodeError):
                return False
    except (tarfile.TarError, OSError):
        return False


def list_batches(batch_dir: str | Path | None = None) -> list[Path]:
    """List all batch archives in a directory.

    Args:
        batch_dir: directory to scan (default: /tmp/ura_batches)

    Returns:
        sorted list of batch paths (newest first)

    """
    batch_dir = Path(batch_dir) if batch_dir else BATCH_DIR
    if not batch_dir.exists():
        return []
    return sorted(batch_dir.glob("ura_batch_*.tar.gz"), reverse=True)


def cleanup_batches(keep: int = 10, batch_dir: str | Path | None = None) -> int:
    """Remove old batch archives, keeping the N most recent.

    Args:
        keep: number of most recent batches to keep
        batch_dir: directory to clean

    Returns:
        number of deleted files

    """
    batch_dir = Path(batch_dir) if batch_dir else BATCH_DIR
    if not batch_dir.exists():
        return 0
    batches = list_batches(batch_dir)
    if len(batches) <= keep:
        return 0
    deleted = 0
    for b in batches[keep:]:
        try:
            b.unlink()
            deleted += 1
        except OSError as e:
            log.warning("Could not delete %s: %s", b, e)
    if deleted:
        log.info("Cleaned %d old batches from %s", deleted, batch_dir)
    return deleted
