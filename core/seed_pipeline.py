#!/usr/bin/env python3
"""
Pipeline de semillas para entrenamiento N3.

Gestiona semillas para entrenamiento masivo, permitiendo agregar,
marcar como usadas y obtener semillas pendientes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("seed_pipeline")

# Configuración
TOSHIBA_PATH = Path("/Volumes/TOSHIBA_NUEVO/URA_entrenamiento")
SEEDS_FILE = TOSHIBA_PATH / "seeds.txt"
USED_SEEDS_FILE = TOSHIBA_PATH / "seeds_usadas.json"


class SeedPipeline:
    """Pipeline de semillas para entrenamiento N3."""

    def __init__(self):
        """Inicializa el pipeline."""
        self.seeds_file = SEEDS_FILE
        self.used_seeds_file = USED_SEEDS_FILE

    def load_seeds(self) -> list[str]:
        """Carga semillas desde archivo."""
        if not self.seeds_file.exists():
            logger.warning(f"Archivo de semillas no encontrado: {self.seeds_file}")
            return []

        with open(self.seeds_file, encoding="utf-8") as f:
            seeds = [line.strip() for line in f if line.strip()]

        logger.info(f"Cargadas {len(seeds)} semillas")
        return seeds

    def save_seeds(self, seeds: list[str]):
        """Guarda semillas en archivo."""
        # Verificar montaje de Toshiba
        if not TOSHIBA_PATH.exists():
            raise RuntimeError(f"Toshiba no montado en {TOSHIBA_PATH}")

        # Crear directorio si no existe
        self.seeds_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.seeds_file, "w", encoding="utf-8") as f:
            for seed in seeds:
                f.write(f"{seed}\n")
        logger.info(f"Guardadas {len(seeds)} semillas")

    def load_used_seeds(self) -> set[str]:
        """Carga semillas usadas desde JSON."""
        if not self.used_seeds_file.exists():
            return set()

        with open(self.used_seeds_file, encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("used_seeds", []))

    def save_used_seeds(self, used_seeds: set[str]):
        """Guarda semillas usadas en JSON."""
        # Verificar montaje de Toshiba
        if not TOSHIBA_PATH.exists():
            raise RuntimeError(f"Toshiba no montado en {TOSHIBA_PATH}")

        # Crear directorio si no existe
        self.used_seeds_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.used_seeds_file, "w", encoding="utf-8") as f:
            json.dump({"used_seeds": list(used_seeds)}, f, indent=2, ensure_ascii=False)

    def get_pending_seeds(self) -> list[str]:
        """Obtiene semillas pendientes (no usadas)."""
        all_seeds = self.load_seeds()
        used_seeds = self.load_used_seeds()

        pending = [seed for seed in all_seeds if seed not in used_seeds]
        logger.info(f"Semillas pendientes: {len(pending)} de {len(all_seeds)}")

        return pending

    def mark_as_used(self, seeds: list[str]):
        """Marca semillas como usadas."""
        used_seeds = self.load_used_seeds()
        used_seeds.update(seeds)
        self.save_used_seeds(used_seeds)
        logger.info(f"Marcadas {len(seeds)} semillas como usadas")

    def add_seeds(self, seeds: list[str]):
        """Agrega nuevas semillas al pipeline."""
        existing_seeds = self.load_seeds()
        new_seeds = set(seeds) - set(existing_seeds)

        if new_seeds:
            all_seeds = existing_seeds + list(new_seeds)
            self.save_seeds(all_seeds)
            logger.info(f"Agregadas {len(new_seeds)} nuevas semillas")
        else:
            logger.info("No se agregaron semillas nuevas (ya existen)")


# Singleton
_pipeline_instance: SeedPipeline | None = None


def get_seed_pipeline() -> SeedPipeline:
    """Obtener singleton del pipeline de semillas."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = SeedPipeline()
    return _pipeline_instance


def reset_seed_pipeline() -> None:
    """Resetear singleton."""
    global _pipeline_instance
    _pipeline_instance = None


if __name__ == "__main__":
    # Test del pipeline
    logging.basicConfig(level=logging.INFO)
    pipeline = get_seed_pipeline()
    pending = pipeline.get_pending_seeds()
    print(f"Semillas pendientes: {len(pending)}")
