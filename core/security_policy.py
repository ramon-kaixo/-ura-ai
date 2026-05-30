#!/usr/bin/env python3
"""
Security Policy — FASE 2
────────────────────────────
API token auth, input sanitization, jailbreak guardrail,
command whitelist. All security in one place.
"""

import hmac
import re
import secrets
from pathlib import Path

# ── Token de API ────────────────────────────────────────────

TOKEN_FILE = Path.home() / ".ura" / "api_token"


def generate_token() -> str:
    """Genera un token aleatorio seguro de 48 caracteres."""
    return secrets.token_hex(24)


def load_or_create_token() -> str:
    """Carga el token existente o crea uno nuevo."""
    TOKEN_FILE.parent.mkdir(exist_ok=True)
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    token = generate_token()
    TOKEN_FILE.write_text(token)
    TOKEN_FILE.chmod(0o600)
    return token


def get_token() -> str:
    return load_or_create_token()


def verify_token(token: str) -> bool:
    """Verifica un token contra el almacenado. Usa comparación de tiempo constante."""
    stored = load_or_create_token().encode()
    provided = token.encode()
    return hmac.compare_digest(stored, provided)


# ── Sanitización de entrada ─────────────────────────────────

MAX_INPUT_LENGTH = 4000
FORBIDDEN_PATTERNS = [
    r"\{:\s*\}",  # Objetos vacíos maliciosos
    r"<script[^>]*>",  # XSS
    r"javascript\s*:",  # JS protocol
    r'on\w+\s*=\s*["\']',  # Event handlers inline
    r"data\s*:\s*text/html",  # Data URI HTML
]


def sanitize_input(text: str) -> str:
    """Sanitiza entrada del usuario: límites, escape, XSS."""
    if not isinstance(text, str):
        return ""

    # Límite de longitud
    text = text[:MAX_INPUT_LENGTH]

    # Escapar caracteres de control
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Escapar caracteres peligrosos
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&#x27;")

    return text


# ── Guardarraíl anti-jailbreak ──────────────────────────────

JAILBREAK_PATTERNS = [
    r"ignor[ae]\s+(las\s+)?instrucciones?\s+(anteriores|previas|de\s+arriba)",
    r"ignore\s+(the\s+)?(previous|above|prior)\s+instructions?",
    r"forget\s+(all|everything|your)\s+(instructions?|rules?|guidelines?)",
    r"eres\s+(ahora|en\s+adelante)\s+(un|una)\b",
    r"you\s+are\s+now\s+(a|an)\b",
    r"pretend\s+(you\s+are|to\s+be)\b",
    r"finge\s+que\s+(eres|estás|sos)\b",
    r"actúa\s+como\s+(si\s+fueras|un|una)\b",
    r"act\s+as\s+(if\s+you\s+are|a|an)\b",
    r"nueva\s+personalidad",
    r"new\s+persona",
    r"sin\s+restricciones",
    r"without\s+restrictions?",
    r"como\s+modelo\s+de\s+lenguaje",
    r"do\s+not\s+follow\s+(your|the)\s+(rules?|guidelines?|ethics?)",
    r"no\s+sigas\s+(tus|las)\s+(reglas?|normas?|ética)",
    r"^(dime|dime\s+todo|cuéntame)\s+(cómo|donde)\s+(hacer|fabricar|crear)\b",
    r"^\s*(tell|show)\s+me\s+how\s+to\s+(hack|exploit|bypass|break)\b",
]

GUARDRAIL_RESPONSE = (
    "[URA: He detectado un intento de manipulación de mis instrucciones. "
    "Soy URA, asistente leal del sistema. No puedo ni voy a ignorar mis "
    "directrices de seguridad. ¿En qué puedo ayudarte de forma legítima?]"
)


def detect_jailbreak(text: str) -> bool:
    """Detecta intentos de jailbreak en el texto del usuario."""
    lower = text.lower()
    return any(re.search(pattern, lower) for pattern in JAILBREAK_PATTERNS)


# ── Lista blanca de comandos ────────────────────────────────

ALLOWED_COMMANDS = [
    "brew install",
    "brew uninstall",
    "brew update",
    "brew upgrade",
    "brew list",
    "brew info",
    "pip install",
    "pip uninstall",
    "pip list",
    "pip show",
    "python",
    "python3",
    "pytest",
    "git status",
    "git log",
    "git diff",
    "git branch",
    "docker ps",
    "docker compose",
    "docker-compose",
    "ollama list",
    "ollama pull",
    "ollama ps",
    "ollama run",
    "ps aux",
    "top",
    "htop",
    "df",
    "du",
    "ls",
    "find",
    "cat",
    "head",
    "tail",
    "wc",
    "curl",
    "wget",
    "open",
    "screencapture",
    "osascript",
    "pgrep",
    "pkill",
    "lsof",
    "netstat",
    "ifconfig",
    "ping",
    "traceroute",
    "nslookup",
    "dig",
    "whois",
    "ssh",
    "scp",
    "rsync",
    "tar",
    "zip",
    "unzip",
    "gzip",
    "gunzip",
    "ruff",
    "bandit",
    "mypy",
    "echo",
    "date",
    "whoami",
    "hostname",
    "uptime",
    "which",
    "whereis",
    "whatis",
    "man",
    "code",
    "windsurf",
    "npm",
    "npx",
    "node",
    "yarn",
    "pnpm",
]

FORBIDDEN_COMMANDS = [
    "rm -rf",
    "rm -r",
    "sudo rm",
    "mkfs",
    "dd if=",
    "> /dev/",
    ":(){ :|:& };:",  # Fork bomb
    "chmod 777",
    "chmod -R 777",
    "chown -R",
    "wget -O - | sh",
    "curl | sh",
    "curl | bash",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
]


def validate_command(command: str) -> tuple[bool, str]:
    """
    Valida un comando contra la lista blanca y la lista negra.
    Returns (is_allowed, reason).
    """
    cmd_lower = command.lower().strip()

    # Lista negra primero (más prioridad)
    for forbidden in FORBIDDEN_COMMANDS:
        if forbidden in cmd_lower:
            return False, f"Comando prohibido detectado: '{forbidden}'"

    # Lista blanca: el comando debe empezar con uno de los prefijos
    for allowed in ALLOWED_COMMANDS:
        if cmd_lower.startswith(allowed.lower()):
            return True, "ok"

    return False, f"Comando '{command[:60]}' no está en la lista blanca"


def validate_brew_package(pkg: str) -> bool:
    """Valida que el nombre del paquete sea seguro (sin inyección)."""
    if not pkg:
        return False
    # Solo letras, números, guiones, puntos
    return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-._@/]*$", pkg))
