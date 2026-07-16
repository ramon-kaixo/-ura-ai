#!/usr/bin/env python3
"""Auditoría de secretos — detecta secretos hardcodeados, credenciales en
código fuente y accesos directos a env vars que deberían pasar por
motor.core.secrets.

Uso:
    python3 scripts/pro/audit_secrets.py
    python3 scripts/pro/audit_secrets.py --json   # salida JSON
    python3 scripts/pro/audit_secrets.py --path scripts/  # escanear directorio específico
"""

import ast
import json
import os
import re
import sys
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))

EXCLUDE_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".venv",
    "backups",
    "site-packages",
    ".nervioso",
    "build",
    "node_modules",
    ".eggs",
    "*.egg-info",
})

SECRET_VAR_PATTERNS = re.compile(
    r"(_API_KEY|_TOKEN|_SECRET|_PASSWORD|_PASS|_KEY|PASSWORD|SECRET|API_KEY)$",
    re.IGNORECASE,
)

KNOWN_SECRET_NAMES: set[str] = set()

HARDCODED_KEY_PATTERN = re.compile(
    r"(?P<quote>['\"])"
    r"(sk-[A-Za-z0-9]{10,}|gsk_[A-Za-z0-9]{10,}|"
    r"sk-ant-[A-Za-z0-9]{10,}|"
    r"[A-Za-z0-9_-]{20,})"
    r"(?P=quote)"
)

CREDENTIAL_URL_PATTERN = re.compile(r"://[^:]+:[^@]+@")


class Finding:
    def __init__(
        self,
        filepath: str,
        lineno: int,
        finding_type: str,
        description: str,
        severity: str,
        value_snippet: str = "",
    ):
        self.filepath = filepath
        self.lineno = lineno
        self.type = finding_type
        self.description = description
        self.severity = severity
        self.value_snippet = value_snippet

    def to_dict(self) -> dict:
        return {
            "file": self.filepath,
            "line": self.lineno,
            "type": self.type,
            "description": self.description,
            "severity": self.severity,
            "snippet": self.value_snippet,
        }

    def __str__(self) -> str:
        return f"  [{self.severity}] {self.filepath}:{self.lineno} — {self.description}"


