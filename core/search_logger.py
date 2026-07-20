#!/usr/bin/env python3
"""search_logger.py — NDJSON query logging for search quality analysis.

Every query() call is logged as a JSON line:
  {"ts": "...", "query": "...", "results": [...], "latency_ms": N,
   "use_reranker": bool, "use_hybrid": bool, "threshold": float,
   "top_k": int, "total_chunks": int}
"""

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("ura.search_logger")

LOG_DIR = Path("/tmp/ura_search_logs")
_LOG_LOCK = threading.Lock()
_WRITER = None


class _NdjsonWriter:
    def __init__(self, log_dir: str | Path) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._path: Path | None = None

    def _ensure_file(self) -> None:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        path = self.log_dir / f"search_{date_str}.ndjson"
        if path != self._path:
            if self._file:
                self._file.close()
            self._file = open(path, "a", encoding="utf-8")  # noqa: PTH123, SIM115
            self._path = path

    def write(self, record: dict) -> None:
        self._ensure_file()
        line = json.dumps(record, ensure_ascii=False, default=str, sort_keys=True)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    def __del__(self) -> None:
        self.close()


def _get_writer() -> _NdjsonWriter:
    global _WRITER  # noqa: PLW0603
    if _WRITER is None:
        _WRITER = _NdjsonWriter(os.environ.get("URA_LOG_DIR", LOG_DIR))
    return _WRITER


def log_query(
    query_text: str,
    results: list[dict],
    latency_ms: float,
    *,
    use_reranker: bool = False,
    use_hybrid: bool = False,
    threshold: float = 0.7,
    top_k: int = 5,
) -> None:
    """Log a query with its results as a single NDJSON line."""
    try:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "query": query_text[:500],
            "num_results": len(results),
            "latency_ms": round(latency_ms, 1),
            "use_reranker": use_reranker,
            "use_hybrid": use_hybrid,
            "threshold": threshold,
            "top_k": top_k,
            "total_chunks": sum(r.get("total_chunks_meta", 0) or 0 for r in results),
            "sources": [r.get("source", "") for r in results],
            "similarities": [r.get("similarity", 0.0) for r in results],
            "idiomas": list({r.get("idioma", "") for r in results if r.get("idioma")}),
            "tipos": list({r.get("tipo_contenido", "") for r in results if r.get("tipo_contenido")}),
        }
        with _LOG_LOCK:
            _get_writer().write(record)
    except Exception as e:
        log.warning("Failed to log query: %s", e)


def read_logs(
    log_dir: str | Path | None = None,
    limit: int = 1000,
    since: str | None = None,
) -> list[dict]:
    """Read search logs, newest first.

    Args:
        log_dir: directory with .ndjson files (default: $URA_LOG_DIR or /tmp/ura_search_logs)
        limit: max records to return
        since: ISO timestamp filter (only records after this time)

    Returns:
        list of log records

    """
    log_dir = Path(log_dir) if log_dir else (Path(os.environ.get("URA_LOG_DIR", LOG_DIR)))
    if not log_dir.exists():
        return []

    records = []
    for f in sorted(log_dir.glob("search_*.ndjson"), reverse=True):
        try:
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()  # noqa: PLW2901
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if len(records) >= limit:
                        break
        except OSError:
            continue
        if len(records) >= limit:
            break

    if since:
        records = [r for r in records if r.get("ts", "") >= since]

    records.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return records[:limit]


def log_feedback(query_ts: str, query_text: str, clicked_sources: list[str], rating: int | None = None) -> None:
    """Log implicit/explicit feedback for a past query.

    Args:
        query_ts: ISO timestamp matching a logged query
        query_text: original query text
        clicked_sources: sources the user clicked/selected
        rating: explicit relevance rating (1-5) if available

    """
    try:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "type": "feedback",
            "query_ts": query_ts,
            "query": query_text[:500],
            "clicked_sources": clicked_sources,
            "rating": rating,
        }
        with _LOG_LOCK:
            _get_writer().write(record)
    except Exception as e:
        log.warning("Failed to log feedback: %s", e)
