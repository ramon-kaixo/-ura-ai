#!/usr/bin/env python3
"""Indexa todos los manuales .txt de docs/manuales en ChromaDB."""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.semantic_brain import SemanticBrain

logger = logging.getLogger("CargarManuales")


def main() -> None:
    """Indexa todos los archivos .txt del directorio de manuales."""
    brain = SemanticBrain()
    manual_dir = "/opt/ura/docs/manuales"
    if not os.path.exists(manual_dir):
        logger.warning("Directorio de manuales no existe: %s", manual_dir)
        return
    for filename in os.listdir(manual_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(manual_dir, filename)
            with open(filepath, encoding="utf-8") as fh:
                texto = fh.read()
            brain.indexar_manual("TPV", texto, filename)
            logger.info("Indexado: %s", filename)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
