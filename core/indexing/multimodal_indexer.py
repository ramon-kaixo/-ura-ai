#!/usr/bin/env python3
"""Multimodal indexer — processes PDFs, images, and videos into ChromaDB."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.memory.semantic_brain import SemanticBrain

try:
    import cv2
    from PIL import Image
    import pytesseract
    from pypdf import PdfReader
    import pdfplumber
except ImportError as exc:
    print(f"Faltan dependencias multimodales: {exc}")
    sys.exit(1)

MANUAL_DIR = os.getenv(
    "MANUAL_DIR", str(Path(__file__).resolve().parent.parent.parent / "docs" / "manuales")
)
brain = SemanticBrain()


def extraer_texto_pdf(ruta: str) -> str:
    """Extracts text from PDF files using pdfplumber with pypdf fallback.

    Args:
        ruta: Path to the PDF file.

    Returns:
        Extracted text content.
    """
    texto: list[str] = []
    try:
        with pdfplumber.open(ruta) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    texto.append(page_text)
        if not texto:
            reader = PdfReader(ruta)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    texto.append(page_text)
    except Exception as exc:
        print(f"Error leyendo PDF {ruta}: {exc}")
    return "\n".join(texto)


def extraer_texto_imagen(ruta: str) -> str:
    """Extracts text from images using Tesseract OCR.

    Args:
        ruta: Path to the image file.

    Returns:
        Extracted text content.
    """
    img = Image.open(ruta)
    return pytesseract.image_to_string(img, lang="spa")


def extraer_texto_video(ruta: str, frame_interval: int = 5) -> str:
    """Extracts text from video frames at regular intervals.

    Args:
        ruta: Path to the video file.
        frame_interval: Seconds between frame captures.

    Returns:
        Extracted text from all sampled frames.
    """
    texto_total: list[str] = []
    try:
        cap = cv2.VideoCapture(ruta)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        for t in range(0, int(duration), frame_interval):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(gray, lang="spa")
            if text.strip():
                texto_total.append(f"[Frame {t}s] {text}")
        cap.release()
    except Exception as exc:
        print(f"Error procesando video {ruta}: {exc}")
    return "\n".join(texto_total)


def procesar_archivo(ruta: str, app_name: str) -> None:
    """Processes a single file and indexes its content.

    Args:
        ruta: Path to the file.
        app_name: Application or category name for indexing.
    """
    ext = os.path.splitext(ruta)[1].lower()
    texto = ""
    if ext == ".pdf":
        texto = extraer_texto_pdf(ruta)
    elif ext in {".png", ".jpg", ".jpeg"}:
        texto = extraer_texto_imagen(ruta)
    elif ext in {".mp4", ".mov", ".avi"}:
        texto = extraer_texto_video(ruta)
    elif ext == ".txt":
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
    else:
        return

    if texto:
        secciones = [s.strip() for s in texto.split("\n\n") if s.strip()]
        for i, sec in enumerate(secciones):
            brain.indexar_manual(app_name, sec, f"seccion_{i}_{os.path.basename(ruta)}")
        print(f"Indexado {ruta} ({len(secciones)} secciones)")


def main() -> None:
    """Walks the manual directory and processes all supported files."""
    for root, dirs, files in os.walk(MANUAL_DIR):
        for file in files:
            ruta = os.path.join(root, file)
            app_name = os.path.basename(root) if root != MANUAL_DIR else "manual_general"
            procesar_archivo(ruta, app_name)


if __name__ == "__main__":
    main()
