#!/usr/bin/env python3
"""
ConflictDetector - Análisis de impacto preventivo antes de instalar paquetes.
"""

import json
import logging
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
INSTALL_LOG_PATH = Path.home() / ".ura" / "install_log.json"
INSTALL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
SANDBOX_IP = "192.168.56.10"


class ConflictDetector:
    """Detector de conflictos preventivo."""

    def __init__(self):
        self.install_log = self._load_install_log()

    def _load_install_log(self) -> list[dict]:
        if INSTALL_LOG_PATH.exists():
            try:
                with open(INSTALL_LOG_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error silencioso en conflict_detector.load_log: {e}")
                # fallback: archivo vacío
        return []

    def _save_install_log(self):
        with open(INSTALL_LOG_PATH, "w") as f:
            json.dump(self.install_log, f, indent=2)

    def _pip_freeze(self, python_exec: str = "python") -> dict:
        """Obtener pip freeze como dict {package: version}."""
        try:
            r = subprocess.run(
                [python_exec, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=30
            )
            packages = {}
            for line in r.stdout.splitlines():
                if "==" in line:
                    name, ver = line.split("==", 1)
                    packages[name.strip().lower()] = ver.strip()
            return packages
        except Exception as e:
            logger.warning(f"pip freeze falló: {e}")
            return {}

    def _check_sandbox_available(self) -> bool:
        """Verificar si el sandbox VirtualBox está disponible."""
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "2", SANDBOX_IP], capture_output=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    def _check_ports(self) -> list[int]:
        """Detectar puertos en uso."""
        try:
            r = subprocess.run(
                ["lsof", "-i", "-P", "-n"], capture_output=True, text=True, timeout=10
            )
            ports = set()
            for line in r.stdout.splitlines():
                match = re.search(r":(\d{4,5})\b", line)
                if match:
                    ports.add(int(match.group(1)))
            return sorted(ports)
        except Exception:
            return []

    def analyze_installation(self, package_name: str, version: str | None = None) -> dict:
        """Analizar instalación de paquete en sandbox antes de aplicar al sistema."""
        pkg_spec = f"{package_name}=={version}" if version else package_name
        result = {
            "package": package_name,
            "version": version,
            "timestamp": datetime.now().isoformat(),
            "sandbox_used": None,
            "conflicts": [],
            "new_dependencies": [],
            "tests_passed": None,
            "port_conflicts": [],
            "applied": False,
            "message": "",
        }

        freeze_before = self._pip_freeze()
        ports_before = set(self._check_ports())

        # ── Paso previo: Sandbox 2 (entrada) ──
        try:
            from core.sandbox_orchestrator import get_sandbox_orchestrator

            orch = get_sandbox_orchestrator()
            entrada_result = orch._run_sandbox_tests("entrada", target=pkg_spec)
            result["sandbox_entrada"] = entrada_result.get("success", False)
            if not entrada_result.get("success"):
                result["conflicts"].append("Sandbox 2 (entrada) rechazó el paquete")
                result["message"] = "❌ Sandbox 'entrada' rechazó el paquete. Instalación abortada."
                self.install_log.append(result)
                self._save_install_log()
                return result
        except Exception as e:
            logger.debug(f"Sandbox entrada no disponible: {e}")
            result["sandbox_entrada"] = None

        if self._check_sandbox_available():
            result["sandbox_used"] = "virtualbox"
            result["message"] = f"Sandbox VirtualBox disponible en {SANDBOX_IP} (simulación local)"
        else:
            result["sandbox_used"] = "venv_temporal"

        with tempfile.TemporaryDirectory() as tmpdir:  # nosec B108
            venv_path = Path(tmpdir) / "sandbox_venv"
            try:
                subprocess.run(
                    ["python", "-m", "venv", str(venv_path)], capture_output=True, timeout=60
                )
                venv_python = str(venv_path / "bin" / "python")

                # Instalar paquete en venv
                install_result = subprocess.run(
                    [venv_python, "-m", "pip", "install", pkg_spec],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                if install_result.returncode != 0:
                    result["conflicts"].append(f"Instalación falló: {install_result.stderr[:200]}")
                    result["message"] = (
                        f"❌ Instalación falló en sandbox: {install_result.stderr[:200]}"
                    )
                    self.install_log.append(result)
                    self._save_install_log()
                    return result

                # Freeze después
                freeze_after = self._pip_freeze(venv_python)
                new_deps = []
                conflicts = []
                for pkg, ver in freeze_after.items():
                    if pkg not in freeze_before:
                        new_deps.append(f"{pkg}=={ver}")
                    elif freeze_before[pkg] != ver:
                        conflicts.append(f"{pkg}: {freeze_before[pkg]} → {ver}")

                result["new_dependencies"] = new_deps
                result["conflicts"].extend(conflicts)

                # Ejecutar tests
                try:
                    test_result = subprocess.run(
                        [venv_python, "-m", "pytest", "tests/", "-q", "--tb=no", "-x"],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    result["tests_passed"] = test_result.returncode == 0
                    if not result["tests_passed"]:
                        result["conflicts"].append(f"Tests fallaron: {test_result.stdout[-200:]}")
                except Exception as e:
                    result["tests_passed"] = False
                    result["conflicts"].append(f"Error en tests: {e}")

                # Puertos
                ports_after = set(self._check_ports())
                new_ports = ports_after - ports_before
                if new_ports:
                    result["port_conflicts"] = sorted(new_ports)

            except Exception as e:
                result["conflicts"].append(f"Excepción en sandbox: {e}")
                result["message"] = f"❌ Error: {e}"
                self.install_log.append(result)
                self._save_install_log()
                return result

        # Decisión final
        if result["conflicts"] or result["tests_passed"] is False:
            result["message"] = (
                f"❌ Conflictos detectados ({len(result['conflicts'])}). "
                f"Instalación NO aplicada. Sandbox revertido."
            )
        else:
            # Instalar en el sistema real
            try:
                real_install = subprocess.run(
                    ["pip", "install", pkg_spec], capture_output=True, text=True, timeout=180
                )
                if real_install.returncode == 0:
                    result["applied"] = True
                    # Añadir a requirements.txt
                    self._add_to_requirements(package_name, version)
                    result["message"] = (
                        f"✅ {pkg_spec} instalado correctamente. Añadido a requirements.txt."
                    )

                    # Validación post-instalación en Sandbox 1 (farina)
                    try:
                        from core.sandbox_orchestrator import get_sandbox_orchestrator

                        orch = get_sandbox_orchestrator()
                        farina_result = orch._run_sandbox_tests("farina", target=pkg_spec)
                        result["sandbox_farina"] = farina_result.get("success", False)
                        # Registrar como cambio importante → activa ciclo acelerado
                        orch.register_critical_change(
                            "package_install",
                            reason=f"Instalado {pkg_spec}",
                            metadata={"package": package_name, "version": version},
                        )
                    except Exception as e:
                        logger.debug(f"Sandbox farina no disponible: {e}")
                        result["sandbox_farina"] = None
                else:
                    result["message"] = f"❌ Instalación real falló: {real_install.stderr[:200]}"
            except Exception as e:
                result["message"] = f"❌ Error instalando: {e}"

        self.install_log.append(result)
        self._save_install_log()
        return result

    def _add_to_requirements(self, package_name: str, version: str | None = None):
        """Añadir paquete a requirements.txt."""
        entry = f"{package_name}=={version}" if version else package_name
        if REQUIREMENTS_PATH.exists():
            with open(REQUIREMENTS_PATH) as f:
                existing = f.read()
            if package_name.lower() in existing.lower():
                return
            with open(REQUIREMENTS_PATH, "a") as f:
                f.write(f"\n{entry}\n")
        else:
            with open(REQUIREMENTS_PATH, "w") as f:
                f.write(f"{entry}\n")

    def post_mortem_check(self) -> list[dict]:
        """Revisar logs de instalación para conflictos post-mortem."""
        recent = self.install_log[-20:]
        issues = []
        for entry in recent:
            if entry.get("conflicts") and entry.get("applied"):
                issues.append(
                    {
                        "package": entry["package"],
                        "conflicts": entry["conflicts"],
                        "timestamp": entry["timestamp"],
                    }
                )
        return issues


_conflict_detector: ConflictDetector | None = None


def get_conflict_detector() -> ConflictDetector:
    global _conflict_detector
    if _conflict_detector is None:
        _conflict_detector = ConflictDetector()
    return _conflict_detector
