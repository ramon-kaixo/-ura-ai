"""SnapshotService — snapshots delta del pipeline de mejora continua.

Genera snapshots con los hashes del sistema_map.json de .nervioso para la
comparación delta de ciclos. La implementación es local desde el retiro de
openclaw_firmador (c6d60c8c), sin dependencias externas.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SnapshotService:
    """Servicio de snapshots delta.

    Único punto de acceso a los snapshots delta desde el pipeline.
    """

    def __init__(self, nervioso: Path, log_fn: Callable[..., Any] | None = None) -> None:
        self._nervioso = nervioso
        self._log = log_fn or (lambda msg: None)

    def save(self, label: str = "ultimo_ciclo") -> Path | None:
        """Guarda un snapshot delta del estado actual.

        Devuelve la ruta del snapshot o None si falla (degradación explícita).
        """
        try:
            index = self._load_index()
            snapshot = self._snapshot_files(index)
            delta_dir = self._nervioso / "delta_snapshots"
            delta_dir.mkdir(parents=True, exist_ok=True)
            path = delta_dir / f"{label}.json"
            payload = {
                "label": label,
                "files": snapshot,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._log(f"Delta snapshot guardado: {path}")
            return path
        except Exception as e:
            self._log(f"Delta snapshot falló: {e}")
            return None

    def exists(self) -> bool:
        """Verifica si existe un snapshot previo."""
        return (self._nervioso / "delta_snapshots" / "ultimo_ciclo.json").exists()

    def clean(self) -> None:
        """Limpia todos los snapshots delta (modo profundo)."""
        delta_dir = self._nervioso / "delta_snapshots"
        if delta_dir.exists():
            import shutil

            shutil.rmtree(delta_dir, ignore_errors=True)
            self._log("Snapshots delta limpiados")

    def _load_index(self) -> dict[str, Any]:
        """Carga el sistema_map.json de .nervioso (vacío si no existe)."""
        map_file = self._nervioso / "sistema_map.json"
        if not map_file.exists():
            return {}
        return json.loads(map_file.read_text(encoding="utf-8"))

    @staticmethod
    def _snapshot_files(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Hashes de los nodos no ESPEJO/ZOMBIE para la comparación futura."""
        deps: dict[str, Any] = index.get("dependency_graph", {})
        return {
            rel: {
                "blake2b": node.get("checksum_blake2b_8", ""),
                "size": node.get("allocation_bytes", 0),
                "mtime": node.get("posix_timestamps", {}).get("st_mtime", 0),
            }
            for rel, node in deps.items()
            if "ESPEJO" not in node.get("pipeline_state", "") and "ZOMBIE" not in node.get("pipeline_state", "")
        }
