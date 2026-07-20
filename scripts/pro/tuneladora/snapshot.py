"""SnapshotService — adaptador para openclaw_firmador.delta_snapshot.

Desacopla PipelineEngine de la librería concreta.
Si en el futuro cambia openclaw_firmador, solo se modifica este archivo.
"""

from __future__ import annotations

from pathlib import Path


class SnapshotService:
    """Servicio de snapshots delta.

    Único punto de acceso a delta_snapshot desde el pipeline.
    """

    def __init__(self, nervioso: Path, log_fn: callable | None = None) -> None:
        self._nervioso = nervioso
        self._log = log_fn or (lambda msg: None)

    def save(self, label: str = "ultimo_ciclo") -> Path | None:
        """Guarda un snapshot delta del estado actual."""
        try:
            from openclaw_firmador import delta_snapshot

            result = delta_snapshot(label)
            self._log(f"Delta snapshot guardado: {result}")
            return Path(result) if result else None
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
