#!/usr/bin/env python3
"""
Sistema de Versionado - URA App
Gestiona versiones del sistema con semver y rollback
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path


class VersionManager:
    """Gestor de versiones del sistema"""

    def __init__(self):
        self.ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")
        self.version_file = self.ura_app_path / "config" / "version.json"
        self.history_file = self.ura_app_path / "config" / "version_history.json"
        self.current_version = self._load_version()
        self.history = self._load_history()

    def _load_version(self) -> dict:
        """Cargar versión actual"""
        if self.version_file.exists():
            with open(self.version_file) as f:
                return json.load(f)
        return {
            "major": 1,
            "minor": 0,
            "patch": 0,
            "pre_release": "",
            "build_metadata": "",
            "timestamp": datetime.now().isoformat(),
        }

    def _load_history(self) -> list[dict]:
        """Cargar historial de versiones"""
        if self.history_file.exists():
            with open(self.history_file) as f:
                return json.load(f)
        return []

    def _save_version(self):
        """Guardar versión actual"""
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        self.current_version["timestamp"] = datetime.now().isoformat()
        with open(self.version_file, "w") as f:
            json.dump(self.current_version, f, indent=2)

    def _save_history(self):
        """Guardar historial de versiones"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "w") as f:
            json.dump(self.history, f, indent=2)

    def get_version_string(self) -> str:
        """Obtener versión como string semver"""
        v = self.current_version
        version = f"{v['major']}.{v['minor']}.{v['patch']}"

        if v["pre_release"]:
            version += f"-{v['pre_release']}"

        if v["build_metadata"]:
            version += f"+{v['build_metadata']}"

        return version

    def increment_major(self):
        """Incrementar versión major (cambios incompatibles)"""
        self.current_version["major"] += 1
        self.current_version["minor"] = 0
        self.current_version["patch"] = 0
        self._add_to_history("major")
        self._save_version()
        self._save_history()

    def increment_minor(self):
        """Incrementar versión minor (nuevas features compatibles)"""
        self.current_version["minor"] += 1
        self.current_version["patch"] = 0
        self._add_to_history("minor")
        self._save_version()
        self._save_history()

    def increment_patch(self):
        """Incrementar versión patch (bug fixes)"""
        self.current_version["patch"] += 1
        self._add_to_history("patch")
        self._save_version()
        self._save_history()

    def set_pre_release(self, pre_release: str):
        """Establecer versión pre-release (alpha, beta, rc)"""
        self.current_version["pre_release"] = pre_release
        self._save_version()

    def set_build_metadata(self, metadata: str):
        """Establecer metadata de build"""
        self.current_version["build_metadata"] = metadata
        self._save_version()

    def _add_to_history(self, change_type: str):
        """Añadir versión al historial"""
        version_entry = {
            "version": self.get_version_string(),
            "change_type": change_type,
            "timestamp": datetime.now().isoformat(),
            "git_commit": self._get_git_commit(),
        }
        self.history.insert(0, version_entry)

        # Mantener solo últimos 50 versiones
        if len(self.history) > 50:
            self.history = self.history[:50]

    def _get_git_commit(self) -> str:
        """Obtener commit actual de git"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.ura_app_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except:
            return ""

    def list_history(self) -> list[dict]:
        """Listar historial de versiones"""
        return self.history

    def rollback_to_version(self, version_string: str) -> bool:
        """Rollback a versión específica"""
        # Buscar versión en historial
        version_entry = None
        for entry in self.history:
            if entry["version"] == version_string:
                version_entry = entry
                break

        if not version_entry:
            print(f"Versión {version_string} no encontrada en historial")
            return False

        # Restaurar versión
        parts = version_string.split(".")
        if len(parts) >= 3:
            self.current_version["major"] = int(parts[0])
            self.current_version["minor"] = int(parts[1])
            self.current_version["patch"] = int(parts[2].split("-")[0].split("+")[0])
            self._save_version()
            print(f"Rollback a versión {version_string} completado")
            return True

        return False


if __name__ == "__main__":
    manager = VersionManager()

    print(f"Versión actual: {manager.get_version_string()}")
    print("\nHistorial de versiones:")

    for entry in manager.list_history()[:10]:
        print(f"  - {entry['version']} ({entry['change_type']}) - {entry['timestamp']}")
