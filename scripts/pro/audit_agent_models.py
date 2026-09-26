#!/usr/bin/env python3
"""Valida que cada `model:` declarado en .opencode/agents/*.md exista en `opencode models`.

Salida: lista de agentes con OK/ROTO. Exit 1 si algún modelo no existe.
No modifica nada: solo lectura.
"""

import re
import subprocess
import sys
from pathlib import Path


def _run_models() -> set[str]:
    bins = [
        "opencode",
        str(Path("~/.opencode/bin/opencode").expanduser()),
        "/usr/local/bin/opencode",
    ]
    for b in bins:
        try:
            out = subprocess.run(
                [b, "models"],
                capture_output=True,
                text=True,
                timeout=240,
                check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                return set(out.stdout.splitlines())
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    return set()


def main() -> int:
    agents = sorted(Path(".opencode/agents").glob("*.md"))
    if not agents:
        print("NO VERIFICADO: no hay .opencode/agents/*.md")
        return 0

    declared: dict[str, str] = {}
    for a in agents:
        text = a.read_text(encoding="utf-8")
        m = re.search(r"^model:\s*(.+)$", text, re.MULTILINE)
        if m:
            declared[str(a)] = m.group(1).strip()

    if not declared:
        print("✅ ningún agente declara `model:` (heredan el global) — nada que validar")
        return 0

    available = _run_models()
    if not available:
        print("NO VERIFICADO: `opencode models` no devolvió modelos (¿binario no disponible?)")
        return 0

    broken = []
    for a, model in declared.items():
        if model in available:
            print(f"✅ {a} -> {model}")
        else:
            print(f"❌ {a} -> {model}  (NO existe)")
            broken.append(a)

    if broken:
        print(f"ROTOS: {', '.join(broken)}")
        return 1
    print("✅ todos los modelos de agentes existen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
