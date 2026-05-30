#!/usr/bin/env python3
"""
core/repair/git_snapshots.py - Git snapshot functionality for auto-repair
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def create_git_snapshot(instance, message: str = "Auto-repair snapshot") -> str:
    """Crear snapshot Git antes de reparación"""
    try:
        project_root = Path(__file__).parent.parent.parent

        # Inicializar git si no existe
        if not (project_root / ".git").exists():
            subprocess.run(["git", "init"], cwd=project_root, capture_output=True, timeout=10)
            logger.info("Git inicializado")

        # Crear commit con estado actual
        subprocess.run(["git", "add", "."], cwd=project_root, capture_output=True, timeout=30)

        commit_hash = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if commit_hash.returncode == 0:
            # Obtener hash del commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            hash_value = result.stdout.strip()
            logger.info(f"Snapshot Git creado: {hash_value}")
            return hash_value
        else:
            logger.warning("No hay cambios para commitear")
            return ""

    except Exception as e:
        logger.warning(f"Error creando snapshot Git: {e}")
        return ""
