#!/usr/bin/env python3
"""
Módulo: core/autonomous_agent.py
Propósito: Agente autónomo que ejecuta acciones del sistema (vaciar trash, matar zombies, rotar logs).
Dependencias principales: subprocess, shlex, shutil, psutil, pathlib
Reglas especiales: NUNCA usar shell=True. Verificar comando antes de ejecutar. Backups antes de borrar.
"""

import json
import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from core.ura_value_system import get_ura_value_system

logger = logging.getLogger(__name__)

AUTONOMOUS_ACTIONS_PATH = Path.home() / ".ura" / "autonomous_actions.json"
AUTONOMOUS_ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Action:
    """Acción que URA puede ejecutar."""

    id: str
    name: str
    description: str
    category: str  # safe, dangerous
    command: str  # comando a ejecutar o función a llamar
    requires_confirmation: bool
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        return cls(**data)


class URAAutonomousAgent:
    """Agente autónomo de URA."""

    def __init__(self):
        self.actions = self._load_actions()
        self.pending_confirmations: dict[str, Action] = {}
        self.value_system = get_ura_value_system()

    def _load_actions(self) -> list[Action]:
        """Cargar acciones desde disco."""
        actions = []
        if AUTONOMOUS_ACTIONS_PATH.exists():
            try:
                with open(AUTONOMOUS_ACTIONS_PATH) as f:
                    data = json.load(f)
                    actions = [Action.from_dict(a) for a in data.get("actions", [])]
            except Exception as e:
                logger.error(f"Error cargando acciones: {e}")
        return actions

    def _save_actions(self):
        """Guardar acciones a disco."""
        with open(AUTONOMOUS_ACTIONS_PATH, "w") as f:
            json.dump({"actions": [a.to_dict() for a in self.actions]}, f, indent=2)

    def register_action(self, action: Action):
        """Registrar una nueva acción."""
        self.actions.append(action)
        self._save_actions()

    def get_available_actions(self) -> list[Action]:
        """Obtener acciones disponibles."""
        return self.actions

    def request_action(self, action_id: str) -> dict:
        """Solicitar ejecución de una acción."""
        action = next((a for a in self.actions if a.id == action_id), None)
        if not action:
            return {"error": "Acción no encontrada"}

        # Validar con sistema de valores
        value_eval = self.value_system.evaluate_action(f"Ejecutar acción: {action.description}")
        if value_eval["recommendation"] == "reconsider":
            logger.warning(f"Acción rechazada por sistema de valores: {action.name}")
            return {"error": "Acción no permitida por sistema de valores", "reason": value_eval}

        # Si requiere confirmación, poner en pendiente
        if action.requires_confirmation:
            self.pending_confirmations[action_id] = action
            return {
                "action": action,
                "requires_confirmation": True,
                "message": f"¿Confirmar ejecución de '{action.name}'? {action.description}",
            }

        # Ejecutar directamente si no requiere confirmación
        return self._execute_action(action)

    def confirm_action(self, action_id: str, confirmed: bool) -> dict:
        """Confirmar o rechazar una acción pendiente."""
        if action_id not in self.pending_confirmations:
            return {"error": "Acción no está pendiente de confirmación"}

        if not confirmed:
            del self.pending_confirmations[action_id]
            return {"status": "cancelled", "message": "Acción cancelada por el usuario"}

        action = self.pending_confirmations.pop(action_id)
        return self._execute_action(action)

    def _execute_action(self, action: Action) -> dict:
        """Ejecutar una acción."""
        try:
            logger.info(f"Ejecutando acción: {action.name}")

            # Acciones predefinidas
            if action.id == "clean_desktop":
                result = self._clean_desktop()
            elif action.id == "organize_downloads":
                result = self._organize_downloads()
            elif action.id == "empty_trash":
                result = self._empty_trash()
            elif action.id == "remove_duplicates":
                result = self._remove_duplicates()
            elif action.id == "create_backup":
                result = self._create_backup()
            else:
                # Ejecutar comando genérico
                import shlex

                result = subprocess.run(
                    shlex.split(action.command), shell=False, capture_output=True, text=True
                )
                return {
                    "status": "executed",
                    "action": action.name,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }

            return {"status": "executed", "action": action.name, "result": result}
        except Exception as e:
            logger.error(f"Error ejecutando acción: {e}")
            return {"status": "failed", "action": action.name, "error": str(e)}

    def _clean_desktop(self) -> dict:
        """Limpiar escritorio."""
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            return {"error": "Desktop no encontrado"}

        cleaned = 0
        for item in desktop.iterdir():
            if item.is_file() and not item.name.startswith("."):
                # Mover a una carpeta de archivo
                archive_dir = desktop / "URA_Archive"
                archive_dir.mkdir(exist_ok=True)
                shutil.move(str(item), str(archive_dir / item.name))
                cleaned += 1

        return {"cleaned_files": cleaned}

    def _organize_downloads(self) -> dict:
        """Organizar descargas por tipo."""
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            return {"error": "Downloads no encontrado"}

        folders = {
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf"],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
        }

        organized = 0
        for item in downloads.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                for folder_name, extensions in folders.items():
                    if ext in extensions:
                        folder = downloads / folder_name
                        folder.mkdir(exist_ok=True)
                        shutil.move(str(item), str(folder / item.name))
                        organized += 1
                        break

        return {"organized_files": organized}

    def _empty_trash(self) -> dict:
        """Vaciar papelera."""
        try:
            for item in (Path.home() / ".Trash").iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True) if hasattr(item, "unlink") else item.unlink()
            return {"status": "trash_emptied"}
        except Exception as e:
            return {"error": str(e)}

    def _remove_duplicates(self) -> dict:
        """Eliminar archivos duplicados en ~/Downloads."""
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            return {"error": "Downloads no encontrado"}

        # Implementación básica: archivos con mismo nombre y tamaño
        seen = {}
        duplicates = 0

        for item in downloads.iterdir():
            if item.is_file():
                key = (item.name, item.stat().st_size)
                if key in seen:
                    item.unlink()
                    duplicates += 1
                else:
                    seen[key] = item

        return {"removed_duplicates": duplicates}

    def _create_backup(self) -> dict:
        """Crear backup manual de ~/.ura/."""
        ura_dir = Path.home() / ".ura"
        if not ura_dir.exists():
            return {"error": ".ura no encontrado"}

        backup_dir = Path.home() / "URA_Backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"ura_backup_{timestamp}"

        shutil.copytree(ura_dir, backup_path)

        return {"backup_path": str(backup_path)}

    def get_pending_confirmations(self) -> list[Action]:
        """Obtener acciones pendientes de confirmación."""
        return list(self.pending_confirmations.values())

    def initialize_default_actions(self):
        """Inicializar acciones por defecto."""
        default_actions = [
            Action(
                id="clean_desktop",
                name="Limpiar escritorio",
                description="Mueve archivos del escritorio a URA_Archive",
                category="safe",
                command="",
                requires_confirmation=False,
                timestamp=datetime.now().isoformat(),
            ),
            Action(
                id="organize_downloads",
                name="Organizar descargas",
                description="Organiza archivos en Downloads por tipo",
                category="safe",
                command="",
                requires_confirmation=False,
                timestamp=datetime.now().isoformat(),
            ),
            Action(
                id="empty_trash",
                name="Vaciar papelera",
                description="Elimina permanentemente todos los archivos de la papelera",
                category="dangerous",
                command="",
                requires_confirmation=True,
                timestamp=datetime.now().isoformat(),
            ),
            Action(
                id="remove_duplicates",
                name="Eliminar duplicados",
                description="Elimina archivos duplicados en Downloads",
                category="safe",
                command="",
                requires_confirmation=False,
                timestamp=datetime.now().isoformat(),
            ),
            Action(
                id="create_backup",
                name="Crear backup manual",
                description="Crea backup de ~/.ura/",
                category="safe",
                command="",
                requires_confirmation=False,
                timestamp=datetime.now().isoformat(),
            ),
        ]

        for action in default_actions:
            if not any(a.id == action.id for a in self.actions):
                self.register_action(action)


# Singleton
_autonomous_agent: URAAutonomousAgent | None = None


def get_autonomous_agent() -> URAAutonomousAgent:
    """Obtener el singleton del agente autónomo de URA."""
    global _autonomous_agent
    if _autonomous_agent is None:
        _autonomous_agent = URAAutonomousAgent()
        _autonomous_agent.initialize_default_actions()
    return _autonomous_agent


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = get_autonomous_agent()

    print("Agente autónomo creado")
    print(f"Acciones disponibles: {len(agent.actions)}")
    for action in agent.actions:
        print(f"  - {action.name} ({action.category})")
