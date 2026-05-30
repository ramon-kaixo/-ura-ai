#!/usr/bin/env python3
"""Anonymizes logs, images, and episodic data to protect privacy."""

import logging
import os
import re
from pathlib import Path


logger = logging.getLogger("Anonymizer")

URA_BASE = Path(__file__).resolve().parent.parent
PATHS: list[str] = [
    str(URA_BASE / "logs"),
    str(URA_BASE / "data" / "episodic_db"),
    str(URA_BASE / "knowledge"),
]
FACE_PIXEL_SIZE = 8
PLATE_PATTERN = re.compile(r"[A-Z0-9]{6,8}")
NAMES: list[str] = [
    "Juan",
    "Maria",
    "Pedro",
    "Laia",
    "URA",
    "Ana",
    "Luis",
    "Carlos",
    "Sofia",
    "Diego",
]


def anonymize_text(text: str) -> str:
    """Replaces personal names and license plates with placeholders.

    Args:
        text: Input text to anonymize.

    Returns:
        Anonymized text.
    """
    text = PLATE_PATTERN.sub("[MATRICULA]", text)
    for name in NAMES:
        text = re.sub(rf"\b{name}\b", "[EMPLEADO]", text, flags=re.IGNORECASE)
    return text


def anonymize_image(image_path: str) -> None:
    """Pixelates faces in an image to protect identity.

    Args:
        image_path: Path to the image file.
    """
    try:
        import cv2
        import face_recognition

        img = cv2.imread(image_path)
        if img is None:
            return
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb)
        for top, right, bottom, left in face_locations:
            face = img[top:bottom, left:right]
            face = cv2.resize(face, (FACE_PIXEL_SIZE, FACE_PIXEL_SIZE))
            face = cv2.resize(face, (right - left, bottom - top), interpolation=cv2.INTER_NEAREST)
            img[top:bottom, left:right] = face
        cv2.imwrite(image_path, img)
        logger.debug("Anonimizada imagen: %s", image_path)
    except ImportError:
        logger.warning("face_recognition o cv2 no instalado. Saltando imagen: %s", image_path)
    except Exception as exc:
        logger.error("Error anonimizando imagen %s: %s", image_path, exc)


def anonymize_logs() -> None:
    """Walks configured paths and anonymizes all text and image files."""
    for base_path in PATHS:
        if not os.path.exists(base_path):
            continue
        for root, dirs, files in os.walk(base_path):
            for file in files:
                full = os.path.join(root, file)
                if file.endswith((".txt", ".log", ".json", ".md")):
                    try:
                        with open(full, encoding="utf-8") as fh:
                            content = fh.read()
                        new_content = anonymize_text(content)
                        if new_content != content:
                            with open(full, "w", encoding="utf-8") as fh:
                                fh.write(new_content)
                    except Exception as exc:
                        logger.error("Error procesando %s: %s", full, exc)
                elif file.endswith((".png", ".jpg", ".jpeg")):
                    anonymize_image(full)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    anonymize_logs()
    logger.info("Anonimizacion completada.")
