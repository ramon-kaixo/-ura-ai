#!/usr/bin/env python3
"""
Terminal Gateway - Puente de Terminal para URA App
Permite ejecutar comandos de terminal (Zsh) de forma segura
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
import logging
import subprocess
from datetime import datetime

from core.privacy_scrubber import PrivacyScrubber

# Configurar logging
BENCHMARKS_DIR = Path(__file__).parent.parent / "benchmarks"
TERMINAL_LOG = BENCHMARKS_DIR / "terminal_commands.log"

# Crear directorio de benchmarks si no existe
BENCHMARKS_DIR.mkdir(exist_ok=True)

# Configurar logger para comandos de terminal
terminal_logger = logging.getLogger("terminal_gateway")
terminal_logger.setLevel(logging.INFO)
handler = logging.FileHandler(TERMINAL_LOG)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
terminal_logger.addHandler(handler)


class TerminalGateway:
    """Puente de Terminal para ejecutar comandos de forma segura"""

    # Comandos peligrosos que requieren confirmación
    DANGEROUS_COMMANDS = {
        "rm",
        "sudo",
        "dd",
        "mkfs",
        "format",
        "del",
        "erase",
        "mv",
        "cp",
        "chmod",
        "chown",
        "kill",
        "killall",
    }

    # Comandos de solo lectura (ejecución automática)
    READ_ONLY_COMMANDS = {
        "ls",
        "find",
        "grep",
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "ps",
        "top",
        "htop",
        "df",
        "du",
        "free",
        "uptime",
        "whoami",
        "id",
        "pwd",
        "date",
        "echo",
        "which",
        "whereis",
        "file",
        "stat",
        "wc",
        "sort",
        "uniq",
        "cut",
        "awk",
        "sed",
        "history",
        "env",
        "printenv",
        "uname",
        "sysctl",
    }

    def __init__(self, context_callback=None, confirmation_callback=None, telegram_bridge=None):
        """
        Inicializar Terminal Gateway

        Args:
            context_callback: Función para actualizar panel Contexto (10%)
            confirmation_callback: Función para pedir confirmación de comandos peligrosos
            telegram_bridge: Instancia de TelegramSecurityBridge (inyectada desde main_final.py)
        """
        self.context_callback = context_callback
        self.confirmation_callback = confirmation_callback
        self.command_history = []

        # Inicializar Privacy Scrubber
        self.privacy_scrubber = PrivacyScrubber()

        # Telegram Security Bridge se inyecta desde main_final.py
        self.telegram_bridge = telegram_bridge
        self.pending_telegram_authorization = False

    def log_command(self, command: str, output: str, error: str | None = None, level="INFO"):
        """Registrar comando en terminal_commands.log"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "output": output[:500] if output else "",  # Limitar output a 500 caracteres
            "error": error[:200] if error else None,
        }
        terminal_logger.log(getattr(logging, level), json.dumps(log_entry))

        if self.context_callback:
            self.context_callback(f"[Terminal] Ejecutado: {command[:50]}...")

    def is_dangerous(self, command: str) -> tuple[bool, str]:
        """
        Verificar si un comando es peligroso

        Returns:
            Tuple[bool, str]: (es_peligroso, razón)
        """
        # Verificar comandos peligrosos
        for dangerous_cmd in self.DANGEROUS_COMMANDS:
            if dangerous_cmd in command:
                return True, f"Comando peligroso detectado: {dangerous_cmd}"

        # Verificar sudo
        if "sudo" in command:
            return True, "Comando con privilegios de administrador (sudo)"

        return False, ""

    def is_read_only(self, command: str) -> bool:
        """Verificar si un comando es de solo lectura"""
        return any(read_only_cmd in command for read_only_cmd in self.READ_ONLY_COMMANDS)

    def execute_command(
        self, command: str, auto_confirm: bool = False
    ) -> tuple[bool, str, str | None]:
        """
        Ejecutar comando de terminal

        Args:
            command: Comando a ejecutar
            auto_confirm: Si es True, ejecuta comandos peligrosos sin confirmación

        Returns:
            Tuple[bool, str, Optional[str]]: (exito, salida, error)
        """
        # Verificar si es peligroso
        is_dangerous, reason = self.is_dangerous(command)

        if is_dangerous and not auto_confirm:
            # Usar Telegram Security Bridge para autorización remota
            if self.telegram_bridge and self.telegram_bridge.enabled:
                # Enviar alerta a Telegram
                def telegram_callback(authorized: bool):
                    """Callback para manejar respuesta de Telegram"""
                    self.pending_telegram_authorization = False
                    if authorized:
                        # Ejecutar comando con auto_confirm=True
                        return self.execute_command(command, auto_confirm=True)
                    else:
                        self.log_command(command, "", "Denegado por Telegram", "WARNING")
                        return False, "", "Comando denegado por usuario vía Telegram"

                self.pending_telegram_authorization = True
                self.telegram_bridge.send_security_alert(command, reason, telegram_callback)

                self.log_command(command, "", "Enviado a Telegram para autorización", "INFO")
                return (
                    False,
                    "",
                    "He detectado una acción crítica. He enviado una solicitud de permiso a tu Telegram para proceder.",
                )
            elif self.confirmation_callback:
                # Fallback a confirmación UI local
                approved = self.confirmation_callback(command, reason)
                if not approved:
                    self.log_command(command, "", "Cancelado por usuario", "WARNING")
                    return False, "", "Comando cancelado por usuario"
            else:
                self.log_command(command, "", "Sin callback de confirmación", "WARNING")
                return False, "", "Se requiere confirmación para este comando"

        # Ejecutar comando
        try:
            import shlex

            command_list = shlex.split(command)
            result = subprocess.run(
                command_list, capture_output=True, text=True, timeout=30, executable="/bin/zsh"
            )

            success = result.returncode == 0
            output = result.stdout.strip()
            error = result.stderr.strip() if result.stderr else None

            # APLICAR PRIVACY SCRUBBER ANTES DE DEVOLVER LA SALIDA
            if output:
                output, _ = self.privacy_scrubber.scrub_terminal_output(output)

            if error:
                error, _ = self.privacy_scrubber.scrub_text(error)

            # Guardar en historial
            self.command_history.append(
                {"timestamp": datetime.now().isoformat(), "command": command, "success": success}
            )

            # Registrar en log
            log_level = "INFO" if success else "ERROR"
            self.log_command(command, output, error, log_level)

            # Mostrar en contexto
            if self.context_callback and output:
                self.context_callback(f"[Terminal Salida] {output[:100]}...")

            return success, output, error

        except subprocess.TimeoutExpired:
            error = "Timeout: El comando tardó más de 30 segundos"
            self.log_command(command, "", error, "ERROR")
            return False, "", error
        except Exception as e:
            error = f"Error ejecutando comando: {str(e)}"
            self.log_command(command, "", error, "ERROR")
            return False, "", error

    def execute_read_only_command(self, command: str) -> tuple[bool, str, str | None]:
        """
        Ejecutar comando de solo lectura automáticamente (sin confirmación)

        Args:
            command: Comando de solo lectura a ejecutar

        Returns:
            Tuple[bool, str, Optional[str]]: (exito, salida, error)
        """
        if not self.is_read_only(command):
            return False, "", "El comando no es de solo lectura"

        return self.execute_command(command, auto_confirm=True)

    def get_command_history(self, limit: int = 50) -> list[dict]:
        """
        Obtener historial de comandos ejecutados

        Args:
            limit: Número máximo de comandos a retornar

        Returns:
            List[dict]: Lista de comandos ejecutados
        """
        return self.command_history[-limit:]

    def smart_execute(self, user_request: str) -> tuple[bool, str, str | None]:
        """
        Ejecutar comando basado en solicitud del usuario (inteligente)

        Este método interpreta la solicitud del usuario y genera el comando
        de terminal apropiado.

        Args:
            user_request: Solicitud del usuario en lenguaje natural

        Returns:
            Tuple[bool, str, Optional[str]]: (exito, salida, error)
        """
        request_lower = user_request.lower()

        # Mapeo de solicitudes a comandos
        command_mappings = {
            # Espacio en disco
            "espacio en disco": "df -h",
            "disk space": "df -h",
            "disco": "df -h",
            # Procesos del sistema
            "procesos": "ps aux",
            "procesos del sistema": "ps aux",
            "procesos activos": "ps aux",
            # Memoria
            "memoria": "vm_stat",
            "ram": "vm_stat",
            # Uptime
            "uptime": "uptime",
            # Directorio actual
            "directorio actual": "pwd",
            "dónde estoy": "pwd",
            # Usuario
            "quién soy": "whoami",
            "usuario": "whoami",
            # Listar archivos
            "archivos": "ls -la",
            "lista archivos": "ls -la",
            # CPU
            "cpu": "sysctl -n machdep.cpu.brand_string",
        }

        # Buscar comando apropiado
        for keyword, command in command_mappings.items():
            if keyword in request_lower:
                if self.context_callback:
                    self.context_callback(f"[Terminal] Ejecutando: {command}")
                success, output, error = self.execute_read_only_command(command)
                # Aplicar Privacy Scrubber también aquí
                if output:
                    output, _ = self.privacy_scrubber.scrub_terminal_output(output)
                return success, output, error

        # Si no se encontró mapeo, intentar interpretar directamente
        if self.context_callback:
            self.context_callback(f"[Terminal] Interpretando: {user_request}")

        # Por defecto, intentar ejecutar como comando directo
        return self.execute_command(user_request, auto_confirm=False)


if __name__ == "__main__":
    # Test del Terminal Gateway
    print("Terminal Gateway - Test")
    print(f"Log de comandos: {TERMINAL_LOG}")

    gateway = TerminalGateway()

    # Test de comando de solo lectura
    success, output, error = gateway.execute_read_only_command("pwd")
    print("\nComando: pwd")
    print(f"Éxito: {success}")
    print(f"Salida: {output}")

    # Test de comando peligroso
    success, output, error = gateway.execute_command("rm -rf test")
    print("\nComando: rm -rf test")
    print(f"Éxito: {success}")
    print(f"Salida: {output}")
    print(f"Error: {error}")
