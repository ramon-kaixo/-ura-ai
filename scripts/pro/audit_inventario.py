"""audit_inventario.py — Inventario automatizado de herramientas del repo.

Clasifica scripts/herramientas en:
- integrado: referenciado por systemd, crontab, tuneladora o imports activos
- dormido_valor: sin referencias ejecutables pero con potencial
- framework: parte de un framework vivo (motor/plugin/, tuneladora/plugins/)
- basura: backups, duplicados o archivos rotos

Salida: data/inventario_herramientas.json
Uso: python3 scripts/pro/audit_inventario.py [--json data/inventario_herramientas.json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "data" / "inventario_herramientas.json"

ZONAS = {
    "scripts/pro": REPO_ROOT / "scripts" / "pro",
    "tools/benchmarks": REPO_ROOT / "tools" / "benchmarks",
    "motor/plugin": REPO_ROOT / "motor" / "plugin",
    "tuneladora/plugins": REPO_ROOT / "scripts" / "pro" / "tuneladora" / "plugins",
}

SISTEMA_PATHS = {
    "scripts/pro": "scripts/pro",
    "tools/benchmarks": "tools/benchmarks",
    "motor/plugin": "motor/plugin",
    "tuneladora/plugins": "scripts/pro/tuneladora/plugins",
}


def _walk_zone(zone: str) -> list[Path]:
    root = ZONAS[zone]
    if not root.exists():
        return []
    return [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in {".py", ".sh", ".service", ".timer", ".json", ".yml", ".yaml", ".conf"}]


def _is_executable_ref(path: Path, corpus: str) -> bool:
    """True si el archivo es referenciado como ejecutable (import, subprocess, systemd, docs)."""
    stem = path.stem
    # Referencias a modulo/import: import X / from X import / from X.Y import X
    if any(re.search(pat, corpus) for pat in (rf"import {stem}\b", rf"from {stem}\b", rf"from \S+ import {stem}\b")):
        return True
    # Referencias a script con ruta o nombre completo
    return any(
        re.search(pat, corpus)
        for pat in (rf"\b{stem}\.py\b", rf"\b{stem}\.sh\b", rf"scripts/pro/{stem}")
    )


def _is_framework(zone: str, path: Path) -> bool:
    if zone in {"motor/plugin", "tuneladora/plugins"}:
        return True
    return "plugin" in path.parent.name or path.name.startswith("plugin")


def _classify(path: Path, zone: str, corpus: str) -> str:
    if path.name.endswith((".bak", ".bak_repair", ".orig", ".old", ".tmp")):
        return "basura"
    if _is_framework(zone, path):
        return "framework"
    if _is_executable_ref(path, corpus):
        return "integrado"
    return "dormido_valor"


def build_corpus() -> str:
    """Texto combinado de fuentes VIVAS: systemd units, crontab, tuneladoras activas y motor/.

    NO incluye scripts/pro (evita que un script se marque 'integrado' por
    mencionarse a si mismo o a sus vecinos).
    """
    parts: list[str] = []
    for pattern in ("deploy/*.service", "deploy/*.timer", "scripts/deploy/*", "*.service", "*.timer"):
        for p in REPO_ROOT.glob(pattern):
            if p.is_file():
                parts.append(p.read_text(errors="ignore"))
    cron = subprocess.run(
        ["crontab", "-l"], capture_output=True, text=True, check=False, timeout=15,
    )
    if cron.returncode == 0:
        parts.append(cron.stdout)
    for name in ("tuneladora_mantenimiento.py", "tuneladora_mejora.py", "tuneladora.py"):
        p = REPO_ROOT / "scripts" / "pro" / name
        if p.is_file():
            parts.append(p.read_text(errors="ignore"))
    for root in (REPO_ROOT / "motor", REPO_ROOT / "core", REPO_ROOT / "knowledge"):
        if root.exists():
            for p in root.rglob("*.py"):
                if p.is_file():
                    parts.append(p.read_text(errors="ignore"))
    for base in (Path("/etc/systemd/system"), Path.home() / ".config/systemd/user"):
        if base.exists():
            for p in base.rglob("ura-*.service"):
                if p.is_file() or p.is_symlink():
                    parts.append(p.read_text(errors="ignore"))
    return "\n".join(parts)


def run(output: Path = DEFAULT_OUTPUT) -> dict:
    corpus = build_corpus()
    inventario: dict = {"generado": datetime.now(UTC).isoformat(), "zonas": {}}
    for zone in ZONAS:
        paths = _walk_zone(zone)
        archivos = []
        for p in paths:
            clasificacion = _classify(p, zone, corpus)
            archivos.append({"archivo": p.name, "ruta": str(p.relative_to(REPO_ROOT)), "clasificacion": clasificacion})
        inventario["zonas"][zone] = {"total": len(archivos), "archivos": archivos}
    return inventario


def main() -> int:
    output = DEFAULT_OUTPUT
    if "--json" in sys.argv:
        idx = sys.argv.index("--json")
        output = Path(sys.argv[idx + 1])
    inventario = run(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventario, ensure_ascii=False, indent=2))
    total = sum(z["total"] for z in inventario["zonas"].values())
    print(f"Inventario: {total} archivos en {len(inventario['zonas'])} zonas -> {output}")
    for zona, data in inventario["zonas"].items():
        por_clase: dict[str, int] = {}
        for a in data["archivos"]:
            por_clase[a["clasificacion"]] = por_clase.get(a["clasificacion"], 0) + 1
        clases = ", ".join(f"{k}={v}" for k, v in sorted(por_clase.items()))
        print(f"  {zona}: {data['total']} ({clases})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
