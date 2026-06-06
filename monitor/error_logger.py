#!/usr/bin/env python3
"""Error Logger — Log circular de errores para URA.

Formato: JSON Lines (.jsonl)
Rotación: Máximo 1000 entradas, elimina las más antiguas.
Cada entrada: timestamp, error_id, context, gateway_status, severity, message.
Detecta plataforma automáticamente (Mac vs ASUS).
"""

import json
import platform
import time
import uuid
from contextlib import suppress
from datetime import datetime
from pathlib import Path

# Detectar plataforma automáticamente
_system = platform.system().lower()
_base = Path("/home/ramon/URA") if _system == "linux" else Path("/Users/ramonesnaola/URA")

DEFAULT_LOG_PATH = _base / "logs" / "ura_errors.log"
MAX_ENTRIES = 1000


class ErrorLogger:
    """Log circular de errores con rotación automática."""

    def __init__(self, log_path: Path | None = None, max_entries: int = MAX_ENTRIES) -> None:
        self.log_path = log_path or DEFAULT_LOG_PATH
        self.max_entries = max_entries
        with suppress(OSError):
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _generate_error_id(self) -> str:
        """Genera un ID corto y único para el error."""
        return f"ERR-{uuid.uuid4().hex[:8].upper()}"

    def log_error(
        self,
        context: str,
        gateway_status: str,
        severity: str,
        message: str,
        error_id: str | None = None,
    ) -> str:
        """Registra un error. Retorna el error_id generado."""
        entry = {
            "ts": datetime.now().isoformat(),
            "id": error_id or self._generate_error_id(),
            "ctx": context,  # "ASUS" o "MAC"
            "gw": gateway_status,  # "OK", "FAIL", "DISCONNECTED"
            "sev": severity,  # "INFO", "WARN", "CRIT"
            "msg": message,
        }

        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

        self.rotate_if_needed()
        return entry["id"]

    def get_recent_errors(self, count: int = 10) -> list[dict]:
        """Retorna los últimos N errores del log."""
        if not self.log_path.exists():
            return []

        try:
            lines = self.log_path.read_text().strip().split("\n")
            errors = []
            for line in lines[-count:]:
                if line.strip():
                    errors.append(json.loads(line))
            return errors
        except Exception:
            return []

    def get_errors_by_severity(self, severity: str) -> list[dict]:
        """Filtra errores por severidad."""
        all_errors = self.get_recent_errors(self.max_entries)
        return [e for e in all_errors if e.get("sev") == severity]

    def has_recent_critical(self, within_seconds: int = 300) -> bool:
        """True si hay errores CRÍTICOS en los últimos N segundos."""
        cutoff = time.time() - within_seconds
        for error in self.get_recent_errors(50):
            if error.get("sev") == "CRIT":
                try:
                    error_time = datetime.fromisoformat(error["ts"]).timestamp()
                    if error_time > cutoff:
                        return True
                except Exception:
                    pass
        return False

    def rotate_if_needed(self) -> bool:
        """Rota el log si excede max_entries. Retorna True si rotó."""
        if not self.log_path.exists():
            return False

        try:
            lines = self.log_path.read_text().strip().split("\n")
            if len(lines) <= self.max_entries:
                return False

            # Mantener solo las últimas max_entries/2 líneas (500)
            keep = lines[-(self.max_entries // 2) :]
            self.log_path.write_text("\n".join(keep) + "\n")
            return True
        except Exception:
            return False

    def count_errors(self) -> int:
        """Cuenta el total de entradas en el log."""
        if not self.log_path.exists():
            return 0
        try:
            return len(self.log_path.read_text().strip().split("\n"))
        except Exception:
            return 0

    def clear(self) -> None:
        """Limpia el log completamente."""
        if self.log_path.exists():
            self.log_path.write_text("")


# Instancia global para uso directo
logger = ErrorLogger()


def log_error(context: str, gateway_status: str, severity: str, message: str) -> str:
    """Función de conveniencia para logear errores."""
    return logger.log_error(context, gateway_status, severity, message)


def get_recent(count: int = 10) -> list[dict]:
    """Función de conveniencia para obtener errores recientes."""
    return logger.get_recent_errors(count)