def _walk_files(path: Path, suffix: str = ".py") -> list[Path]:
    files = []
    if not path.exists():
        return files
    if path.is_file():
        return [path] if path.suffix == suffix else []
    for root, dirs, fnames in os.walk(path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        files.extend(Path(root) / f for f in fnames if f.endswith(suffix))
    return files


def _load_known_secrets() -> set[str]:
    """Carga KNOWN_SECRETS desde motor.core.secrets."""
    try:
        from motor.core.secrets import KNOWN_SECRETS
        return set(KNOWN_SECRETS)
    except ImportError:
        return set()


def _check_direct_env_access(  # noqa: C901
    filepath: Path, tree: ast.AST, text: str, known_secrets: set[str]
) -> list[Finding]:
    """Detecta os.environ.get() / os.getenv() para secretos conocidos que
    no pasan por motor.core.secrets."""
    findings: list[Finding] = []
    uses_secrets_module = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "motor.core.secrets":
                    uses_secrets_module = True
        if isinstance(node, ast.ImportFrom) and node.module and "motor.core.secrets" in node.module:
            uses_secrets_module = True

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        args = node.args
        if not args or not isinstance(args[0], ast.Constant) or not isinstance(args[0].value, str):
            continue
        var_name = args[0].value
        if var_name not in known_secrets:
            continue

        _is_os_env_get = (
            isinstance(func, ast.Attribute)
            and func.attr == "get"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "environ"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "os"
        )
        _is_os_getenv = (
            isinstance(func, ast.Attribute)
            and func.attr == "getenv"
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
        )

        if not uses_secrets_module and (_is_os_env_get or _is_os_getenv):
            findings.append(
                Finding(
                    str(filepath.relative_to(URA_ROOT) if filepath.is_relative_to(URA_ROOT) else filepath),
                    node.lineno or 0,
                    "direct_env_access",
                    f"Acceso directo a env var secreta '{var_name}' sin usar motor.core.secrets",
                    "high",
                    "",
                )
            )
    return findings


def _check_hardcoded_strings(
    filepath: Path, text: str
) -> list[Finding]:
    """Detecta cadenas que parecen API keys, tokens o passwords hardcodeados."""
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        # URLs con credenciales
        if CREDENTIAL_URL_PATTERN.search(line):
            findings.append(
                Finding(
                    str(filepath.relative_to(URA_ROOT) if filepath.is_relative_to(URA_ROOT) else filepath),
                    lineno,
                    "credential_url",
                    "URL con credenciales en texto plano",
                    "critical",
                    line.strip()[:100],
                )
            )
        # Cadenas con API key pattern en contexto sospechoso
        lower_line = line.lower()
        is_sensitive_context = any(
            keyword in lower_line
            for keyword in ["api_key", "apikey", "token", "password", "secret", "bearer"]
        )
        if is_sensitive_context and not line.strip().startswith("#"):
            for match in HARDCODED_KEY_PATTERN.finditer(line):
                val = match.group(0)
                findings.append(
                    Finding(
                        str(filepath.relative_to(URA_ROOT) if filepath.is_relative_to(URA_ROOT) else filepath),
                        lineno,
                        "hardcoded_secret",
                        "Posible secreto hardcodeado en contexto sensible",
                        "critical",
                        val[:50],
                    )
                )
    return findings


def _check_hardcoded_vars(
    filepath: Path, tree: ast.AST
) -> list[Finding]:
    """Detecta asignaciones a variables de nombre secreto con valores literales."""
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            var_name = target.id
            if not SECRET_VAR_PATTERNS.search(var_name):
                continue
            if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                continue
            val: str = node.value.value
            if not val:
                continue
            if val.startswith("$") or val == "None":
                continue
            findings.append(
                Finding(
                    str(filepath.relative_to(URA_ROOT) if filepath.is_relative_to(URA_ROOT) else filepath),
                    node.lineno or 0,
                    "hardcoded_variable",
                    f"Variable '{var_name}' con valor hardcodeado (no env var)",
                    "high",
                    val[:50],
                )
            )
    return findings


def main() -> int:  # noqa: C901, PLR0912
    args = sys.argv[1:]
    output_json = "--json" in args
    custom_path = None
    for arg in args:
        if arg.startswith("--path="):
            custom_path = arg.split("=", 1)[1]

    known_secrets = _load_known_secrets()
    all_findings: list[Finding] = []

    scan_root = Path(custom_path) if custom_path else URA_ROOT
    for py_file in _walk_files(scan_root):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(text, filename=str(py_file))
        except SyntaxError:
            continue

        all_findings.extend(_check_hardcoded_strings(py_file, text))
        all_findings.extend(_check_hardcoded_vars(py_file, tree))
        all_findings.extend(_check_direct_env_access(py_file, tree, text, known_secrets))

    if output_json:
        print(
            json.dumps(
                {
                    "findings": [f.to_dict() for f in sorted(all_findings, key=lambda x: (x.severity, x.filepath))],
                    "total": len(all_findings),
                    "by_severity": {
                        "critical": sum(1 for f in all_findings if f.severity == "critical"),
                        "high": sum(1 for f in all_findings if f.severity == "high"),
                        "medium": sum(1 for f in all_findings if f.severity == "medium"),
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        if not all_findings:
            print("✓ 0 hallazgos de secretos.")
            return 0

        critical = [f for f in all_findings if f.severity == "critical"]
        high = [f for f in all_findings if f.severity == "high"]
        medium = [f for f in all_findings if f.severity == "medium"]

        if critical:
            print(f"\n🔴 CRÍTICOS ({len(critical)}):")
            for f in critical:
                print(f"  {f.filepath}:{f.lineno} — {f.description}")
                if f.value_snippet:
                    print(f"    valor: {f.value_snippet}")

        if high:
            print(f"\n🟡 ALTOS ({len(high)}):")
            for f in high:
                print(f"  {f.filepath}:{f.lineno} — {f.description}")

        if medium:
            print(f"\n🔵 MEDIOS ({len(medium)}):")
            for f in medium:
                print(f"  {f.filepath}:{f.lineno} — {f.description}")

        print(
            f"\nTotal: {len(all_findings)} hallazgo(s) "
            f"(críticos={len(critical)}, altos={len(high)}, medios={len(medium)})"
        )

    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
