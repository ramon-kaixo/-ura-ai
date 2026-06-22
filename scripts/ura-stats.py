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
from datetime import datetime, timedelta, timezone

GUARDIAN_LOG = os.getenv("GUARDIAN_LOG", "/var/log/ura/guardian.jsonl")


def parse_duration(s: str) -> timedelta:
    s = s.strip().lower()
    if s.endswith("h"):
        return timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=int(s[:-1]))
    if s.endswith("m"):
        return timedelta(minutes=int(s[:-1]))
    raise ValueError(f"Formato invalido: {s}. Usa ej: 24h, 7d, 30m")


def load_events(since: datetime | None = None, tail: int | None = None) -> list[dict]:
    if not os.path.exists(GUARDIAN_LOG):
        print(f"No se encuentra {GUARDIAN_LOG}", file=sys.stderr)
        sys.exit(1)

    events = []
    with open(GUARDIAN_LOG) as f:
        lines = f.readlines()[-tail:] if tail else f.readlines()

    for line in lines:
        line = line.strip()
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


def print_drift(events: list[dict]):
    by_model = defaultdict(lambda: {"complexities": [], "results": []})
    for e in events:
        model = e.get("model", "unknown")
        cpx = e.get("complexity", 0)
        if cpx:
            by_model[model]["complexities"].append(cpx)
        rtype = e.get("result_type", "")
        if rtype:
            by_model[model]["results"].append(1 if rtype == "success" else 0)

    print(f"{'='*60}")
    print("  DRIFT REPORT — Complejidad vs Tasa de exito por modelo")
    print(f"{'='*60}")
    for model, data in sorted(by_model.items()):
        avg_cpx = sum(data["complexities"]) / len(data["complexities"]) if data["complexities"] else 0
        rate = sum(data["results"]) / len(data["results"]) * 100 if data["results"] else 0
        print(f"  {model:<35s} avg_complexity={avg_cpx:<5.1f}  success_rate={rate:>5.1f}%")
    print(f"{'='*60}")


def print_injection_report(events: list[dict]):
    injections = [e for e in events if e.get("event") == "injection_blocked"]
    if not injections:
        print("No hay eventos de inyeccion bloqueada en el periodo.")
        return

    by_model = Counter(e.get("model", "unknown") for e in injections)
    by_file = Counter(e.get("file", "unknown") for e in injections)

    print(f"{'='*60}")
    print("  INJECTION REPORT — Intentos bloqueados por filtro AST")
    print(f"{'='*60}")
    print(f"  Total bloqueos: {len(injections)}")
    print()
    print("  Por modelo:")
    for model, count in by_model.most_common(5):
        print(f"    {model:<40s} {count:>4d}")
    print()
    print("  Por archivo:")
    for file, count in by_file.most_common(5):
        print(f"    {file:<40s} {count:>4d}")
    print(f"{'='*60}")


def print_stats(events: list[dict], json_output: bool = False):
    total = len(events)
    if total == 0:
        print("No hay eventos en el periodo.")
        return

    vagancy = [e for e in events if e.get("event") == "stream_aborted"]
    syntax_fails = [e for e in events if e.get("event") == "syntax_reject"]
    sandbox_fails = [e for e in events if e.get("event") == "sandbox_reject"]
    injections = [e for e in events if e.get("event") == "injection_blocked"]
    commits = [e for e in events if e.get("event") == "commit"]
    success_rate = (len(commits) / total * 100) if total else 0
    avg_attempts = sum(e.get("attempts", 1) for e in events) / total if total else 0
    avg_complexity = sum(e.get("complexity", 0) for e in events) / total if total else 0
    model_counter = Counter(e.get("model", "unknown") for e in events)
    top_models = model_counter.most_common(5)

    if json_output:
        print(json.dumps({
            "total": total,
            "vagancy_cuts": len(vagancy),
            "syntax_fails": len(syntax_fails),
            "sandbox_fails": len(sandbox_fails),
            "injection_blocks": len(injections),
            "commits": len(commits),
            "success_rate_pct": round(success_rate, 1),
            "avg_attempts": round(avg_attempts, 2),
            "avg_complexity": round(avg_complexity, 1),
            "top_models": [{"model": m, "count": c} for m, c in top_models],
        }, indent=2))
        return

    print(f"{'='*50}")
    print(f"  GUARDIAN STATS  —  {total} eventos totales")
    print(f"{'='*50}")
    print(f"  Tasa de exito:          {success_rate:.1f}%")
    print(f"  Cortes por vagancia:    {len(vagancy)}")
    print(f"  Rechazos sintaxis:      {len(syntax_fails)}")
    print(f"  Rechazos sandbox:       {len(sandbox_fails)}")
    print(f"  Bloqueos inyeccion:     {len(injections)}")
    print(f"  Commits exitosos:       {len(commits)}")
    print(f"  Promedio intentos/task: {avg_attempts:.2f}")
    print(f"  Complejidad promedio:   {avg_complexity:.1f}")
    print()
    print("  Modelos con mas cortes:")
    for model, count in top_models:
        print(f"    {model:<40s} {count:>4d}")
    print(f"{'='*50}")


def main():
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
        since = datetime.now(timezone.utc) - parse_duration(args.last)
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
