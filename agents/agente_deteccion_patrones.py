#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict


def detect_breakage_patterns():
    patterns = []
    scribe_log = Path.home() / ".ura" / "scribe_log.json"
    if not scribe_log.exists():
        return patterns
    with open(scribe_log) as f:
        events = json.load(f)
    windows = defaultdict(list)
    for e in events:
        ts = e.get("timestamp", "")
        if ts:
            hour = ts[:13]
            windows[hour].append(e)
    for hour, evts in windows.items():
        upgrades = [e for e in evts if "upgrade" in e.get("type", "").lower()]
        failures = [e for e in evts if "failure" in e.get("type", "").lower()]
        if upgrades and failures:
            for upg in upgrades:
                for fail in failures:
                    patterns.append(
                        {
                            "pattern": f"Actualización de {upg.get('module', '?')} → fallo en {fail.get('module', '?')}",
                            "upgrade": upg,
                            "failure": fail,
                            "timestamp": hour,
                        }
                    )
    return patterns


if __name__ == "__main__":
    patterns = detect_breakage_patterns()
    if patterns:
        print(f"🔍 {len(patterns)} patrones detectados:")
        for p in patterns:
            print(f"  ⚠️  {p['pattern']}")
    else:
        print("✅ Sin patrones de rotura detectados")
