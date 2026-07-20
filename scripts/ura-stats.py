#!/usr/bin/env python3
"""ura-stats.py — Metricas del Guardian Post-Inferencia.

Uso:
  python3 ura-stats.py --last 24h
  python3 ura-stats.py --last 7d  --json
  python3 ura-stats.py --tail 50
  python3 ura-stats.py --drift
  python3 ura-stats.py --injection-report
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

GUARDIAN_LOG = os.getenv("GUARDIAN_LOG", "/var/log/ura/guardian.jsonl")


def parse_duration(s: str) -> timedelta:
    s = s.strip().lower()
    if s.endswith("h"):
        return timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=int(s[:-1]))
    if s.endswith("m"):
        return timedelta(minutes=int(s[:-1]))
    msg = f"Formato invalido: {s}. Usa ej: 24h, 7d, 30m"
    raise ValueError(msg)


def load_events(since: datetime | None = None, tail: int | None = None) -> list[dict]:
    if not Path(GUARDIAN_LOG).exists():
        sys.exit(1)

    events = []
    with open(GUARDIAN_LOG) as f:  # noqa: PTH123
        lines = f.readlines()[-tail:] if tail else f.readlines()

    for line in lines:
        line = line.strip()  # noqa: PLW2901
        if not line:
            continue
        try:
            ev = json.loads(line)
            if since:
                ts = datetime.fromisoformat(ev["timestamp"])
                if ts < since:
                    continue
            events.append(ev)
        except (json.JSONDecodeError, KeyError):
            continue
    return events


def print_drift(events: list[dict]) -> None:
    by_model = defaultdict(lambda: {"complexities": [], "results": []})
    for e in events:
        model = e.get("model", "unknown")
        cpx = e.get("complexity", 0)
        if cpx:
            by_model[model]["complexities"].append(cpx)
        rtype = e.get("result_type", "")
        if rtype:
            by_model[model]["results"].append(1 if rtype == "success" else 0)

    for model, data in sorted(by_model.items()):  # noqa: B007
        sum(data["complexities"]) / len(data["complexities"]) if data["complexities"] else 0
        sum(data["results"]) / len(data["results"]) * 100 if data["results"] else 0


def print_injection_report(events: list[dict]) -> None:
    injections = [e for e in events if e.get("event") == "injection_blocked"]
    if not injections:
        return

    by_model = Counter(e.get("model", "unknown") for e in injections)
    by_file = Counter(e.get("file", "unknown") for e in injections)

    for _model, _count in by_model.most_common(5):
        pass
    for _file, _count in by_file.most_common(5):
        pass


def print_stats(events: list[dict], json_output: bool = False) -> None:
    total = len(events)
    if total == 0:
        return

    [e for e in events if e.get("event") == "stream_aborted"]
    [e for e in events if e.get("event") == "syntax_reject"]
    [e for e in events if e.get("event") == "sandbox_reject"]
    [e for e in events if e.get("event") == "injection_blocked"]
    commits = [e for e in events if e.get("event") == "commit"]
    (len(commits) / total * 100) if total else 0
    sum(e.get("attempts", 1) for e in events) / total if total else 0
    sum(e.get("complexity", 0) for e in events) / total if total else 0
    model_counter = Counter(e.get("model", "unknown") for e in events)
    top_models = model_counter.most_common(5)

    if json_output:
        return

    for _model, _count in top_models:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Metricas del Guardian Post-Inferencia")
    parser.add_argument("--last", type=str, help="Periodo: 24h, 7d, 30m")
    parser.add_argument("--tail", type=int, help="Ultimas N lineas")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--drift", action="store_true", help="Tendencia complexity vs success rate")
    parser.add_argument("--injection-report", action="store_true", help="Intentos de inyeccion bloqueados")
    args = parser.parse_args()

    since = None
    tail = None
    if args.last:
        since = datetime.now(UTC) - parse_duration(args.last)
    if args.tail:
        tail = args.tail

    events = load_events(since=since, tail=tail)

    if args.drift:
        print_drift(events)
    elif args.injection_report:
        print_injection_report(events)
    else:
        print_stats(events, json_output=args.json)


if __name__ == "__main__":
    main()
