"""ProactiveDetector — detecta problemas antes de que sean criticos.

Uso:
    detector = ProactiveDetector()
    detector.check_disk()      # Alerta si < 20GB (warning), < 10GB (critical)
    detector.check_memory()    # Alerta si > 90% uso
    detector.check_ollama()    # Alerta si Ollama no responde
    detector.check_git_status()  # Alerta si hay cambios sin commitear
"""
from __future__ import annotations

import logging
import os
import subprocess  # nosec B404
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from motor.brain.alerts import Alert
    from motor.brain.alerts import AlertEngine as _AlertEngine
    from motor.brain.observer import BrainObserver

    _HAS_ALERTS = True
except ImportError:
    _HAS_ALERTS = False

log = logging.getLogger("ura.tuneladora.detector")


@dataclass
class DetectionResult:
    check: str
    status: str  # ok, warning, critical
    message: str
    value: float | int | str | None = None
    timestamp: str = ""


_DISK_WARN_GB = 20
_DISK_CRIT_GB = 10
_MEM_WARN_PCT = 85
_MEM_CRIT_PCT = 95


class ProactiveDetector:
    """Detecta anomalias antes de que afecten al sistema."""

    def __init__(self, notify: bool = True) -> None:
        self._notify = notify
        self._alert_engine: Any = None
        if _HAS_ALERTS:
            try:
                self._alert_engine = _AlertEngine(BrainObserver())
            except Exception:
                self._alert_engine = None

    def _alert(self, severity: str, title: str, description: str = "") -> None:
        """Envia alerta via AlertEngine si esta disponible."""
        log.warning("[%s] %s: %s", severity.upper(), title, description)
        if self._notify and self._alert_engine is not None:
            try:
                alert = Alert(
                    severity=severity,
                    title=title,
                    description=description,
                    affected_subsystems=["tuneladora"],
                    timestamp=datetime.now(UTC).timestamp(),
                )
                self._alert_engine._alert_history.append(alert)
            except Exception as exc:
                log.debug("alert append failed: %s", exc)

    # ── Checks individuales ──────────────────────────────────

    def check_disk(self, path: str = "/") -> DetectionResult:
        """Verifica espacio en disco. Alerta si < umbrales."""
        try:
            usage = os.statvfs(path)
            libre_gb = round((usage.f_frsize * usage.f_bavail) / 1e9, 1)
            total_gb = round((usage.f_frsize * usage.f_blocks) / 1e9, 1)
            used_pct = round((1 - usage.f_bavail / usage.f_blocks) * 100, 1)

            if libre_gb < _DISK_CRIT_GB:
                self._alert("emergency", "DISKO KRITIKOA", f"Solo {libre_gb}GB libres de {total_gb}GB ({used_pct}% usado)")
                return DetectionResult("disk", "critical", f"{libre_gb}GB libre", libre_gb)
            if libre_gb < _DISK_WARN_GB:
                self._alert("warning", "DISKO BAXUA", f"{libre_gb}GB libres de {total_gb}GB ({used_pct}% usado)")
                return DetectionResult("disk", "warning", f"{libre_gb}GB libre", libre_gb)
            return DetectionResult("disk", "ok", f"{libre_gb}GB libre", libre_gb)
        except Exception as e:
            return DetectionResult("disk", "error", str(e))

    def check_memory(self) -> DetectionResult:
        """Verifica uso de RAM. Alerta si > umbrales."""
        try:
            with Path("/proc/meminfo").open() as f:
                lines = f.readlines()
            mem_total = 0
            mem_available = 0
            for line in lines:
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1])
            if mem_total == 0:
                return DetectionResult("memory", "error", "No se pudo leer /proc/meminfo")
            used_pct = round((1 - mem_available / mem_total) * 100, 1)
            if used_pct > _MEM_CRIT_PCT:
                self._alert("critical", "MEMORIA KRITIKOA", f"{used_pct}% usada")
                return DetectionResult("memory", "critical", f"{used_pct}% usado", used_pct)
            if used_pct > _MEM_WARN_PCT:
                self._alert("warning", "MEMORIA ALTUA", f"{used_pct}% usada")
                return DetectionResult("memory", "warning", f"{used_pct}% usado", used_pct)
            return DetectionResult("memory", "ok", f"{used_pct}% usado", used_pct)
        except Exception as e:
            return DetectionResult("memory", "error", str(e))

    def check_ollama(self) -> DetectionResult:
        """Verifica que Ollama responde."""
        try:
            import httpx

            r = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if r.status_code == 200:
                models = r.json().get("models", [])
                count = len(models)
                if count == 0:
                    self._alert("warning", "OLLAMA HUTSA", "Ollama responde pero no hay modelos cargados")
                    return DetectionResult("ollama", "warning", "0 modelos cargados", count)
                return DetectionResult("ollama", "ok", f"{count} modelos disponibles", count)
            self._alert("warning", "OLLAMA ERROA", f"Status code: {r.status_code}")
            return DetectionResult("ollama", "warning", f"HTTP {r.status_code}")
        except httpx.ConnectError:
            self._alert("critical", "OLLAMA EZ DAU", "Ollama no responde en localhost:11434")
            return DetectionResult("ollama", "critical", "No conecta")
        except Exception as e:
            return DetectionResult("ollama", "error", str(e))

    def check_git_status(self) -> DetectionResult:
        """Verifica si hay cambios sin commitear."""
        try:
            repo = Path(__file__).resolve().parent.parent.parent.parent
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10, cwd=str(repo), check=False,  # nosec B603 B607
            )
            if r.returncode != 0:
                return DetectionResult("git", "error", "No es un repo git")
            changes = [line for line in r.stdout.split("\n") if line.strip()]
            count = len(changes)
            if count > 50:
                self._alert("critical", "GIT GARBITU GABE", f"{count} archivos sin commitear")
                return DetectionResult("git", "critical", f"{count} archivos sin commit", count)
            if count > 10:
                self._alert("warning", "GIT GARBITU GABE", f"{count} archivos sin commitear")
                return DetectionResult("git", "warning", f"{count} archivos sin commit", count)
            return DetectionResult("git", "ok", f"{count} archivos sin commit", count)
        except Exception as e:
            return DetectionResult("git", "error", str(e))

    # ── Check completo ───────────────────────────────────────

    def check_all(self) -> list[DetectionResult]:
        """Ejecuta todos los checks y retorna resultados."""
        return [
            self.check_disk(),
            self.check_memory(),
            self.check_ollama(),
            self.check_git_status(),
        ]

    def get_critical(self, results: list[DetectionResult]) -> list[DetectionResult]:
        """Filtra solo resultados criticos."""
        return [r for r in results if r.status == "critical"]


    # ── Auto-healing (v4.0) ─────────────────────────────

    def restart_ollama(self) -> dict:
        try:
            import shutil
            import subprocess  # nosec B404
            if shutil.which("systemctl"):
                r = subprocess.run(["systemctl", "restart", "ollama"], capture_output=True, text=True, timeout=30, check=False)  # nosec B603 B607
                return {"ok": r.returncode == 0, "method": "systemctl", "output": (r.stdout or "")[:200]}
            r = subprocess.run(["docker", "restart", "ollama"], capture_output=True, text=True, timeout=30, check=False)  # nosec B603 B607
            return {"ok": r.returncode == 0, "method": "docker", "output": (r.stdout or "")[:200]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def clear_zombies(self) -> dict:
        """Mata procesos zombies (estado Z) del sistema, no procesos URA."""
        import os as _os
        killed = 0
        try:
            for entry in Path("/proc").iterdir():
                pid = entry.name
                if not pid.isdigit():
                    continue
                try:
                    Path(f"/proc/{pid}/exe").readlink()
                    with Path(f"/proc/{pid}/status").open() as f:
                        status = f.read()
                    if "State:\tZ" in status:
                        _os.kill(int(pid), 9)
                        killed += 1
                except (OSError, PermissionError, FileNotFoundError):
                    continue
            return {"ok": True, "killed": killed}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def restart_service(self, service: str = "ura-tuneladora") -> dict:
        import shutil
        import subprocess  # nosec B404
        if not shutil.which("systemctl"):
            return {"ok": False, "error": "systemctl no disponible"}
        try:
            r = subprocess.run(["systemctl", "restart", service], capture_output=True, text=True, timeout=30, check=False)  # nosec B603 B607
            return {"ok": r.returncode == 0, "service": service, "output": (r.stdout or "")[:200]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
