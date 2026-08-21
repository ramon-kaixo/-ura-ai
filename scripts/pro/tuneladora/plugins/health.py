"""HealthPlugin — health checks, dispositivos, métricas del sistema."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine


class HealthPlugin:
    """Plugins de health check. Se ejecutan en fase preflight."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine

    def check_all(self) -> dict[str, Any]:
        """Ejecuta todos los health checks. Retorna métricas."""
        results: dict[str, Any] = {}

        # Disco
        results["disco"] = self.engine.health_disk()

        # Ollama
        models = self.engine.health_ollama()
        results["ollama"] = {"ok": len(models) > 0, "modelos": len(models)}

        # RAM
        try:
            r = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=5, check=False)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "Mem:" in line:
                        parts = line.split()
                        if len(parts) > 2:
                            results["ram_usada_mb"] = int(parts[2])
        except Exception:  # noqa: S110
            pass

        # Zombies
        try:
            r = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5, check=False)
            results["zombies"] = r.stdout.count(" Z ") if r.returncode == 0 else -1
        except Exception:
            results["zombies"] = -1

        self.engine.log.info(
            f"Health: RAM={results.get('ram_usada_mb', '?')}MB, "
            f"Disco={results.get('disco', {}).get('libre_gb', '?')}GB, "
            f"Ollama={'OK' if results.get('ollama', {}).get('ok') else 'DOWN'}, "
            f"Zombies={results.get('zombies', '?')}"
        )
        return results
