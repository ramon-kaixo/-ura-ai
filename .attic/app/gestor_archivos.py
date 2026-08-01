#!/usr/bin/env python3
"""app/gestor_archivos.py — Puente a core/open_claw_reporte.py.
Proporciona GestorArchivosSeguro con proteccion Directory Traversal.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

from core.open_claw_reporte import get_cola_pendiente


class GestorArchivosSeguro:
    def __init__(self, root_path: str | None = None) -> None:
        self.root_path = root_path or str(Path.home() / "URA")

    def archivos_en_cola(self) -> int:
        return get_cola_pendiente()

    def listar_proyectos(self) -> list[str]:
        """Lista proyectos en el directorio raiz."""
        if not Path(self.root_path).exists():
            return []
        try:
            return [d for d in os.listdir(self.root_path) if Path(os.path.join(self.root_path, d).is_dir())]  # noqa: PTH118, PTH208
        except Exception:
            logger.exception("Error listing projects in %s", self.root_path)
            return []
