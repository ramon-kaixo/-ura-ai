#!/usr/bin/env python3
"""TuneladoraBridge — Permite que Laia lance buzos y consulte memoria de Tuneladora."""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class TuneladoraBridge:
    def __init__(self, tuneladora_path: str | None = None) -> None:
        if tuneladora_path:
            self.path = Path(tuneladora_path)
        else:
            self.path = Path(__file__).resolve().parent.parent
        self.buzos_dir = self.path / "sandbox" / "Aprendizaje" / "Enjambre" / "buzos"
        self.scripts_dir = self.path / "scripts"

    def lanzar_buzo(self, buzo_name: str, args: str = "") -> dict:
        buzo_script = self.buzos_dir / f"{buzo_name}.sh"
        if not buzo_script.exists():
            logger.error("Buzo no encontrado: %s", buzo_script)
            return {"stdout": "", "stderr": f"Buzo no encontrado: {buzo_name}", "returncode": 1}
        cmd = ["bash", str(buzo_script)]
        if args:
            cmd.extend(args.split())
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
        logger.info("Buzo %s ejecutado: rc=%d", buzo_name, result.returncode)
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def consultar_memoria(self, query: str) -> list:
        script = self.scripts_dir / "memoria" / "consulta_memoria.sh"
        if not script.exists():
            logger.warning("Script de memoria no encontrado")
            return []
        cmd = ["bash", str(script), query]
        try:
            out = subprocess.check_output(cmd, text=True, timeout=30)
            return json.loads(out) if out.strip() else []
        except Exception as exc:
            logger.error("Consulta memoria fallo: %s", exc)
            return []

    def obtener_estado_flota(self) -> dict:
        return self.lanzar_buzo("buzo_flota")

    def obtener_estado_red(self) -> dict:
        return self.lanzar_buzo("buzo_red")

    def ejecutar_reflexion(self) -> dict:
        script = self.path / "orquestador" / "reflexion_ciclo.sh"
        if not script.exists():
            return {"stderr": "reflexion_ciclo.sh no encontrado", "returncode": 1}
        result = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, check=False, timeout=600
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def lanzar_buzo_async(self, buzo_name: str, args: str = "") -> subprocess.Popen:
        buzo_script = self.buzos_dir / f"{buzo_name}.sh"
        cmd = ["bash", str(buzo_script)]
        if args:
            cmd.extend(args.split())
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logger.info("Buzo %s lanzado en background: pid=%d", buzo_name, proc.pid)
        return proc
