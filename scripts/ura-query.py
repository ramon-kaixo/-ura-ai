#!/usr/bin/env python3
"""ura-query.py — CLI para analizar datos del sistema URA.

Uso:
    --stats                    → promedios de telemetría
    --anomalies                → latencia > 3ms en telemetría
    --search <query>           → búsqueda full-text en analytics.db
    --suggest <prefix>         → autocompletado de métricas
    --date YYYY-MM-DD          → filtrar por fecha (solo --stats)
"""

import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
TELEMETRY_DIR = REPO_DIR / "logs" / "telemetry"
if not TELEMETRY_DIR.exists():
    TELEMETRY_DIR = Path("/home/ramon/URA/logs/telemetry")

GREEN = "\033[92m"; YELLOW = "\033[93m"; RED = "\033[91m"; BOLD = "\033[1m"; END = "\033[0m"


def _load_telemetry(date=None):
    if not TELEMETRY_DIR.exists():
        print(f"{RED}No existe {TELEMETRY_DIR}{END}"); sys.exit(1)
    recs = []
    for f in sorted(TELEMETRY_DIR.glob("*.jsonl")):
        if date and date not in f.stem: continue
        for line in f.read_text().strip().split("\n"):
            try: recs.append(json.loads(line.strip()))
            except: pass
    return recs


def cmd_stats(recs):
    if not recs: print(f"{YELLOW}No hay datos.{END}"); return
    lats = [r.get("latency_ms",-1) for r in recs if r.get("latency_ms",-1)>=0]
    cpus = [r.get("cpu_pct",-1) for r in recs if r.get("cpu_pct",-1)>=0]
    mems = [r.get("mem_pct",-1) for r in recs if r.get("mem_pct",-1)>=0]
    mc = Counter(r.get("mode","?") for r in recs)
    print(f"\n{BOLD}TELEMETRÍA — ESTADÍSTICAS{END}")
    print(f"  Snapshots: {len(recs)}")
    if lats: print(f"  Latencia:  avg={statistics.mean(lats):.1f}ms  max={max(lats):.1f}ms")
    if cpus: print(f"  CPU:       avg={statistics.mean(cpus):.1f}%  max={max(cpus):.1f}%")
    if mems: print(f"  Memoria:   avg={statistics.mean(mems):.1f}%")
    for m,c in mc.most_common(): print(f"  {m:8s} → {c} snaps")
    print()


def cmd_anomalies(recs):
    anom = [r for r in recs if r.get("latency_ms",-1) > 3.0]
    if not anom:
        print(f"{GREEN}✅ Sin anomalías (>3ms) en telemetría{END}")
    else:
        print(f"\n{BOLD}ANOMALÍAS TELEMETRÍA (>3ms): {len(anom)}{END}")
        for r in anom: print(f"  {YELLOW}⚠{END}  {r.get('ts','?')}  lat={RED}{r.get('latency_ms')}ms{END}  mode={r.get('mode','?')}")

    # También revisar analytics.db
    try:
        sys.path.insert(0, str(REPO_DIR))
        from core.search_engine import search
        results = search("latency", limit=10)
        analytics_anom = [r for r in results if r.get("metric_value", 0) > 3.0]
        if analytics_anom:
            print(f"\n{BOLD}ANOMALÍAS ANALYTICS DB: {len(analytics_anom)}{END}")
            for r in analytics_anom[:5]:
                print(f"  {YELLOW}⚠{END}  {r['source']}  {r['metric_name']}={RED}{r['metric_value']}{END}")
    except Exception as e:
        print(f"  analytics db: {e}")
    print()


def cmd_search(query):
    sys.path.insert(0, str(REPO_DIR))
    from core.search_engine import search, get_suggestions
    results = search(query, limit=30)
    if not results:
        print(f"{YELLOW}Sin resultados para '{query}'{END}")
        sug = get_suggestions(query)
        if sug: print(f"  Sugerencias: {', '.join(sug)}")
        return
    print(f"\n{BOLD}BÚSQUEDA: '{query}' — {len(results)} resultados{END}\n")
    for r in results:
        print(f"  #{r['id']:3d}  {r['source']:20s}  {r['metric_name']:15s}  "
              f"val={r['metric_value']:>10.2f}  mov_avg={r['moving_avg']:>10.2f}  "
              f"cnt={r['records_count']}  {r['ts'][:19]}")


def cmd_suggest(prefix):
    sys.path.insert(0, str(REPO_DIR))
    from core.search_engine import get_suggestions
    results = get_suggestions(prefix)
    if results:
        print(f"\n{BOLD}Sugerencias para '{prefix}':{END}")
        for r in results: print(f"  {r}")
    else:
        print(f"{YELLOW}Sin sugerencias para '{prefix}'{END}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "--help"):
        print(__doc__); sys.exit(0)

    date = sys.argv[sys.argv.index("--date")+1] if "--date" in sys.argv else None

    if "--search" in sys.argv:
        q = sys.argv[sys.argv.index("--search")+1]
        cmd_search(q)
    elif "--suggest" in sys.argv:
        p = sys.argv[sys.argv.index("--suggest")+1]
        cmd_suggest(p)
    elif "--anomalies" in sys.argv or "-a" in sys.argv:
        cmd_anomalies(_load_telemetry(date))
    elif "--stats" in sys.argv or "-s" in sys.argv:
        cmd_stats(_load_telemetry(date))
    else:
        print(__doc__)
