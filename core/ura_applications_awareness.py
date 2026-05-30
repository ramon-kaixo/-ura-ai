#!/usr/bin/env python3
"""
Conciencia de Aplicaciones Instaladas de URA - Nivel 24

URA tiene conocimiento de todas las aplicaciones instaladas:
- Aplicaciones de escritorio
- Servicios y daemons
- Metadatos de aplicaciones
"""

import json
import logging
import platform
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from core.ura_config import config
from core.ura_monitoring import get_ura_monitoring

logger = logging.getLogger(__name__)
monitor = get_ura_monitoring()

APPLICATIONS_AWARENESS_PATH = Path.home() / ".ura" / "applications_awareness.json"
APPLICATIONS_AWARENESS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ApplicationInfo:
    """Información de una aplicación."""

    name: str
    bundle_id: str
    path: str
    version: str
    category: str
    last_accessed: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ApplicationInfo":
        return cls(**data)


@dataclass
class ApplicationsInfo:
    """Información agregada del escaneo de aplicaciones."""

    scan_time: str
    os_name: str
    applications: list[ApplicationInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ApplicationsInfo":
        apps = [ApplicationInfo.from_dict(a) for a in data.get("applications", [])]
        return cls(
            scan_time=data["scan_time"],
            os_name=data["os_name"],
            applications=apps,
        )


class URAApplicationsAwareness:
    """Gestor de conciencia de aplicaciones de URA."""

    def __init__(self):
        self.applications = self._load_applications()

    def _load_applications(self) -> dict[str, ApplicationInfo]:
        """Cargar aplicaciones desde disco."""
        applications = {}
        if APPLICATIONS_AWARENESS_PATH.exists():
            try:
                with open(APPLICATIONS_AWARENESS_PATH) as f:
                    data = json.load(f)
                    applications = {
                        app["name"]: ApplicationInfo.from_dict(app)
                        for app in data.get("applications", [])
                    }
            except Exception as e:
                logger.error(f"Error cargando aplicaciones: {e}")

        # Si no hay aplicaciones, escanear
        if not applications:
            applications = self._scan_applications()

        return applications

    def _scan_applications(self) -> dict[str, ApplicationInfo]:
        """Escanear aplicaciones instaladas con límites de performance."""
        import time

        start = time.time()

        try:
            apps_config = config.get_apps_config()
            max_applications = apps_config["max_applications"]

            applications = []

            if platform.system() == "Darwin":  # macOS
                applications = self._scan_macos_applications(max_applications)
            elif platform.system() == "Windows":
                applications = self._scan_windows_applications(max_applications)
            else:  # Linux
                applications = self._scan_linux_applications(max_applications)

            duration = time.time() - start
            monitor.log_performance("applications_awareness", "scan_applications", duration)

            applications_info = ApplicationsInfo(
                scan_time=datetime.now().isoformat(),
                os_name=platform.system(),
                applications=applications,
            )

            with open(APPLICATIONS_AWARENESS_PATH, "w") as f:
                json.dump(asdict(applications_info), f, indent=2)

            return {app.name: app for app in applications}
        except Exception as e:
            monitor.log_error("applications_awareness", "ScanError", str(e))
            raise

    def _scan_macos_applications(self, max_applications: int) -> list[ApplicationInfo]:
        """Escanear aplicaciones de macOS."""
        applications = []

        # Escanear /Applications en macOS
        applications_dir = Path("/Applications")
        if applications_dir.exists():
            for app_path in applications_dir.glob("*.app"):
                try:
                    app_name = app_path.stem
                    bundle_id = self._get_bundle_id(app_path)
                    version = self._get_app_version(app_path)

                    app_info = ApplicationInfo(
                        name=app_name,
                        bundle_id=bundle_id,
                        path=str(app_path),
                        version=version,
                        category="desktop",
                        last_accessed=datetime.now().isoformat(),
                    )
                    applications.append(app_info)

                    if len(applications) >= max_applications:
                        break
                except Exception as e:
                    logger.warning(f"Error silencioso en applications_awareness.scan: {e}")
                    # fallback: continuar

        # Escanear aplicaciones de usuario
        user_applications = Path.home() / "Applications"
        if user_applications.exists():
            for app_path in user_applications.glob("*.app"):
                try:
                    app_name = app_path.stem
                    if app_name not in applications:
                        bundle_id = self._get_bundle_id(app_path)
                        version = self._get_app_version(app_path)

                        app_info = ApplicationInfo(
                            name=app_name,
                            bundle_id=bundle_id,
                            path=str(app_path),
                            version=version,
                            category="user",
                            last_accessed=datetime.now().isoformat(),
                        )
                        applications[app_name] = app_info
                except Exception as e:
                    logger.warning(f"Error silencioso en applications_awareness.scan_user: {e}")
                    # fallback: continuar

        return applications

    def _get_bundle_id(self, app_path: Path) -> str:
        """Obtener el bundle ID de una aplicación macOS."""
        try:
            result = subprocess.run(
                [
                    "defaults",
                    "read",
                    str(app_path / "Contents" / "Info.plist"),
                    "CFBundleIdentifier",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Error silencioso en applications_awareness.get_version: {e}")
            # fallback: continuar
        return "unknown"

    def _get_app_version(self, app_path: Path) -> str:
        """Obtener la versión de una aplicación macOS."""
        try:
            result = subprocess.run(
                [
                    "defaults",
                    "read",
                    str(app_path / "Contents" / "Info.plist"),
                    "CFBundleShortVersionString",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Error silencioso en applications_awareness.get_version2: {e}")
            # fallback: continuar
        return "unknown"

    def _save_applications(self):
        """Guardar aplicaciones a disco."""
        with open(APPLICATIONS_AWARENESS_PATH, "w") as f:
            json.dump(
                {"applications": [app.to_dict() for app in self.applications.values()]}, f, indent=2
            )

    def refresh_applications(self):
        """Actualizar lista de aplicaciones."""
        self.applications = self._scan_applications()
        self._save_applications()

    def get_applications_context(self) -> str:
        """Genera contexto de aplicaciones para el system prompt."""
        context_parts = ["CONCIENCIA DE APLICACIONES INSTALADAS:"]
        context_parts.append(f"- Total de aplicaciones: {len(self.applications)}")

        # Categorizar aplicaciones
        categories = {}
        for app in self.applications.values():
            if app.category not in categories:
                categories[app.category] = []
            categories[app.category].append(app.name)

        for category, apps in categories.items():
            context_parts.append(f"- {category.capitalize()}: {len(apps)} aplicaciones")

        # Aplicaciones principales
        main_apps = list(self.applications.keys())[:10]
        context_parts.append(f"- Aplicaciones principales: {', '.join(main_apps)}")

        return "\n".join(context_parts) + "\n"

    def get_application_info(self, app_name: str) -> ApplicationInfo | None:
        """Obtener información de una aplicación específica."""
        return self.applications.get(app_name)

    def launch_application(self, app_name: str) -> bool:
        """Lanzar una aplicación."""
        app_info = self.get_application_info(app_name)
        if not app_info:
            return False

        try:
            subprocess.run(["open", app_info.path], check=True)
            return True
        except Exception:
            return False

    def search_applications(self, query: str) -> list[str]:
        """Buscar aplicaciones por nombre."""
        query_lower = query.lower()
        return [name for name in self.applications if query_lower in name.lower()]


# Singleton
_ura_applications_awareness: URAApplicationsAwareness | None = None


def get_ura_applications_awareness() -> URAApplicationsAwareness:
    """Obtener el singleton de conciencia de aplicaciones de URA."""
    global _ura_applications_awareness
    if _ura_applications_awareness is None:
        _ura_applications_awareness = URAApplicationsAwareness()
    return _ura_applications_awareness


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    apps = get_ura_applications_awareness()

    print("Conciencia de aplicaciones instaladas creada")
    print(apps.get_applications_context())
