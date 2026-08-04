#!/usr/bin/env python3
import json, re, subprocess
from pathlib import Path
B = Path("/home/ramon/URA/ura_ia_1972")
E = {".git","build",".venv",".sandbox_packages","__pycache__",".pytest_cache"}
P = [f for f in B.rglob("*.py") if not any(x in str(f) for x in E)]
T = {f: f.read_text(errors="ignore") for f in P}
I = set()
for t in T.values():
    for m in re.finditer(r'(?:from|import)\s+([a-zA-Z_]\w*)', t): I.add(m.group(1))
NI = [str(f.relative_to(B)) for f in P if f.stem not in I|{"__init__","conftest","setup","__main__"} and not any(f.stem in v for v in T.values())]
R = lambda c: subprocess.run(c,shell=True,capture_output=True,text=True,timeout=60).stdout.strip()
SI = [l.split()[0] for l in R("systemctl list-units --type=service --state=inactive --no-pager --no-legend | grep ura- || true").splitlines() if l.strip()]
SF = [l.split()[0] for l in R("systemctl list-units --type=service --state=failed --no-pager --no-legend | grep ura- || true").splitlines() if l.strip()]
TM = [l.strip() for l in R("systemctl list-timers --all --no-pager | grep -E 'ura-|tuneladora-' || true").splitlines() if l.strip()]
SC = [l.strip() for l in R("screen -ls 2>/dev/null || true").splitlines() if "\t" in l or "." in l]
TX = [l.strip() for l in R("tmux ls 2>/dev/null || true").splitlines() if l.strip()]
M = (B/"Makefile").read_text(errors="ignore") if (B/"Makefile").exists() else ""
SH = [str(f.relative_to(B)) for f in (B/"scripts"/"pro").rglob("*.py") if f.stem not in M and not any(f.stem in v for v in T.values())]
ST = [l.strip() for l in R("find /home/ramon/URA/ura_ia_1972 -name '*.py' -not -path '*/build/*' -not -path '*/.venv/*' -not -path '*/.git/*' -mtime +60 | head -50").splitlines() if l.strip()]
SK = []
for f,t in T.items():
    for m in re.finditer(r'(@pytest\.mark\.skip.*|#\s*(TODO|FIXME|HACK|XXX))', t, re.I):
        SK.append({"file":str(f.relative_to(B)),"line":t[:m.start()].count("\n")+1,"match":m.group(0)[:60]})
D = {"no_importados":NI,"systemd_inactive":SI,"systemd_failed":SF,"timers":TM,"screens":SC,"tmux":TX,"scripts_huerfanos":SH,"stale":ST,"skipped":SK}
(B/"docs").mkdir(exist_ok=True)
(B/"docs"/"auditoria_dormidos.json").write_text(json.dumps(D,indent=2,ensure_ascii=False),encoding="utf-8")
print("="*50);print("AUDITORIA DORMIDOS");print("="*50)
print(f"No importados: {len(NI)}");print(f"Inactive systemd: {len(SI)}");print(f"Failed systemd: {len(SF)}")
print(f"Timers: {len(TM)}");print(f"Screens: {len(SC)}");print(f"Tmux: {len(TX)}")
print(f"Scripts huerfanos: {len(SH)}");print(f"Stale: {len(ST)}");print(f"Skipped/TODO: {len(SK)}")
print(f"\nJSON: docs/auditoria_dormidos.json")
