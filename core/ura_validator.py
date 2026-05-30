#!/usr/bin/env python3
"""URA Validator — validación y sanitización de entradas.

Reglas inmutables (Final[frozenset] / tuple) para evitar mutación accidental
del estado compartido entre instancias (RUF012).
"""

import ipaddress
import logging
import re
import urllib.parse
from typing import ClassVar, Final
from urllib.parse import unquote

logger = logging.getLogger(__name__)


class URAValidator:
    """Validador de entradas de URA con reglas inmutables."""

    # ----- Límites -----
    MAX_COMMAND_LENGTH: Final[int] = 1000
    MAX_CODE_LENGTH: Final[int] = 5000
    MAX_QUERY_LENGTH: Final[int] = 500

    # ----- Patrones de comandos peligrosos (regex precompilados) -----
    DANGEROUS_COMMAND_PATTERNS: ClassVar[tuple[re.Pattern, ...]] = tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\brm\s+-rf?\b",
            r"\bformat\b",
            r"\bdel\s+/[fs]\b",
            r"\bshutdown\b",
            r"\breboot\b",
            r">\s*/dev/",
            r"\bdd\s+if=",
            r":\s*\(\s*\)\s*\{",  # fork bomb (cualquier variante)
            r"\bchmod\s+777\b",
            r"\bchown\b",
            r"\bsudo\b",
            r"\bsu\s",
            r"\bmkfs\.",
        )
    )

    DANGEROUS_SHELL_CHARS: Final[frozenset[str]] = frozenset(
        ("|", "&", ";", "`", "$", "(", ")", "<", ">")
    )

    ALLOWED_SHELL_COMMANDS: Final[frozenset[str]] = frozenset(
        ("echo", "ls", "pwd", "cd", "cat", "grep", "find", "head", "tail", "wc", "sort", "uniq")
    )

    # ----- Patrones Python peligrosos -----
    DANGEROUS_PYTHON_PATTERNS: ClassVar[tuple[re.Pattern, ...]] = tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"__import__\s*\(",
            r"\bexec\s*\(",
            r"\beval\s*\(",
            r"\bcompile\s*\(",
            r"\bopen\s*\(",
            r"\bfile\s*\(",
            r"__builtins__",
            r"\bglobals\s*\(",
            r"\blocals\s*\(",
            r"\bgetattr\s*\(",
            r"\bsetattr\s*\(",
            r"\bdelattr\s*\(",
            r"\b__class__\b",
            r"\b__bases__\b",
            r"\b__subclasses__\b",
            r"\bimport\s+",
            r"\bos\s*\.",
            r"\bsys\s*\.",
        )
    )

    ALLOWED_PYTHON_FUNCTIONS: Final[frozenset[str]] = frozenset(
        (
            "print",
            "len",
            "str",
            "int",
            "float",
            "list",
            "dict",
            "set",
            "tuple",
            "range",
            "sum",
            "min",
            "max",
            "abs",
            "round",
            "sorted",
            "reversed",
            "enumerate",
            "zip",
            "map",
            "filter",
        )
    )

    # ----- SQL injection (sin apóstrofe, demasiado falso-positivo) -----
    SQL_INJECTION_PATTERNS: Final[tuple[str, ...]] = (
        "--",
        "/*",
        "*/",
        "xp_",
        "sp_",
        " or 1=1",
        " union select",
        " drop table",
        " insert into",
        " delete from",
    )

    DANGEROUS_PATH_CHARS: Final[frozenset[str]] = frozenset(("~", "$", "`"))

    SENSITIVE_PATHS: Final[tuple[str, ...]] = (
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/.ssh/",
        "/.aws/",
        "/private/etc/",
    )

    PATH_TRAVERSAL_PATTERNS: ClassVar[tuple[re.Pattern, ...]] = tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e[/\\]",
            r"%252e%252e",
            r"\.\.%2f",
            r"\.\.%5c",
        )
    )

    # ----- helpers -----

    @staticmethod
    def _is_empty(value: str) -> bool:
        """Verifica si un valor está vacío o solo contiene espacios."""
        return not value or not value.strip()

    @staticmethod
    def _is_too_long(value: str, max_length: int) -> bool:
        """Verifica si un valor excede la longitud máxima."""
        return len(value) > max_length

    @classmethod
    def _matches_any_pattern(
        cls, value: str, patterns: tuple[re.Pattern, ...]
    ) -> re.Pattern | None:
        """Devuelve el primer patrón que coincide, o None."""
        for pat in patterns:
            if pat.search(value):
                return pat
        return None

    # ----- shell -----

    def sanitize_shell_command(self, command: str) -> tuple[bool, str]:
        """Sanitiza comando shell. Retorna (seguro, comando_o_error)."""
        if self._is_empty(command):
            return False, "Comando vacío"
        if self._is_too_long(command, self.MAX_COMMAND_LENGTH):
            return False, "Comando demasiado largo"

        match = self._matches_any_pattern(command, self.DANGEROUS_COMMAND_PATTERNS)
        if match:
            logger.warning("Comando peligroso detectado: %s", match.pattern)
            return False, f"Comando peligroso: {match.pattern}"

        bad = next((c for c in self.DANGEROUS_SHELL_CHARS if c in command), None)
        if bad:
            logger.warning("Carácter peligroso: %s", bad)
            return False, f"Carácter peligroso: {bad}"

        first_word = command.split()[0] if command.split() else ""
        if first_word not in self.ALLOWED_SHELL_COMMANDS:
            logger.warning("Comando no permitido: %s", first_word)
            return False, f"Comando no permitido: {first_word}"

        return True, command

    # ----- python -----

    def sanitize_python_code(self, code: str) -> tuple[bool, str]:
        """Sanitiza código Python. Retorna (seguro, código_o_error)."""
        if self._is_empty(code):
            return False, "Código vacío"
        if self._is_too_long(code, self.MAX_CODE_LENGTH):
            return False, "Código demasiado largo"

        match = self._matches_any_pattern(code, self.DANGEROUS_PYTHON_PATTERNS)
        if match:
            logger.warning("Patrón Python peligroso: %s", match.pattern)
            return False, f"Patrón peligroso: {match.pattern}"

        for word in re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", code):
            if word not in self.ALLOWED_PYTHON_FUNCTIONS and word != "__output__":
                logger.warning("Función no permitida: %s", word)
                return False, f"Función no permitida: {word}"

        return True, code

    # ----- url -----

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Valida URL. Retorna (válido, url_o_error)."""
        if self._is_empty(url):
            return False, "URL vacía"
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False, f"Protocolo no permitido: {parsed.scheme}"
            if not parsed.hostname:
                return False, "URL sin host"

            host = parsed.hostname
            if host == "localhost":
                return False, "Acceso a localhost no permitido"

            try:
                ip = ipaddress.ip_address(host)
                if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
                    logger.warning("IP no pública: %s", host)
                    return False, f"Acceso a IP no pública: {host}"
            except ValueError:
                pass  # hostname normal

            return True, url
        except Exception as e:  # noqa: BLE001
            logger.error("Error validando URL: %s", e)
            return False, f"Error validando URL: {e}"

    # ----- path -----

    def validate_path(self, path: str) -> tuple[bool, str]:
        """Valida path local. Retorna (válido, path_o_error)."""
        if self._is_empty(path):
            return False, "Path vacío"

        decoded = unquote(path)
        match = self._matches_any_pattern(decoded, self.PATH_TRAVERSAL_PATTERNS)
        if match:
            logger.warning("Path traversal: %s", match.pattern)
            return False, "Path traversal no permitido"

        decoded_lower = decoded.lower()
        for sensitive in self.SENSITIVE_PATHS:
            if sensitive in decoded_lower:
                logger.warning("Path sensible: %s", sensitive)
                return False, f"Path sensible: {sensitive}"

        bad = next((c for c in self.DANGEROUS_PATH_CHARS if c in path), None)
        if bad:
            return False, f"Carácter peligroso en path: {bad}"

        return True, path

    # ----- query -----

    def validate_query(self, query: str) -> tuple[bool, str]:
        """Valida query de búsqueda. Retorna (válido, query_o_error)."""
        if self._is_empty(query):
            return False, "Query vacía"
        if self._is_too_long(query, self.MAX_QUERY_LENGTH):
            return False, "Query demasiado larga"

        q = query.lower()
        for pat in self.SQL_INJECTION_PATTERNS:
            if pat in q:
                logger.warning("SQL injection: %s", pat)
                return False, f"Patrón SQL inyección: {pat}"

        return True, query.strip()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    validator = URAValidator()

    print("Pruebas de validación:")
    print("\nShell commands:")
    print(validator.sanitize_shell_command("echo 'hello'"))
    print(validator.sanitize_shell_command("rm -rf /"))
    print(validator.sanitize_shell_command(":(){:|:};:"))
    print(validator.sanitize_shell_command(": ( ) { :|:& };:"))

    print("\nPython code:")
    print(validator.sanitize_python_code("print('hello')"))
    print(validator.sanitize_python_code("__import__('os')"))
    print(validator.sanitize_python_code("().__class__.__bases__"))

    print("\nURLs:")
    print(validator.validate_url("https://example.com"))
    print(validator.validate_url("http://localhost"))
    print(validator.validate_url("http://172.16.0.1"))

    print("\nPaths:")
    print(validator.validate_path("/home/user"))
    print(validator.validate_path("../../etc/passwd"))
    print(validator.validate_path("/etc/passwd"))
    print(validator.validate_path("..%2fetc%2fpasswd"))
