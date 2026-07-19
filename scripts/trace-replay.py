#!/usr/bin/env python3
"""Trace Replay — reconstruye el recorrido completo de un trace_id (OBS-4).

Usage:
    python3 scripts/trace-replay.py --trace <trace_id> <trace_file>
    python3 scripts/trace-replay.py --list <trace_file>  # list all trace IDs
    python3 scripts/trace-replay.py --summary <trace_file>  # aggregate stats

Reads JSONL files produced by TraceExporter (motor/platform/tracing.py).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_events(path: str) -> list[dict]:
    """Load all span events from a JSONL file."""
    events = []
    p = Path(path)
    # Load rotated files
    files = sorted(p.parent.glob(f"{p.stem}*{p.suffix}"))
    if not files:
        files = [p]

    for f in files:
        if f.exists():
            with open(f) as fh:  # noqa: PTH123
                for line in fh:
                    line = line.strip()  # noqa: PLW2901
                    if line:
                        with contextlib.suppress(json.JSONDecodeError):
                            events.append(json.loads(line))
    return events


def list_traces(events: list[dict]) -> None:
    """List all unique trace IDs with span count and time range."""
    traces: dict[str, dict] = {}
    for ev in events:
        tid = ev.get("trace_id", "unknown")
        ts = ev.get("timestamp_utc", 0)
        if tid not in traces:
            traces[tid] = {"count": 0, "first": ts, "last": ts, "sources": set(), "errors": 0}
        traces[tid]["count"] += 1
        traces[tid]["first"] = min(traces[tid]["first"], ts)
        traces[tid]["last"] = max(traces[tid]["last"], ts)
        traces[tid]["sources"].add(f"{ev.get('source', '?')}→{ev.get('destination', '?')}")
        if ev.get("error_code"):
            traces[tid]["errors"] += 1

    for tid, info in sorted(traces.items()):  # noqa: B007
        ", ".join(sorted(info["sources"]))


def replay_trace(events: list[dict], trace_id: str) -> None:
    """Reconstruct the full path for a single trace."""
    spans = [ev for ev in events if ev.get("trace_id") == trace_id]
    if not spans:
        return

    # Build tree
    {ev["span_id"]: ev for ev in spans}
    children: dict[str, list[dict]] = defaultdict(list)

    for ev in spans:
        parent = ev.get("parent_span_id", "")
        if parent and parent not in {"ROOT", ""}:
            children[parent].append(ev)

    # Find root spans
    roots = [
        ev
        for ev in spans
        if ev.get("parent_span_id", "") == "ROOT"
        or ev.get("parent_span_id", "") == ""
        or ev.get("span_id") not in {e.get("parent_span_id", "") for e in spans}
    ]

    def print_span(ev: dict, depth: int = 0, prefix: str = "") -> None:
        "  " * depth
        ev.get("duration_ns", 0) / 1_000_000
        f" ❌ {ev.get('error_code', '')}: {ev.get('error_message', '')}" if ev.get("error_code") else ""
        ev.get("source", "?")
        ev.get("destination", "?")
        ev.get("message_type", "?")
        ev.get("message_kind", "?")

        for child in children.get(ev["span_id"], []):
            print_span(child, depth + 1, "└─ ")

    if not roots:
        # Use all spans sorted by timestamp
        roots = sorted(spans, key=lambda e: e.get("timestamp_utc", 0))

    for root in roots[:1]:  # Just the first root
        print_span(root)


def summary(events: list[dict]) -> None:
    """Aggregate statistics across all traces."""
    len(events)
    sum(1 for ev in events if ev.get("error_code"))
    {ev.get("trace_id", "") for ev in events}
    sum(ev.get("duration_ns", 0) for ev in events)

    # Per subsystem pair
    pairs: dict[str, dict] = {}
    for ev in events:
        pair = f"{ev.get('source', '?')}→{ev.get('destination', '?')}"
        if pair not in pairs:
            pairs[pair] = {"count": 0, "errors": 0, "total_duration_ns": 0}
        pairs[pair]["count"] += 1
        if ev.get("error_code"):
            pairs[pair]["errors"] += 1
        pairs[pair]["total_duration_ns"] += ev.get("duration_ns", 0)

    for pair, info in sorted(pairs.items()):  # noqa: B007
        info["total_duration_ns"] / max(info["count"], 1) / 1_000_000


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace Replay (OBS-4)")
    parser.add_argument("file", help="JSONL trace file (or base name for rotated files)")
    parser.add_argument("--trace", help="Trace ID to replay")
    parser.add_argument("--list", action="store_true", help="List all trace IDs")
    parser.add_argument("--summary", action="store_true", help="Aggregate statistics")

    args = parser.parse_args()

    if not [x for x in [args.trace, args.list, args.summary] if x]:
        parser.print_help()
        sys.exit(0)

    events = load_events(args.file)
    if not events:
        sys.exit(1)

    if args.list:
        list_traces(events)
    elif args.summary:
        summary(events)
    elif args.trace:
        replay_trace(events, args.trace)


if __name__ == "__main__":
    main()
