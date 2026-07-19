#!/usr/bin/env python3
"""Meta Miner Remoto — Extracción determinista de metadatos de código.
Sin GPU, sin LLM, sin estado: puro os.walk + regex en frío.
Uso: meta_miner_remote.py /ruta/a/datos
Salida: JSON a /tmp/metadata_raw.json.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

EXTS = {".py", ".md", ".json", ".sh", ".yaml", ".yml", ".toml", ".cfg"}
IMPORT_RE = re.compile(r"^(?:import|from)\s+(\S+)", re.MULTILINE)
MAX_SUMMARY_CHARS = 500


def _hash_path(path: str) -> str:
    return hashlib.sha256(path.encode()).hexdigest()[:12]


def _extract_deps(text: str, ext: str) -> list[str]:
    if ext == ".py":
        return sorted(set(IMPORT_RE.findall(text)))
    if ext == ".md":
        refs = re.findall(r"\[.+?\]\((.+?)\)", text)
        return sorted(set(refs))
    if ext == ".json":
        return []
    if ext == ".sh":
        bins = re.findall(r"(?:^|\s)(\w+)(?=\s)", text)
        return sorted(
            {
                b
                for b in bins
                if b
                in {
                    "curl",
                    "wget",
                    "ssh",
                    "scp",
                    "docker",
                    "git",
                    "python3",
                    "systemctl",
                    "journalctl",
                    "chattr",
                    "grep",
                    "sed",
                    "awk",
                }
            },
        )
    return []


def _summarize(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:MAX_SUMMARY_CHARS]


def _guess_tags(path: str) -> list[str]:
    tags = []
    parts = Path(path).parts
    for p in parts:
        if p in ("scripts", "pro", "core", "tests", "docs", "config"):
            tags.append(p)
        if p.endswith(".service"):
            tags.append("systemd")
    if Path(path).suffix == ".py":
        tags.append("python")
    elif Path(path).suffix == ".sh":
        tags.append("bash")
    elif Path(path).suffix == ".md":
        tags.append("documentation")
    if "test" in str(Path(path).stem).lower():
        tags.append("test")
    return sorted(set(tags)) or ["generic"]


def scan(data_root: str) -> list[dict]:
    docs_dir = Path(data_root)
    if not docs_dir.exists():
        return []

    items = []
    for fpath in docs_dir.rglob("*"):
        if not fpath.is_file() or fpath.name.startswith("."):
            continue
        ext = fpath.suffix.lower()
        if ext not in EXTS:
            continue

        rel = str(fpath.relative_to(docs_dir))
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: S112
            continue

        items.append(
            {
                "path": str(fpath),
                "size_bytes": fpath.stat().st_size,
                "ext": ext,
                "tags": _guess_tags(rel),
                "dependencies": _extract_deps(text, ext),
                "content_summary": _summarize(text),
                "hash": _hash_path(rel),
            },
        )

    return items


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(1)

    data_root = sys.argv[1]
    items = scan(data_root)
    tmp_path = "/tmp/metadata_raw.json"  # noqa: S108
    with open(tmp_path, "w") as f:  # noqa: PTH123
        json.dump(items, f, indent=2, ensure_ascii=False)

    sys.exit(0)


if __name__ == "__main__":
    main()
