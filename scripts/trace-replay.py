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
            with open(f) as fh:
                for line in fh:
                    line = line.strip()
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
        traces[tid]["sources"].add(f"{ev.get('source','?')}→{ev.get('destination','?')}")
        if ev.get("error_code"):
            traces[tid]["errors"] += 1

    print(f"{'Trace ID':<40} {'Spans':>6} {'Errors':>6}  Path")
    print("-" * 80)
    for tid, info in sorted(traces.items()):
        path = ", ".join(sorted(info["sources"]))
        print(f"{tid:<40} {info['count']:>6} {info['errors']:>6}  {path}")


def replay_trace(events: list[dict], trace_id: str) -> None:
    """Reconstruct the full path for a single trace."""
    spans = [ev for ev in events if ev.get("trace_id") == trace_id]
    if not spans:
        print(f"No events found for trace_id: {trace_id}")
        return

    # Build tree
    {ev["span_id"]: ev for ev in spans}
    children: dict[str, list[dict]] = defaultdict(list)

    for ev in spans:
        parent = ev.get("parent_span_id", "")
        if parent and parent not in {"ROOT", ""}:
            children[parent].append(ev)

    # Find root spans
    roots = [ev for ev in spans if ev.get("parent_span_id", "") == "ROOT" or ev.get("parent_span_id", "") == "" or ev.get("span_id") not in {e.get("parent_span_id", "") for e in spans}]

    def print_span(ev: dict, depth: int = 0, prefix: str = "") -> None:
        indent = "  " * depth
        duration_ms = ev.get("duration_ns", 0) / 1_000_000
        error = f" ❌ {ev.get('error_code','')}: {ev.get('error_message','')}" if ev.get("error_code") else ""
        src = ev.get("source", "?")
        dst = ev.get("destination", "?")
        mt = ev.get("message_type", "?")
        mk = ev.get("message_kind", "?")
        print(f"{indent}{prefix} [{src}→{dst}] {mt} ({mk}) {duration_ms:.1f}ms{error}")

        for child in children.get(ev["span_id"], []):
            print_span(child, depth + 1, "└─ ")

    if not roots:
        # Use all spans sorted by timestamp
        roots = sorted(spans, key=lambda e: e.get("timestamp_utc", 0))

    print(f"\nTrace: {trace_id}")
    print(f"Spans: {len(spans)}")
    print("=" * 60)
    for root in roots[:1]:  # Just the first root
        print_span(root)


def summary(events: list[dict]) -> None:
    """Aggregate statistics across all traces."""
    total_spans = len(events)
    total_errors = sum(1 for ev in events if ev.get("error_code"))
    trace_ids = {ev.get("trace_id", "") for ev in events}
    total_duration = sum(ev.get("duration_ns", 0) for ev in events)

    # Per subsystem pair
    pairs: dict[str, dict] = {}
    for ev in events:
        pair = f"{ev.get('source','?')}→{ev.get('destination','?')}"
        if pair not in pairs:
            pairs[pair] = {"count": 0, "errors": 0, "total_duration_ns": 0}
        pairs[pair]["count"] += 1
        if ev.get("error_code"):
            pairs[pair]["errors"] += 1
        pairs[pair]["total_duration_ns"] += ev.get("duration_ns", 0)

    print("\nTrace Summary")
    print(f"{'Total traces':<30} {len(trace_ids)}")
    print(f"{'Total spans':<30} {total_spans}")
    print(f"{'Total errors':<30} {total_errors}")
    print(f"{'Error rate':<30} {total_errors/max(total_spans,1)*100:.1f}%")
    print(f"{'Total duration (ms)':<30} {total_duration/1_000_000:.1f}")
    print()
    print(f"{'Subsystem':<30} {'Spans':>8} {'Errors':>8} {'Avg ms':>8}")
    print("-" * 60)
    for pair, info in sorted(pairs.items()):
        avg_ms = info["total_duration_ns"] / max(info["count"], 1) / 1_000_000
        print(f"{pair:<30} {info['count']:>8} {info['errors']:>8} {avg_ms:>8.1f}")


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
        print(f"No events found in {args.file}")
        sys.exit(1)

    if args.list:
        list_traces(events)
    elif args.summary:
        summary(events)
    elif args.trace:
        replay_trace(events, args.trace)


if __name__ == "__main__":
    main()
