#!/usr/bin/env python3
"""
AGENTE INSTALADOR OPENCODE — Instala dependencias y configura entornos.

Gestiona la instalación de paquetes, configuración de entornos virtuales,
verificación de dependencias y preparación de entornos de desarrollo
para proyectos gestionados por OpenCode.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SISTEMA = Path(__file__).parent.parent
LOG_DIR = SISTEMA / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG = LOG_DIR / "instalador_opencode.log"
DB_PATH = SISTEMA / "board.db"

GESTORES_PAQUETES = {
    "python": {
        "check": "python3 --version",
        "install": "pip3 install",
        "list": "pip3 list --format=json",
        "venv": "python3 -m venv",
    },
    "node": {
        "check": "node --version",
        "install": "npm install",
        "list": "npm list --json",
        "venv": None,
    },
    "rust": {
        "check": "rustc --version",
        "install": "cargo install",
        "list": "cargo install --list",
        "venv": None,
    },
}

DEPENDENCIAS_URA = [
    "flask",
    "requests",
    "sqlite3",
    "psutil",
]


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    logger.info(msg)


def _run(cmd: str, timeout: int = 60) -> dict:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Timeout", "code": -1}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "code": -1}


class AgenteInstaladorOpenCode:
    """Instala dependencias y configura entornos para OpenCode."""

    def __init__(self) -> None:
        self.proyecto_root = SISTEMA
        self.instalaciones_log: list[dict] = []

    def verificar_entorno(self) -> dict:
        """Verifica el estado del entorno: Python, Node, herramientas."""
        _log("Verificando entorno de desarrollo...")
        resultado = {"timestamp": datetime.now().isoformat(), "herramientas": {}}

        for nombre, cmds in GESTORES_PAQUETES.items():
            check = _run(cmds["check"])
            resultado["herramientas"][nombre] = {
                "disponible": check["ok"],
                "version": check["stdout"] if check["ok"] else None,
            }

        for tool in ["git", "curl", "ssh", "docker", "ollama"]:
            check = _run(f"which {tool}")
            resultado["herramientas"][tool] = {
                "disponible": check["ok"],
                "path": check["stdout"] if check["ok"] else None,
            }

        _log(
            f"Entorno verificado: {sum(1 for v in resultado['herramientas'].values() if v['disponible'])}/{len(resultado['herramientas'])} herramientas disponibles"
        )
        return resultado

    def instalar_dependencias(self, proyecto_path: str, gestor: str = "python") -> dict:
        """Instala dependencias de un proyecto."""
        path = Path(proyecto_path)
        _log(f"Instalando dependencias en {path} con {gestor}")

        if gestor == "python":
            req_file = path / "requirements.txt"
            if req_file.exists():
                result = _run(f"pip3 install -r {req_file}")
                _log(f"pip install: {'OK' if result['ok'] else 'FALLO'}")
                return {"ok": result["ok"], "gestor": "pip", "detalle": result}

            pyproject = path / "pyproject.toml"
            if pyproject.exists():
                result = _run(f"cd {path} && pip3 install -e .")
                _log(f"pip install -e: {'OK' if result['ok'] else 'FALLO'}")
                return {"ok": result["ok"], "gestor": "pip", "detalle": result}

        elif gestor == "node":
            pkg = path / "package.json"
            if pkg.exists():
                result = _run(f"cd {path} && npm install")
                _log(f"npm install: {'OK' if result['ok'] else 'FALLO'}")
                return {"ok": result["ok"], "gestor": "npm", "detalle": result}

        return {"ok": False, "error": f"No se encontró archivo de dependencias en {path}"}

    def crear_entorno_virtual(self, nombre: str, path: str | None = None) -> dict:
        """Crea un entorno virtual Python."""
        venv_path = Path(path) if path else SISTEMA / "venvs" / nombre
        _log(f"Creando venv: {venv_path}")

        venv_path.parent.mkdir(parents=True, exist_ok=True)
        result = _run(f"python3 -m venv {venv_path}")

        if result["ok"]:
            _log(f"Venv creado: {venv_path}")
            return {
                "ok": True,
                "path": str(venv_path),
                "activate": f"source {venv_path}/bin/activate",
            }

        _log(f"Error creando venv: {result['stderr']}")
        return {"ok": False, "error": result["stderr"]}

    def configurar_opencode(
        self, modelo: str = "qwen2.5-coder:14b", ollama_url: str = "http://localhost:11434"
    ) -> dict:
        """Configura OpenCode para usar Ollama local."""
        config_dir = Path.home() / ".config" / "opencode"
        auth_dir = Path.home() / ".local" / "share" / "opencode"
        config_dir.mkdir(parents=True, exist_ok=True)
        auth_dir.mkdir(parents=True, exist_ok=True)

        config = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "ollama-local": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Ollama Local",
                    "options": {"baseURL": f"{ollama_url}/v1"},
                    "models": {modelo: {"name": modelo, "tool_call": True}},
                }
            },
        }

        auth = {"ollama-local": {"type": "api", "key": "local"}}

        config_file = config_dir / "opencode.json"
        auth_file = auth_dir / "auth.json"

        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        with open(auth_file, "w") as f:
            json.dump(auth, f, indent=2)

        _log(f"OpenCode configurado: modelo={modelo}, url={ollama_url}")
        return {"ok": True, "config": str(config_file), "auth": str(auth_file)}

    def verificar_ollama(self, url: str = "http://localhost:11434") -> dict:
        """Verifica que Ollama está corriendo y lista modelos."""
        result = _run(f"curl -s {url}/api/tags")
        if not result["ok"]:
            return {"ok": False, "error": "Ollama no responde"}

        try:
            data = json.loads(result["stdout"])
            modelos = [m["name"] for m in data.get("models", [])]
            _log(f"Ollama OK: {len(modelos)} modelos disponibles")
            return {"ok": True, "modelos": modelos}
        except (json.JSONDecodeError, KeyError):
            return {"ok": False, "error": "Respuesta inválida de Ollama"}

    def ejecutar(self, tarea: str = "verificar") -> dict:
        """Punto de entrada principal del agente."""
        _log(f"Ejecutando tarea: {tarea}")

        if tarea == "verificar":
            return self.verificar_entorno()
        elif tarea == "instalar":
            return self.instalar_dependencias(str(SISTEMA))
        elif tarea == "opencode":
            return self.configurar_opencode()
        elif tarea == "ollama":
            return self.verificar_ollama()

        return {"error": f"Tarea desconocida: {tarea}"}


def ejecutar(tarea: str = "verificar") -> dict:
    """Función de entrada para el orquestador."""
    agente = AgenteInstaladorOpenCode()
    return agente.ejecutar(tarea)


if __name__ == "__main__":
    import sys

    tarea = sys.argv[1] if len(sys.argv) > 1 else "verificar"
    resultado = ejecutar(tarea)
    print(json.dumps(resultado, indent=2, default=str))
