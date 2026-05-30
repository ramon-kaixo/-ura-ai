"""
Módulo: core/security/command_whitelist.py
Propósito: Lista blanca de comandos permitidos para ejecución segura del sistema.
Dependencias principales: os, shlex
Reglas especiales: Solo comandos en whitelist pueden ejecutarse. Nunca permitir shell=True.
"""

import os
import shlex


class CommandWhitelist:
    def __init__(self):
        self.whitelist = {
            "ls": True,
            "pwd": True,
            "echo": True,
            "cat": True,
            "head": True,
            "tail": True,
            "wc": True,
            "grep": True,
            "find": True,
            "du": True,
            "df": True,
            "ps": True,
            "python3": True,
            "pip": True,
            "pip3": True,
            "git": True,
            "docker": True,
            "ollama": True,
            "openclaw": True,
            "curl": True,
            "wget": True,
            "which": True,
            "date": True,
            "whoami": True,
            "mkdir": True,
            "touch": True,
            "cp": True,
            "mv": True,
            "chmod": True,
            "chown": True,
            "tar": True,
            "zip": True,
            "source": True,
            "brew": True,
            "npm": True,
            "node": True,
        }
        self.blocked_commands = {
            "rm": True,
            "sudo": True,
            "su": True,
            "shutdown": True,
            "reboot": True,
            "kill": True,
            "killall": True,
            "dd": True,
            "mkfs": True,
            "fdisk": True,
            "poweroff": True,
            "passwd": True,
        }

    def is_allowed(self, command: str) -> bool:
        if not command or not isinstance(command, str):
            return False
        try:
            parts = shlex.split(command)
        except ValueError:
            return False
        if not parts:
            return False
        base_cmd = os.path.basename(parts[0])
        if base_cmd in self.blocked_commands:
            return False
        if base_cmd in self.whitelist:
            return True
        return False

    def get_base_command(self, command: str) -> str:
        try:
            parts = shlex.split(command)
        except ValueError:
            return ""
        if parts:
            return os.path.basename(parts[0])
        return ""
