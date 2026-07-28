#!/usr/bin/env python3
"""ADR Generator — Genera documentos de decisión automáticamente tras commits significativos.

Uso:
  adr_generator.py                              # Analiza el último commit y genera ADR si procede
  adr_generator.py --force <mensaje> <archivos>  # Genera ADR forzado
  adr_generator.py --list                        # Lista ADRs existentes
"""

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "architecture"
ADR_DIR.mkdir(parents=True, exist_ok=True)

SIGNIFICANT_PATTERNS = [
    (r"shell=True|subprocess\.run.*shell", "Seguridad: Eliminación de shell=True"),
    (r"sys\.exit", "Arquitectura: Eliminación de sys.exit() en librerías"),
    (r"merge conflict|<<<<<<<", "Mantenimiento: Resolución de conflictos merge"),
    (r"auth|Authorization|Bearer|API_KEY", "Seguridad: Autenticación y autorización"),
    (r"deadlock|lock|thread|race condition", "Arquitectura: Concurrencia y locks"),
    (r"abstractmethod|PluginBase|on_load|on_unload", "Arquitectura: Cambio en interfaz de plugins"),
    (r"ruff|linting|EXE|F821", "Calidad: Linting y formato"),
    (r"bandit|B324|B605|HIGH", "Seguridad: Hallazgos de bandit"),
    (r"pytest|test_.*\.py", "Calidad: Tests y cobertura"),
    (r"manifest|preflight|system_manifest", "Infraestructura: System manifest"),
    (r"migra|refactor|renombr|elimin", "Arquitectura: Refactorización"),
    (r"docker|compose|container", "Infraestructura: Docker"),
    (r"systemd|service|timer", "Infraestructura: Systemd"),
]


def get_last_commit() -> dict:
    r = subprocess.run(
        ["git", "log", "-1", "--format=%H%n%h%n%an%n%ad%n%s%n%b"],
        capture_output=True, text=True, timeout=10,
    )
    parts = r.stdout.strip().split("\n", 5)
    return {
        "hash": parts[0] if len(parts) > 0 else "",
        "short": parts[1] if len(parts) > 1 else "",
        "author": parts[2] if len(parts) > 2 else "",
        "date": parts[3] if len(parts) > 3 else "",
        "subject": parts[4] if len(parts) > 4 else "",
        "body": parts[5] if len(parts) > 5 else "",
    }


def get_changed_files() -> list[str]:
    r = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1..HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    return [f.strip() for f in r.stdout.split("\n") if f.strip()]


def adr_exists(subject: str) -> bool:
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:60]
    return any(slug in f.name for f in ADR_DIR.glob("*.md"))


def generate_adr(commit: dict, files: list[str], reason: str, category: str) -> str | None:
    subject = commit["subject"][:80]
    if adr_exists(subject):
        return None
    
    # Find next ADR number
    existing = [int(f.name.split("-")[1].split(".")[0]) for f in ADR_DIR.glob("ADR-*.md")]
    next_num = max(existing or [0]) + 1
    
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:50]
    filename = f"ADR-{next_num:03d}-{slug}.md"
    filepath = ADR_DIR / filename
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    files_str = "\n".join(f"- `{f}`" for f in files[:10])
    
    content = f"""# ADR-{next_num:03d}: {subject}

**Fecha:** {now}
**Categoría:** {category}
**Autor:** {commit['author']}
**Commit:** {commit['short']}

## Contexto
{commit['body'] or 'Cambio significativo detectado automáticamente.'}

## Decisión
{reason}

## Archivos afectados
{files_str}

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*
"""
    filepath.write_text(content)
    return str(filepath)


def main() -> int:
    if "--list" in sys.argv:
        for f in sorted(ADR_DIR.glob("ADR-*.md")):
            title = f.read_text().split("\n")[0] if f.exists() else ""
            print(f"  {f.name}: {title.replace('# ', '')}")
        return 0
    
    commit = get_last_commit()
    files = get_changed_files()
    
    if not commit["hash"]:
        print("No hay commits para analizar")
        return 1
    
    subject = commit["subject"]
    
    # Check if any significant pattern matches
    for pattern, category in SIGNIFICANT_PATTERNS:
        if re.search(pattern, subject + "\n" + commit["body"] + "\n" + " ".join(files), re.IGNORECASE):
            adr_path = generate_adr(commit, files, category, category)
            if adr_path:
                print(f"ADR generado: {adr_path}")
            else:
                print(f"ADR ya existe para: {subject[:50]}")
            return 0
    
    if "--force" in sys.argv:
        reason = sys.argv[sys.argv.index("--force") + 1] if len(sys.argv) > sys.argv.index("--force") + 1 else "Cambio significativo"
        category = "General"
        adr_path = generate_adr(commit, files, reason, category)
        if adr_path:
            print(f"ADR generado (forzado): {adr_path}")
        return 0
    
    print(f"Commit {commit['short']}: {subject[:60]}")
    print("  No se detectaron patrones significativos. Usa --force para generar manualmente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
