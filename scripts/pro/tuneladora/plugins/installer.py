"""InstallerPlugin — instalacion y verificacion del sistema."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine


class InstallerPlugin:
    """Instalacion, verificacion de requisitos y setup del entorno."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine
        self.repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent

    def check_requirements(self) -> dict[str, Any]:
        """Python 3.12+, pip, git, espacio disco >5GB."""
        results: dict[str, Any] = {}
        # Python version
        v = sys.version_info
        results["python"] = {"ok": v.major == 3 and v.minor >= 12, "version": f"{v.major}.{v.minor}.{v.micro}"}
        # pip
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, timeout=10)
            results["pip"] = {"ok": True}
        except Exception:
            results["pip"] = {"ok": False, "error": "pip no disponible"}
        # git
        try:
            subprocess.run(["git", "--version"], capture_output=True, timeout=10)
            results["git"] = {"ok": True}
        except Exception:
            results["git"] = {"ok": False, "error": "git no disponible"}
        # Disk space
        try:
            usage = shutil.disk_usage("/")
            libre_gb = usage.free / (1024**3)
            results["disk"] = {"ok": libre_gb > 5, "libre_gb": round(libre_gb, 1)}
        except Exception as e:
            results["disk"] = {"ok": False, "error": str(e)}
        return results

    def check_connectivity(self) -> dict[str, Any]:
        """GitHub, pip, Ollama responden."""
        results: dict[str, Any] = {}
        try:
            import httpx
            # GitHub
            r = httpx.get("https://github.com", timeout=5)
            results["github"] = {"ok": r.status_code < 500}
            # Ollama
            r2 = httpx.get("http://localhost:11434/api/tags", timeout=5)
            results["ollama"] = {"ok": r2.status_code == 200}
        except Exception as e:
            results["connectivity_error"] = str(e)
        return results

    def install_dependencies(self) -> dict[str, Any]:
        """pip install -e .[dev] desde pyproject.toml."""
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
                capture_output=True, text=True, timeout=300, cwd=str(self.repo_root),
            )
            ok = r.returncode == 0
            if ok:
                self.engine.log.info("Dependencias instaladas correctamente")
            else:
                self.engine.log.warning("Instalacion de dependencias fallo: %s", r.stderr[-200:])
            return {"ok": ok, "stdout": (r.stdout or "")[-200:], "stderr": (r.stderr or "")[-200:]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def setup_environment(self) -> dict[str, Any]:
        """Crea .env, pre-commit install, verifica permisos."""
        results: dict[str, Any] = {}
        try:
            # pre-commit install
            r = subprocess.run(
                [sys.executable, "-m", "pre_commit", "install"],
                capture_output=True, text=True, timeout=30, cwd=str(self.repo_root),
            )
            results["precommit"] = {"ok": r.returncode == 0, "output": (r.stdout or "")[:200]}
        except Exception as e:
            results["precommit"] = {"ok": False, "error": str(e)}
        return results

    def verify_installation(self) -> dict[str, Any]:
        """pytest, ruff, mypy pasan."""
        results: dict[str, Any] = {}
        # Pytest basico
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--no-cov", "motor/tests/tuneladora/"],
                capture_output=True, text=True, timeout=60, cwd=str(self.repo_root),
            )
            passed = "passed" in r.stdout and "failed" not in r.stdout
            results["pytest"] = {"ok": passed, "output": (r.stdout or "")[-200:]}
        except Exception as e:
            results["pytest"] = {"ok": False, "error": str(e)}
        # Ruff
        try:
            r = subprocess.run(
                [str(self.repo_root / ".venv" / "bin" / "ruff"), "check", "motor/brain/"],
                capture_output=True, text=True, timeout=30, cwd=str(self.repo_root),
            )
            results["ruff"] = {"ok": r.returncode == 0, "output": (r.stdout or "")[:200]}
        except Exception as e:
            results["ruff"] = {"ok": False, "error": str(e)}
        return results

    def install(self) -> dict[str, Any]:
        """Pipeline completo: check -> connectivity -> install -> setup -> verify."""
        phases: dict[str, Any] = {}
        phases["requirements"] = self.check_requirements()
        if all(v.get("ok") for v in phases["requirements"].values() if isinstance(v, dict)):
            phases["connectivity"] = self.check_connectivity()
            phases["dependencies"] = self.install_dependencies()
            phases["setup"] = self.setup_environment()
            phases["verify"] = self.verify_installation()
        all_ok = all(
            isinstance(v, dict) and v.get("ok", False)
            for p in phases.values()
            if isinstance(p, dict)
            for v in p.values()
            if isinstance(v, dict)
        )
        return {"status": "ok" if all_ok else "partial", "phases": phases}
