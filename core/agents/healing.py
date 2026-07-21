"""Bucle completo: DETECTAR → AISLAR → REPARAR → VALIDAR → ACTUALIZAR."""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime

from core.agents.conciencia import Conciencia
from core.agents.constants import MAX_CICLO_S, RUFF, SCRIPTS, URA_ROOT
from core.agents.ejecutor import AgenteEjecutor
from core.agents.orquestador import AgenteOrquestador
from core.agents.reparador import AgenteReparador
from core.agents.telemetry import Telemetria


class SelfHealingLoop:
    """Bucle completo: DETECTAR → AISLAR → REPARAR → VALIDAR → ACTUALIZAR."""

    def __init__(self) -> None:
        self.orquestador = AgenteOrquestador()
        self.ejecutor = AgenteEjecutor()
        self.reparador = AgenteReparador()
        self.telemetria = Telemetria()
        self._fallos_consecutivos = 0

    def ejecutar(self, archivo: str | None = None) -> dict:
        inicio = time.monotonic()
        reporte = {"timestamp": datetime.now(UTC).isoformat(), "pasos": []}

        tele = self.telemetria.reporte_completo()
        conciencia = Conciencia.leer()

        accion, razon = self.orquestador.decidir(tele, conciencia)
        reporte["accion"] = accion
        reporte["razon"] = razon
        reporte["pasos"].append({"paso": "orquestar", "accion": accion, "razon": razon})

        if accion == "REFACTORIZAR":
            Conciencia.actualizar_proceso("ejecutor", "activo")
            result = self.ejecutor.ejecutar(workers=4)
            reporte["refactor"] = result
            Conciencia.actualizar_proceso("ejecutor", "idle")

        elif accion == "REPARAR":
            Conciencia.actualizar_proceso("reparador", "activo")
            try:
                r = subprocess.run(
                    [RUFF, "check", "--select", "F821", "--output-format", "json", "."],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(URA_ROOT),
                    check=False,
                )
                data = json.loads(r.stdout)
                files = {x["filename"] for x in data if "/.venv/" not in x.get("filename", "")}
                for f in list(files)[:5]:
                    reparado, nivel, msg = self.reparador.reparar(f, [])
                    reporte["pasos"].append(
                        {
                            "paso": "reparar",
                            "archivo": f,
                            "reparado": reparado,
                            "nivel": nivel,
                            "mensaje": msg,
                        },
                    )
            except Exception as e:
                reporte["pasos"].append({"paso": "reparar", "error": str(e)})
            Conciencia.actualizar_proceso("reparador", "idle")

        elif accion == "PAUSAR":
            reporte["pasos"].append({"paso": "pausar", "mensaje": "RAM saturada"})
            time.sleep(30)

        subprocess.run(
            [RUFF, "check", "--fix", "."],
            capture_output=True,
            timeout=60,
            cwd=str(URA_ROOT),
            check=False,
        )
        subprocess.run(
            [sys.executable, str(SCRIPTS / "auto_reglas.py"), "--generar"],
            capture_output=True,
            timeout=15,
            cwd=str(URA_ROOT),
            check=False,
        )

        f821_final = self.telemetria.f821_count()
        Conciencia.actualizar_proceso("orquestador", "idle")

        if time.monotonic() - inicio > MAX_CICLO_S:
            reporte["resultado"] = "TIMEOUT"
            reporte["razon"] = f"Sobrepasado {MAX_CICLO_S}s limite"
            self._fallos_consecutivos += 1
            return reporte

        if reporte.get("resultado") in ("ROLLBACK", "TIMEOUT"):
            self._fallos_consecutivos += 1
        else:
            self._fallos_consecutivos = 0

        reporte["f821_final"] = f821_final
        reporte["tiempo_total_s"] = round(time.monotonic() - inicio, 1)
        reporte["ram_final_mb"] = self.telemetria.hardware().get("ram_libre_mb", 0)

        return reporte
