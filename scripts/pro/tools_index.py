#!/usr/bin/env python3
"""tools_index.py — Genera índice de todas las herramientas ejecutables del repo."""

import re
from collections import defaultdict
from pathlib import Path

BASE = Path("/home/ramon/URA/ura_ia_1972")
EXCLUDES = {".git", "build", ".venv", ".sandbox_packages", "__pycache__", ".pytest_cache", ".tuneladora", ".nervioso", ".attic"}

def is_executable(f: Path) -> bool:
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if text.startswith("#!/usr/bin/env python"):
            return True
        if '__name__ == "__main__"' in text or "__name__=='__main__'" in text:
            return True
        return False
    except Exception:
        return False

def extract_docstring(f: Path) -> str:
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'"""(.*?)"""', text, re.DOTALL)
        if m:
            doc = m.group(1).strip().split("\n")[0].strip()
            if doc:
                return doc
        for line in text.split("\n")[:10]:
            line = line.strip()
            if line.startswith("#") and not line.startswith("#!/"):
                return line.lstrip("#").strip()
        return "(sin descripción)"
    except Exception:
        return "(error leyendo archivo)"

def extract_usage(f: Path) -> str:
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
        for line in text.split("\n")[:30]:
            if "python3" in line and (".py" in line or "Usage" in line or "usage" in line):
                return line.strip().lstrip("#").strip()
        return ""
    except Exception:
        return ""

tools = []
for f in sorted(BASE.rglob("*.py")):
    if any(x in str(f) for x in EXCLUDES):
        continue
    if not is_executable(f):
        continue
    rel = f.relative_to(BASE)
    tools.append({"path": str(rel), "name": f.stem, "doc": extract_docstring(f), "usage": extract_usage(f)})

md = f"""# 🧰 Índice de Herramientas — URA v3.2

**Total:** {len(tools)} herramientas ejecutables | **Actualizado:** `python3 scripts/pro/tools_index.py`

---

| Herramienta | Descripción | Uso |
|-------------|-------------|-----|
n"""
for t in tools:
    uso = f"`{t['usage'][:60]}`" if t['usage'] else "—"
    md += f"| `{t['path']}` | {t['doc'][:80]} | {uso} |\n"

md += "\n---\n\n## Por categoría\n\n"
by_dir = defaultdict(list)
for t in tools:
    parts = t["path"].split("/")
    by_dir[parts[0] if len(parts) > 1 else "raíz"].append(t)

for cat in sorted(by_dir.keys()):
    md += f"\n### {cat}/\n\n"
    for t in by_dir[cat]:
        md += f"- **`{t['name']}`** — {t['doc'][:100]}\n"
        if t['usage']:
            md += f"  - Uso: `{t['usage'][:80]}`\n"

out = BASE / "docs" / "TOOLS_INDEX.md"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(md, encoding="utf-8")

print(f"✅ Índice generado: {out}")
print(f"   {len(tools)} herramientas encontradas\n")
print("📋 Listado rápido:")
for t in tools:
    print(f"   {t['path']:50s} — {t['doc'][:60]}")
