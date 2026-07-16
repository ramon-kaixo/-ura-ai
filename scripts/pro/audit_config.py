#!/usr/bin/env python3
"""Auditoría de configuración unificada (F17 scope).

Verifica:
1. Ningún consumidor accede a config.local.json o /etc/ura/config.json directamente
   (deben pasar por UraConfig.load() o config_manager.load_config()).
2. UraConfig y CONFIG son consistentes en campos compartidos (data_dir, log_level).
3. Env vars URA_QDRANT_HOST / URA_QDRANT_PORT / URA_TIMER_INTERVAL_MIN /
   URA_LOG_LEVEL solo se leen desde motor/core/config.py.

Uso:
    python3 scripts/pro/audit_config.py
"""

import ast
import os
import sys
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))

ALLOWED_CONFIG_JSON: set[Path] = {
    URA_ROOT / "motor/core/config.py",
    URA_ROOT / "core/config_manager.py",
    URA_ROOT / "motor/cli/cmd_status.py",
    URA_ROOT / "motor/tests/test_cli.py",
    URA_ROOT / "scripts/pro/audit_config.py",
}

ALLOWED_ENV_VAR: set[Path] = {
    URA_ROOT / "motor/core/config.py",
    URA_ROOT / "core/secretario_cache.py",
}

URACONFIG_ENV_VARS = frozenset({
    "URA_QDRANT_HOST",
    "URA_QDRANT_PORT",
    "URA_TIMER_INTERVAL_MIN",
    "URA_LOG_LEVEL",
})

EXCLUDE_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "backups",
    "site-packages",
    ".nervioso",
    "build",
})


def _walk_py_files() -> list[Path]:
    py_files = []
    for root, dirs, files in os.walk(URA_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f.endswith(".py"):
                py_files.append(Path(root) / f)
    return py_files


def _check_config_json_access(filepath: Path) -> list[str]:
    if filepath in ALLOWED_CONFIG_JSON:
        return []
    text = filepath.read_text(encoding="utf-8", errors="replace")
    errors = []
    for pattern, name in [
        ('"config.local.json"', "config.local.json"),
        ("'config.local.json'", "config.local.json"),
        ('"/etc/ura/config.json"', "/etc/ura/config.json"),
        ("'/etc/ura/config.json'", "/etc/ura/config.json"),
    ]:
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern in line:
                errors.append(
                    f"{filepath.relative_to(URA_ROOT)}:{lineno}: "
                    f"referencia directa a {name} (debe usar UraConfig o config_manager)"
                )
    return errors


def _check_env_var_access(filepath: Path) -> list[str]:
    if filepath in ALLOWED_ENV_VAR:
        return []
    text = filepath.read_text(encoding="utf-8", errors="replace")
    errors = []
    try:
        tree = ast.parse(text, filename=str(filepath))
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        args = node.args
        if not args or not isinstance(args[0], ast.Constant) or not isinstance(args[0].value, str):
            continue
        var = args[0].value
        if var not in URACONFIG_ENV_VARS:
            continue
        # os.environ.get(...)
        if (isinstance(func, ast.Attribute)
                and func.attr == "get"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "environ"
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "os"):
            errors.append(
                f"{filepath.relative_to(URA_ROOT)}:{node.lineno}: "
                f"env var directa {var}"
            )
        # environ.get(...) from os import environ
        if (isinstance(func, ast.Attribute)
                and func.attr == "get"
                and isinstance(func.value, ast.Name)
                and func.value.id == "environ"):
            errors.append(
                f"{filepath.relative_to(URA_ROOT)}:{node.lineno}: "
                f"env var directa {var} (from os import environ)"
            )
    return errors


def _check_consistency() -> list[str]:
    errors = []
    try:
        from motor.core.config import UraConfig
        from core.config_manager import CONFIG
    except ImportError as e:
        return [f"  ERROR: ImportError — {e}"]
    cfg = UraConfig.load()
    expected_data = CONFIG.get("paths", {}).get("data", "")
    expected_log = CONFIG.get("log_level", "")
    if cfg.data_dir != expected_data:
        errors.append(
            f"  data_dir mismatch: UraConfig={cfg.data_dir} != CONFIG={expected_data}"
        )
    if cfg.log_level != expected_log:
        errors.append(
            f"  log_level mismatch: UraConfig={cfg.log_level} != CONFIG={expected_log}"
        )
    return errors


def check1_text_references() -> list[str]:
    errors = []
    for py_file in _walk_py_files():
        errors.extend(_check_config_json_access(py_file))
    return errors


def check2_env_vars() -> list[str]:
    errors = []
    for py_file in _walk_py_files():
        errors.extend(_check_env_var_access(py_file))
    return errors


def check3_consistency() -> list[str]:
    return _check_consistency()


def main() -> int:
    c1 = check1_text_references()
    c2 = check2_env_vars()
    c3 = check3_consistency()

    print("=== Auditoría de Configuración Unificada (F17) ===\n")

    print(f"[1] Acceso directo a config.json (fuera de módulos permitidos):")
    if c1:
        for e in c1:
            print(f"  ✗ {e}")
    else:
        print("  ✓ 0 problemas")

    print(f"\n[2] Env vars UraConfig fuera de motor/core/config.py:")
    if c2:
        for e in c2:
            print(f"  ✗ {e}")
    else:
        print("  ✓ 0 problemas")

    print(f"\n[3] Consistencia UraConfig == CONFIG:")
    if c3:
        for e in c3:
            print(f"  ✗ {e}")
    else:
        print("  ✓ campos compartidos coinciden")

    total = len(c1) + len(c2) + len(c3)
    print(f"\nTotal: {total} problema(s) encontrado(s).")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
