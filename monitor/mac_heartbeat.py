#!/usr/bin/env python3
"""Mac Heartbeat — Detección de presencia Mac.

Hace ping a Mac cada 30s. Si falla 3 veces consecutivas → alerta.
Información persistida en ~/.ura/run/ura_mac_heartbeat.json.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

_TERMINAL_HOST = os.environ.get("TERMINAL_HOST", "")
try:
    with open(Path(__file__).resolve().parent.parent / "config" / "dispositivos.json") as f:
        cfg = json.load(f)
    MAC_IP = _TERMINAL_HOST or cfg.get("dispositivos", {}).get("mac-mini-de-ramon", {}).get("ip_cable", "10.164.1.26")
except (FileNotFoundError, json.JSONDecodeError):
    MAC_IP = _TERMINAL_HOST or "10.164.1.26"
PING_TIMEOUT = 2  # segundos
CONSECUTIVE_FAILURES_THRESHOLD = 3
_STATE_DIR = Path.home() / ".ura" / "run"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_STATE_DIR.chmod(0o700)
HEARTBEAT_FILE = _STATE_DIR / "ura_mac_heartbeat.json"


class MacHeartbeat:
    """Verifica si Mac es alcanzable via ping."""

    def __init__(
        self,
        mac_ip: str = MAC_IP,
        timeout: int = PING_TIMEOUT,
        threshold: int = CONSECUTIVE_FAILURES_THRESHOLD,
    ) -> None:
        self.mac_ip = mac_ip
        self.timeout = timeout
        self.threshold = threshold
        self.consecutive_failures = 0
        self.last_check = None
        self.mac_reachable = True
        self._load_state()

    def _load_state(self) -> None:
        """Carga estado previo desde disco."""
        if HEARTBEAT_FILE.exists():
            try:
                data = json.loads(HEARTBEAT_FILE.read_text())
                self.consecutive_failures = data.get("consecutive_failures", 0)
                self.mac_reachable = data.get("mac_reachable", True)
            except Exception:
                pass

    def _save_state(self) -> None:
        """Persiste estado a disco."""
        state = {
            "timestamp": datetime.now().isoformat(),
            "mac_ip": self.mac_ip,
            "mac_reachable": self.mac_reachable,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_check,
        }
        try:
            tmp = HEARTBEAT_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2))
            import os
            os.replace(str(tmp), str(HEARTBEAT_FILE))
        except Exception:
            pass

    def check_mac(self) -> bool:
        """Hace ping a Mac. Retorna True si responde."""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(self.timeout), self.mac_ip],
                capture_output=True,
                timeout=self.timeout + 1,
            )
            reachable = result.returncode == 0
        except Exception:
            reachable = False

        self.last_check = datetime.now().isoformat()

        if reachable:
            self.consecutive_failures = 0
            self.mac_reachable = True
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.threshold:
                self.mac_reachable = False

        self._save_state()
        return reachable

    def get_consecutive_failures(self) -> int:
        """Número de fallos consecutivos."""
        return self.consecutive_failures

    def should_escalate(self) -> bool:
        """True si alcanzó el umbral de escalación."""
        return self.consecutive_failures >= self.threshold

    def is_mac_connected(self) -> bool:
        """True si Mac está conectada."""
        return self.mac_reachable

    def get_sync_command(self) -> str:
        """Retorna el comando de sincronización manual."""
        _local = os.environ.get("URA_ROOT", "/Users/ramonesnaola/URA/ura_ia_1972")
        _remote = os.environ.get("ASUS_SSH", "ramon@10.164.1.99")
        _remote_path = os.environ.get("ASUS_PATH", "/home/ramon/URA/ura_ia_1972")
        return f"rsync -avz {_local}/ {_remote}:{_remote_path}/"

    def get_status(self) -> dict:
        """Retorna estado completo del heartbeat."""
        return {
            "mac_ip": self.mac_ip,
            "mac_reachable": self.mac_reachable,
            "consecutive_failures": self.consecutive_failures,
            "threshold": self.threshold,
            "last_check": self.last_check,
            "sync_command": self.get_sync_command(),
        }


# Instancia global
heartbeat = MacHeartbeat()


def check() -> bool:
    """Función de conveniencia: verifica Mac y retorna True si responde."""
    return heartbeat.check_mac()


def is_connected() -> bool:
    """Función de conveniencia: True si Mac está conectada."""
    return heartbeat.is_mac_connected()
