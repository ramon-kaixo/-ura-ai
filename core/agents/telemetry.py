"""Telemetría — estado del hardware, red, LLM y recuento F821."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from core.agents.constants import NERVIOSO, RUFF, URA_ROOT
from motor.core.llm import health as _health

log = logging.getLogger("ura.multi_agent.telemetry")


class Telemetria:
    """Sistema de telemetría en tiempo real."""

    @staticmethod
    def hardware() -> dict:
        metrics = {"timestamp": datetime.now(UTC).isoformat()}
        try:
            import psutil

            vm = psutil.virtual_memory()
            metrics["ram_total_mb"] = vm.total // (1024 * 1024)
            metrics["ram_libre_mb"] = vm.available // (1024 * 1024)
            metrics["ram_pct"] = vm.percent
            metrics["cpu_pct"] = psutil.cpu_percent(interval=0.1)
        except ImportError:
            try:
                with Path("/proc/meminfo").open() as f:
                    for line in f:
                        if "MemAvailable" in line:
                            metrics["ram_libre_mb"] = int(line.split()[1]) // 1024
                        elif "MemTotal" in line:
                            metrics["ram_total_mb"] = int(line.split()[1]) // 1024
            except Exception as e:
                log.warning("Error leyendo /proc/meminfo: %s", e)
                metrics["ram_libre_mb"] = 8192
                metrics["ram_total_mb"] = 121920
        return metrics

    @staticmethod
    def red() -> dict:
        import httpx

        status = {}
        try:
            r = httpx.get(
                f"{os.environ.get('MODEL_ROUTER_URL', 'http://10.164.1.99:11435')}/health",
                timeout=3,
            )
            status["model_router"] = "ok" if r.status_code < 500 and "ok" in r.text else "down"
        except Exception:
            log.exception("Error checking model router health")
            status["model_router"] = "down"

        try:
            result = _health()
            if result.get("status") == "ok":
                modelos = result.get("modelos_disponibles", [])
                status["ollama"] = f"{len(modelos)} modelos"
            else:
                status["ollama"] = "down"
        except Exception:
            log.exception("Error checking Ollama health")
            status["ollama"] = "down"

        return status

    @staticmethod
    def llm_stats() -> dict:
        config_path = NERVIOSO / "chunk_config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            return {
                "chunk_actual": data.get("chunk_actual", 8192),
                "modelo": data.get("modelo", "?"),
                "historico_ajustes": len(data.get("historico", [])),
            }
        return {"chunk_actual": 8192, "modelo": "?", "historico_ajustes": 0}

    @staticmethod
    def f821_count() -> int:
        try:
            r = subprocess.run(
                [RUFF, "check", "--select", "F821", "."],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(URA_ROOT),
                check=False,
            )
            return r.stdout.count("F821")
        except Exception:
            log.exception("Error counting F821")
            return -1

    def reporte_completo(self) -> dict:
        return {
            "hardware": self.hardware(),
            "red": self.red(),
            "llm": self.llm_stats(),
            "f821": self.f821_count(),
        }
