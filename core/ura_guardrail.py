"""Stub: URA Guardrail — sistema de protección y validación de comandos."""

import logging

log = logging.getLogger(__name__)

BLOCKED_COMMANDS = ["rm -rf /", "sudo rm", "mkfs", "dd if="]


def validate_command(command: str) -> bool:
    """Valida que un comando sea seguro para ejecutar."""
    for blocked in BLOCKED_COMMANDS:
        if blocked in command:
            log.warning("Comando bloqueado: %s", command)
            return False
    return True


def sanitize_input(text: str) -> str:
    """Sanitiza entrada de usuario."""
    return text.strip()
