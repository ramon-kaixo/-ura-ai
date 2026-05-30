#!/usr/bin/env python3
"""
Script para corregir indentación de métodos procesar() que quedaron fuera de la clase
"""

import re
from pathlib import Path


def fix_indentation(file_path: Path):
    """Corrige indentación de métodos procesar() fuera de la clase."""
    content = file_path.read_text()
    original = content

    # Patrón para detectar métodos fuera de la clase (después de get_* o singleton)
    pattern = r"(def get_\w+\(.*?\):.*?return .+?\n)(\s+)(def procesar\(self, texto: str\) -> str:.*?def responder\(self, texto: str\) -> str:)"

    def replacer(match):
        match.group(2)
        methods = match.group(3)
        # Reducir indentación de los métodos para que estén dentro de la clase
        # Reemplazar 4 espacios de indentación extra
        methods_fixed = re.sub(r"^    ", "", methods, flags=re.MULTILINE)
        # Mover los métodos antes del get_*
        return methods_fixed + "\n\n" + match.group(1)

    content_fixed = re.sub(pattern, replacer, content, flags=re.DOTALL)

    if content_fixed != original:
        file_path.write_text(content_fixed)
        return True
    return False


def main():
    agents_dir = Path("/Users/ramonesnaola/URA/ura_ia_1972/agents")

    fixed = 0
    for file_path in agents_dir.glob("agente_*.py"):
        if fix_indentation(file_path):
            fixed += 1
            print(f"✓ Corregido: {file_path.name}")

    print(f"\nTotal corregidos: {fixed}")


if __name__ == "__main__":
    main()
