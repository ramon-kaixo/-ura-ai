#!/usr/bin/env python3
"""
Auto-etiquetado de tests con marcadores pytest basándose en:
- Path del test (unit/, integration/, contracts/)
- Nombre del test (timeout, slow, stress, load, etc.)
"""

from pathlib import Path

MARKER_RULES = [
    (lambda p, n: 'contracts/' in p, 'contract'),
    (lambda p, n: 'integration/' in p, 'integration'),
    (lambda p, n: 'unit/' in p, 'unit'),
    (lambda p, n: any(k in p.lower() or k in n.lower() for k in ['timeout', 'slow', 'stress', 'load', 'benchmark', 'perf_', 'latency']), 'slow'),
    (lambda p, n: 'smoke' in p.lower() or 'smoke' in n.lower(), 'smoke'),
    (lambda p, n: 'e2e/' in p or 'e2e_' in p.lower() or 'e2e_' in n.lower(), 'e2e'),
    (lambda p, n: 'hypothesis' in p.lower() or 'property' in p.lower() or 'hypothesis' in n.lower(), 'hypothesis'),
    (lambda p, n: 'gx10' in p.lower() or 'asus' in p.lower(), 'gx10'),
    (lambda p, n: 'mac' in p.lower() or 'darwin' in p.lower(), 'mac'),
]

def should_add_marker(filepath: Path, test_name: str) -> set[str]:
    markers = set()
    rel_path = str(filepath).replace('\\', '/')

    for check, marker in MARKER_RULES:
        if check(rel_path, test_name):
            markers.add(marker)

    if 'unit/' in rel_path and not markers:
        markers.add('unit')

    return markers

def auto_mark_test(filepath: Path) -> bool:
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')
    new_lines = []
    i = 0
    modified = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('def test_'):
            # Buscar decoradores existentes
            j = i - 1
            existing_markers = set()
            while j >= 0 and lines[j].strip().startswith('@'):
                dec = lines[j].strip()
                if 'pytest.mark.' in dec:
                    marker = dec.split('pytest.mark.')[-1].rstrip(')')
                    existing_markers.add(marker)
                j -= 1

            test_name = stripped.split('(')[0].replace('def ', '')
            new_markers = should_add_marker(filepath, test_name) - existing_markers

            if new_markers:
                indent = len(line) - len(line.lstrip())
                for marker in sorted(new_markers):
                    new_lines.append(' ' * indent + f'@pytest.mark.{marker}')
                modified = True

        new_lines.append(line)
        i += 1

    if modified:
        filepath.write_text('\n'.join(new_lines), encoding='utf-8')
        return True
    return False

def main():
    test_root = Path('tests')
    modified_count = 0
    total = 0

    for test_file in test_root.rglob('test_*.py'):
        if '__pycache__' in str(test_file):
            continue
        total += 1
        if auto_mark_test(test_file):
            modified_count += 1
            print(f"✅ Marcado: {test_file}")

    print(f"\nTotal archivos: {total}, Modificados: {modified_count}")

if __name__ == '__main__':
    main()
