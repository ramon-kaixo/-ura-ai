#!/usr/bin/env python3
"""Trace Viewer (OBS-10) — generate HTML or JSON tree for a trace.

Usage:
    python3 scripts/trace-viewer.py --trace <trace_id> <trace_file> --html > trace.html
    python3 scripts/trace-viewer.py --trace <trace_id> <trace_file> --json
    python3 scripts/trace-viewer.py --list <trace_file>
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_events(path: str) -> list[dict]:
    events = []
    p = Path(path)
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


def build_tree(spans: list[dict]) -> dict[str, Any]:
    """Build a tree from flat spans list."""
    span_map = {s["span_id"]: s for s in spans}
    children: dict[str, list[dict]] = defaultdict(list)
    roots: list[dict] = []

    for s in spans:
        parent = s.get("parent_span_id", "")
        if parent and parent != "ROOT" and parent in span_map:
            children[parent].append(s)
        else:
            roots.append(s)

    def node(span: dict) -> dict:
        n: dict = {
            "span_id": span["span_id"],
            "parent_span_id": span.get("parent_span_id", ""),
            "source": span.get("source", "?"),
            "destination": span.get("destination", "?"),
            "message_type": span.get("message_type", "?"),
            "message_kind": span.get("message_kind", "?"),
            "duration_ms": span.get("duration_ns", 0) / 1_000_000,
            "error_code": span.get("error_code", ""),
            "error_message": span.get("error_message", ""),
            "timestamp_utc": span.get("timestamp_utc", 0),
            "children": [node(c) for c in children.get(span["span_id"], [])],
        }
        return n

    return {
        "roots": [node(r) for r in roots],
        "total_spans": len(spans),
        "total_errors": sum(1 for s in spans if s.get("error_code")),
    }


def render_html(tree: dict) -> str:
    """Render trace tree as a standalone HTML page."""
    error_count = tree["total_errors"]
    span_count = tree["total_spans"]

    def render_node(n: dict, depth: int = 0) -> str:
        indent = depth * 4
        cls = "error" if n["error_code"] else "ok"
        badge = f'<span class="badge error">❌ {n["error_code"]}</span>' if n["error_code"] else ""
        dur_class = "slow" if n["duration_ms"] > 100 else ""
        children_html = "".join(render_node(c, depth + 1) for c in n.get("children", []))

        return f'''<div class="node {cls}" style="margin-left:{indent}px">
  <div class="node-header">
    <span class="arrow" onclick="toggle(this)">▶</span>
    <span class="path">[{n["source"]}→{n["destination"]}]</span>
    <span class="type">{n["message_type"]}</span>
    <span class="kind">{n["message_kind"]}</span>
    <span class="duration {dur_class}">{n["duration_ms"]:.1f}ms</span>
    {badge}
  </div>
  {f'<div class="children">{children_html}</div>' if children_html else ''}
</div>'''

    roots_html = "".join(render_node(r) for r in tree["roots"])

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Trace Tree</title>
<style>
  body {{
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 13px;
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 20px;
  }}
  .node {{
    margin: 4px 0;
    padding: 4px 8px;
    border-left: 2px solid #333;
  }}
  .node-header {{
    display: flex;
    gap: 12px;
    align-items: center;
  }}
  .arrow {{
    cursor: pointer;
    color: #888;
    user-select: none;
    width: 16px;
  }}
  .children {{
    display: none;
    margin-top: 4px;
  }}
  .path {{
    color: #569cd6;
    min-width: 120px;
  }}
  .type {{
    color: #ce9178;
    min-width: 150px;
  }}
  .kind {{
    color: #6a9955;
    min-width: 80px;
  }}
  .duration {{
    color: #b5cea8;
    min-width: 70px;
    text-align: right;
  }}
  .slow {{
    color: #f44747;
    font-weight: bold;
  }}
  .badge {{
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 3px;
  }}
  .badge.error {{
    background: #5a1d1d;
    color: #f48771;
  }}
  .stats {{
    margin-bottom: 20px;
    padding: 10px;
    background: #252526;
    border-radius: 4px;
  }}
  .stats span {{
    margin-right: 20px;
  }}
</style>
</head>
<body>
<div class="stats">
  <span>Spans: <strong>{span_count}</strong></span>
  <span>Errors: <strong>{error_count}</strong></span>
</div>
<div id="tree">
{roots_html}
</div>
<script>
function toggle(el) {{
  const children = el.parentElement.nextElementSibling;
  if (children && children.classList.contains("children")) {{
    children.style.display = children.style.display === "block" ? "none" : "block";
    el.textContent = children.style.display === "block" ? "▼" : "▶";
  }}
}}
</script>
</body>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace Viewer (OBS-10)")
    parser.add_argument("file", help="JSONL trace file")
    parser.add_argument("--trace", help="Trace ID to visualize")
    parser.add_argument("--list", action="store_true", help="List all trace IDs")
    parser.add_argument("--json", action="store_true", help="Output JSON tree")
    parser.add_argument("--html", action="store_true", help="Output HTML page")

    args = parser.parse_args()

    events = load_events(args.file)
    if not events:
        print(f"No events in {args.file}", file=sys.stderr)
        sys.exit(1)

    if args.list:
        traces = sorted({e.get("trace_id", "") for e in events})
        for tid in traces:
            count = sum(1 for e in events if e.get("trace_id") == tid)
            print(f"{tid}  ({count} spans)")
        return

    if not args.trace:
        print("Use --trace <id> or --list", file=sys.stderr)
        sys.exit(1)

    spans = [e for e in events if e.get("trace_id") == args.trace]
    if not spans:
        print(f"Trace not found: {args.trace}", file=sys.stderr)
        sys.exit(1)

    tree = build_tree(spans)

    if args.json:
        json.dump(tree, sys.stdout, indent=2)
    elif args.html:
        print(render_html(tree))
    else:
        json.dump(tree, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
