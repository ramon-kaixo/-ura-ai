#!/usr/bin/env python3
"""Auto-mantenimiento: degrada fragmentos inefectivos, refuerza efectivos."""

import json
from pathlib import Path

KNOWLEDGE_DIR = Path(os.environ.get("KNOWLEDGE_DIR", Path.home() / "URA/ura_ia_1972/knowledge"))
EFFECTIVENESS = {"effective": 1.0, "settled": 0.7, "unmatched": 0.4, "ineffective": 0.1}

for frag_path in sorted(KNOWLEDGE_DIR.glob("fragmentos/*.json")):
    with open(frag_path) as f:
        data = json.load(f)
    changed = False
    for chunk in data.get("chunks", []):
        level = chunk.get("effectiveness", "settled")
        score = EFFECTIVENESS.get(level, 0.5)
        if score < 0.2:
            chunk["quarantine"] = True
            changed = True
        elif score >= 0.7:
            chunk["reinforced"] = True
            changed = True
    if changed:
        with open(frag_path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"🔄 {frag_path.name}: mantenimiento aplicado")
print("✅ Auto-mantenimiento completado")
