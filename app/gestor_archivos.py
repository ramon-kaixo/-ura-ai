#!/usr/bin/env python3
"""app/gestor_archivos.py — Puente a core/open_claw_reporte.py.
Proporciona GestorArchivosSeguro con proteccion Directory Traversal.
"""
from __future__ import annotations
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.open_claw_reporte import COLA_DIR, get_cola_pendiente

class GestorArchivosSeguro:
    def __init__(self, root_path: str | None = None) -> None:
        self.root_path = root_path or str(Path.home() / "URA")

    def archivos_en_cola(self) -> int:
        return get_cola_pendiente()

    def listar_proyectos(self) -> list[str]:
        """Lista proyectos en el directorio raiz."""
        if not os.path.exists(self.root_path):
            return []
        try:
            return [d for d in os.listdir(self.root_path)
                    if os.path.isdir(os.path.join(self.root_path, d))]
        except: return []
