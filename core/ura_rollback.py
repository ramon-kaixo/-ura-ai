#!/usr/bin/env python3
"""
Sistema de Rollback de URA

Guarda snapshots del estado de cada nivel y permite revertir cambios:
- Snapshots periódicos del estado
- Revertir cambios si un nivel causa problemas
- Sistema de versionado para configuraciones
"""

import json
import logging
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Snapshot:
    """Snapshot del estado de un nivel."""

    snapshot_id: str
    level_name: str
    timestamp: str
    data_path: str  # Ruta al archivo de datos
    metadata: dict

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        return cls(**data)


class URARollback:
    """Sistema de rollback de URA."""

    def __init__(self, config_path: str | Path = None):
        """Inicializar rollback.

        Args:
            config_path: Ruta al directorio de configuración
        """
        if config_path is None:
            config_path = Path.home() / ".ura" / "rollback"
        self.config_path = Path(config_path)
        self.config_path.mkdir(parents=True, exist_ok=True)
        self.snapshots = self._load_snapshots()

    def _load_snapshots(self) -> list[Snapshot]:
        """Cargar snapshots desde disco."""
        snapshots = []
        snapshots_file = self.config_path / "snapshots.json"
        if snapshots_file.exists():
            try:
                with open(snapshots_file) as f:
                    data = json.load(f)
                    snapshots = [Snapshot.from_dict(s) for s in data.get("snapshots", [])]
            except Exception as e:
                logger.error(f"Error cargando snapshots: {e}")
        return snapshots

    def _save_snapshots(self):
        """Guardar snapshots a disco."""
        snapshots_file = self.config_path / "snapshots.json"
        with open(snapshots_file, "w") as f:
            json.dump({"snapshots": [s.to_dict() for s in self.snapshots]}, f, indent=2)

    def create_snapshot(self, level_name: str, data_path: Path, metadata: dict = None) -> str:
        """Crear snapshot del estado de un nivel."""
        if metadata is None:
            metadata = {}

        # Copiar archivo de datos
        snapshot_id = f"snapshot_{datetime.now().timestamp()}"
        snapshot_dir = self.config_path / snapshot_id
        snapshot_dir.mkdir(exist_ok=True)

        if data_path.exists():
            shutil.copy2(data_path, snapshot_dir / data_path.name)

        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            level_name=level_name,
            timestamp=datetime.now().isoformat(),
            data_path=str(snapshot_dir / data_path.name),
            metadata=metadata,
        )

        self.snapshots.append(snapshot)

        # Mantener solo últimos 3 snapshots por nivel
        self.keep_last_three(level_name)

        self._save_snapshots()
        return snapshot_id

    def keep_last_three(self, level_name: str):
        """Mantener solo las 3 últimas copias de seguridad de un nivel."""
        level_snapshots = [s for s in self.snapshots if s.level_name == level_name]
        if len(level_snapshots) > 3:
            level_snapshots.sort(key=lambda s: s.timestamp)
            to_remove = level_snapshots[:-3]
            for snap in to_remove:
                snap_dir = self.config_path / snap.snapshot_id
                if snap_dir.exists():
                    shutil.rmtree(snap_dir)
                self.snapshots.remove(snap)
            logger.info(
                f"keep_last_three({level_name}): eliminados {len(to_remove)} snapshots antiguos"
            )

    def restore_snapshot(self, snapshot_id: str, level_name: str) -> bool:
        """Restaurar snapshot de un nivel."""
        snapshot = next(
            (
                s
                for s in self.snapshots
                if s.snapshot_id == snapshot_id and s.level_name == level_name
            ),
            None,
        )

        if not snapshot:
            return False

        # Restaurar archivo de datos
        data_path = Path.home() / ".ura" / f"{level_name}.json"
        snapshot_path = Path(snapshot.data_path)

        if snapshot_path.exists():
            shutil.copy2(snapshot_path, data_path)
            return True

        return False

    def get_latest_snapshot(self, level_name: str) -> Snapshot | None:
        """Obtener el snapshot más reciente de un nivel."""
        level_snapshots = [s for s in self.snapshots if s.level_name == level_name]

        if not level_snapshots:
            return None

        return max(level_snapshots, key=lambda s: s.timestamp)

    def get_rollback_context(self) -> str:
        """Genera contexto de rollback para el system prompt."""
        if not self.snapshots:
            return ""

        context_parts = ["SISTEMA DE ROLLBACK:"]
        context_parts.append(f"- Snapshots totales: {len(self.snapshots)}")

        # Niveles con snapshots
        levels_with_snapshots = {s.level_name for s in self.snapshots}
        context_parts.append(f"- Niveles con snapshots: {len(levels_with_snapshots)}")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_rollback: URARollback | None = None


def get_ura_rollback(config_path: str | Path = None) -> URARollback:
    """Obtener el singleton del sistema de rollback de URA."""
    global _ura_rollback
    if _ura_rollback is None:
        _ura_rollback = URARollback(config_path=config_path)
    return _ura_rollback


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rollback = URARollback()

    # Prueba
    snapshot_id = rollback.create_snapshot("emotions", Path.home() / ".ura" / "emotions.json")
    print("Sistema de rollback creado")
    print(rollback.get_rollback_context())
