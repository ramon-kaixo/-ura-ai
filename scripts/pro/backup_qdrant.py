#!/usr/bin/env python3
"""Backup semanal de Qdrant: snapshot → descargar → verificar → limpiar viejos."""
import sys
import hashlib
import logging
from datetime import datetime
from pathlib import Path

import httpx

QDRANT = "http://127.0.0.1:6333"
BACKUP_DIR = Path.home() / ".nervioso" / "backups"
COLLECTION = "ideas"
KEEP_COPIES = 4

logging.basicConfig(level=logging.INFO, format="%(asctime)s [backup] %(message)s")
log = logging.getLogger()


def _api(method, path, json_data=None):
    r = httpx.request(method, f"{QDRANT}{path}", json=json_data, timeout=30)
    r.raise_for_status()
    return r.json()


def create_snapshot() -> dict:
    resp = _api("POST", f"/collections/{COLLECTION}/snapshots")
    return resp.get("result", resp)


def download_snapshot(snap_name: str, dest: Path) -> str:
    url = f"{QDRANT}/collections/{COLLECTION}/snapshots/{snap_name}"
    with httpx.stream("GET", url, timeout=300) as r:
        r.raise_for_status()
        sha = hashlib.sha256()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(65536):
                f.write(chunk)
                sha.update(chunk)
    return sha.hexdigest()


def clean_old_snapshots():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BACKUP_DIR.glob("qdrant_*.snapshot"))
    for f in files[:-KEEP_COPIES]:
        f.unlink()
        log.info(f"Deleted old: {f.name}")


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Creating snapshot...")
    snap = create_snapshot()
    snap_name = snap.get("name", "")

    if not snap_name:
        log.error("No snapshot name in response")
        return 1

    ts = datetime.now().strftime("%Y-%m-%d")
    dest = BACKUP_DIR / f"qdrant_{ts}.snapshot"

    log.info(f"Downloading {snap_name} → {dest}")
    sha = download_snapshot(snap_name, dest)

    size_mb = round(dest.stat().st_size / 1e6, 1)
    log.info(f"Downloaded {size_mb} MB, SHA256: {sha[:16]}...")

    clean_old_snapshots()

    # Verify: can we list snapshots?
    snaps = _api("GET", f"/collections/{COLLECTION}/snapshots")
    log.info(f"Snapshots on server: {len(snaps.get('result',[]))}")

    log.info("Backup complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
