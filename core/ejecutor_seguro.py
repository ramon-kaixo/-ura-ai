#!/usr/bin/env python3
"""
URA - Ejecutor Seguro de Comandos
Controlled command execution with blacklist and timeout
"""

import shlex
import subprocess
from typing import Any

from core.logging_config import get_logger

logger = get_logger("ejecutor_seguro", log_dir="./logs")

# Lista negra de comandos peligrosos
BLACKLIST = [
    "rm -rf",
    "rm -r /",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",  # fork bomb
    "chmod 777",
    "chown root",
    "sudo rm",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "> /dev/sd",
    ":(){:|:&};:",
    "init 0",
    "kill -9 -1",
]


def ejecutar(comando: str, timeout: int = 30) -> dict[str, Any]:
    """
    Ejecutar comando de forma controlada

    Args:
        comando: Comando a ejecutar
        timeout: Timeout en segundos (default 30)

    Returns:
        Dict con {ok, stdout, stderr, codigo}
    """
    # Verificar lista negra
    comando_lower = comando.lower()
    for peligroso in BLACKLIST:
        if peligroso.lower() in comando_lower:
            logger.warning(f"Comando bloqueado por lista negra: {comando}")
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"Comando bloqueado: contiene patrón peligroso '{peligroso}'",
                "codigo": -1,
            }

    logger.info(f"Ejecutando comando: {comando}")

    try:
        # Use shlex.split to avoid shell=True (prevents shell injection)
        try:
            args = shlex.split(comando)
        except ValueError as e:
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"Comando mal formado: {e}",
                "codigo": -4,
            }

        if not args:
            return {
                "ok": False,
                "stdout": "",
                "stderr": "Comando vacío",
                "codigo": -5,
            }

        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        log_result = {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "codigo": result.returncode,
        }

        logger.info(f"Comando ejecutado: returncode={result.returncode}")

        return log_result

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout al ejecutar comando: {comando}")
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"Timeout después de {timeout} segundos",
            "codigo": -2,
        }
    except Exception as e:
        logger.error(f"Error al ejecutar comando: {e}")
        return {
            "ok": False,
            "stdout": "",
            "stderr": str(e),
            "codigo": -3,
        }


if __name__ == "__main__":
    # Test
    print("=== TEST EJECUTOR SEGURO ===")

    # Comando seguro
    resultado = ejecutar("echo 'Hola Mundo'")
    print(f"Echo: {resultado}")

    # Comando peligroso
    resultado = ejecutar("rm -rf /")
    print(f"rm -rf: {resultado}")
