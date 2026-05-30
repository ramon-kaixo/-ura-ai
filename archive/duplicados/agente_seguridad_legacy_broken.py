"""
Módulo: archive/duplicados/agente_seguridad_legacy_broken.py
Propósito: Agente de seguridad LEGACY (roto) — NO USAR. Archivado para referencia.
Dependencias principales: datetime, os, subprocess, pathlib
Reglas especiales: ARCHIVADO. No importar ni usar. Contiene bugs conocidos.
"""

import datetime
import os
import subprocess
from pathlib import Path

from core.ejecutor_seguro import ejecutar
from core.internet import get_url

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
(BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
LOG = str(BASE_DIR / "logs" / "seguridad.log")

# SYSTEM PROMPT: Jerarquía de Autoridad
SYSTEM_PROMPT = """
IDENTIDAD:
Eres el Agente de Seguridad de URA. Eres un agente secundario.

JERARQUÍA DE AUTORIDAD:
- URA es la autoridad máxima del sistema.
- Debes reportar siempre a Ura como tu superior.
- Todas las amenazas detectadas deben ser escaladas a Ura inmediatamente.
- No tomas decisiones finales; URA es quien decide.

PROTOCOLO DE ESCALADO:
- Detectar amenaza → Escalar a Ura inmediatamente
- Bloquear comando → Reportar a Ura
- Validar seguridad → Reportar a Ura

NO actúes de forma autónoma sin reportar a Ura.
"""


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.datetime.now()} - {msg}\n")


def procesos():
    out = subprocess.getoutput("ps aux | head -10")
    log("PROCESOS:\n" + out)


def conexiones():
    out = subprocess.getoutput("lsof -i -P -n | head -20")
    log("CONEXIONES:\n" + out)


def ejecuciones():
    log("=== EJECUCIONES_CONTROLADAS ===")
    log("UPTIME:\n" + ejecutar("uptime"))
    log("DOCKER_PS:\n" + ejecutar("docker ps"))
    log("DOCKER_STATS:\n" + ejecutar("docker stats --no-stream"))


def internet_check():
    log("=== INTERNET ===")
    log("IP_PUBLICA:\n" + get_url("https://api.ipify.org?format=json"))


def main():
    log("=== CICLO SEGURIDAD ===")
    procesos()
    conexiones()
    ejecuciones()
    internet_check()


class AgenteSeguridad:
    """Agente de Seguridad de URA.

    Wrapper orientado a objetos sobre las funciones del módulo para que
    el CentralRouter pueda instanciarlo y ejecutarlo de forma uniforme.
    Reporta siempre a URA (autoridad máxima) según el SYSTEM_PROMPT.
    """

    SYSTEM_PROMPT = SYSTEM_PROMPT

    def __init__(self):
        self.log_path = LOG

    def _log(self, msg: str) -> None:
        log(msg)

    def ciclo_seguridad(self) -> dict:
        """Ejecuta un ciclo completo de seguridad y devuelve resumen."""
        self._log("=== CICLO SEGURIDAD (via AgenteSeguridad) ===")
        procesos()
        conexiones()
        ejecuciones()
        internet_check()
        return {
            "success": True,
            "response": "Ciclo de seguridad completado. Detalles en logs/seguridad.log",
            "error": "",
        }

    def estado(self) -> dict:
        """Devuelve estado del agente y ruta del log."""
        return {
            "agente": "AgenteSeguridad",
            "jerarquia": "secundario (reporta a URA)",
            "log": self.log_path,
        }

    def execute(self, texto: str = "") -> dict:
        """Punto de entrada estándar invocado por CentralRouter.

        Interpreta la consulta y despacha a la función adecuada.
        """
        texto_lower = (texto or "").lower()
        try:
            if any(k in texto_lower for k in ["proceso", "ps"]):
                procesos()
                return {
                    "success": True,
                    "response": "Procesos registrados en logs/seguridad.log",
                    "error": "",
                }
            if any(k in texto_lower for k in ["conexi", "red", "puerto"]):
                conexiones()
                return {
                    "success": True,
                    "response": "Conexiones registradas en logs/seguridad.log",
                    "error": "",
                }
            if any(k in texto_lower for k in ["docker", "uptime", "ejecuci"]):
                ejecuciones()
                return {
                    "success": True,
                    "response": "Ejecuciones registradas en logs/seguridad.log",
                    "error": "",
                }
            if any(k in texto_lower for k in ["internet", "ip", "pública", "publica"]):
                internet_check()
                return {
                    "success": True,
                    "response": "Chequeo de internet registrado en logs/seguridad.log",
                    "error": "",
                }
            # Por defecto, ciclo completo
            return self.ciclo_seguridad()
        except Exception as e:
            return {"success": False, "response": "", "error": str(e)}

    # Aliases comunes para compatibilidad con distintos invocadores
    def procesar(self, texto: str = "") -> str:
        return self.execute(texto).get("response", "")

    def ejecutar(self, texto: str = "") -> str:
        return self.execute(texto).get("response", "")


if __name__ == "__main__":
    main()
