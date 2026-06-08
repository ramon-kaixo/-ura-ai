#!/usr/bin/env python3
"""detectar_patrones.py — Lee historicos JSONL y detecta patrones."""
import json, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from memoria_fallos import MemoriaFallos

mem = MemoriaFallos("sistema")
hist_paths = list(Path("mantenimiento").glob("historico_*.jsonl"))

if not hist_paths:
    print("[] — No hay historicos")
    sys.exit(0)

for hp in hist_paths:
    content = hp.read_text().strip()
    if not content:
        continue
    for line in content.splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            if not e.get("reparado", True):
                mem.registrar(e.get("error", "UNKNOWN"), e.get("detalle", str(e)))
        except json.JSONDecodeError:
            continue

patrones = []
for f in mem.fallos_recientes():
    if mem.es_patron(f.tipo):
        patrones.append({
            "error": f.tipo,
            "repeticiones": mem.contar(f.tipo),
            "ultimo": f.timestamp,
            "arreglo": mem.arreglo_conocido(f.tipo)
        })

output = {
    "total_fallos": len(mem.fallos_recientes()),
    "patrones": patrones,
    "fecha": datetime.now().isoformat()
}

Path("/tmp/informe_patrones_mensual.json").write_text(json.dumps(output, indent=2, ensure_ascii=False))
print(json.dumps(output, indent=2, ensure_ascii=False))
