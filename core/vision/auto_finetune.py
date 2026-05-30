#!/usr/bin/env python3
"""Auto fine-tune for vision models using camera snapshots."""

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("AutoFineTune")

URA_BASE = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = URA_BASE / "data" / "vision_dataset"
MODEL_PATH = URA_BASE / "models" / "yolo_platos.pt"
FRIGATE_API = os.getenv("FRIGATE_API", "http://localhost:5000/api/events")


def recopilar_imagenes(dias_atras: int = 7) -> list[str]:
    """Collects snapshots from Frigate camera events.

    Args:
        dias_atras: Number of days to look back for events.

    Returns:
        List of paths to collected images.
    """
    images_dir = DATASET_DIR / "images"
    labels_dir = DATASET_DIR / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    try:
        import requests

        since = int((datetime.now().timestamp()) - (dias_atras * 86400))
        resp = requests.get(f"{FRIGATE_API}?after={since}", timeout=10)
        events = resp.json()
        for event in events:
            event_id = event.get("id", "")
            if event_id:
                thumb_url = f"{FRIGATE_API}/events/{event_id}/thumbnail.jpg"
                thumb_resp = requests.get(thumb_url, timeout=10)
                if thumb_resp.status_code == 200:
                    img_path = images_dir / f"{event_id}.jpg"
                    with open(img_path, "wb") as fh:
                        fh.write(thumb_resp.content)
    except Exception as exc:
        logger.error("Error recopilando imagenes: %s", exc)

    return list(images_dir.glob("*.jpg"))


def entrenar() -> bool:
    """Trains or fine-tunes a YOLO model on the collected dataset.

    Returns:
        True if training completed, False otherwise.
    """
    try:
        from ultralytics import YOLO

        if not MODEL_PATH.exists():
            model = YOLO("yolov8n.pt")
        else:
            model = YOLO(str(MODEL_PATH))

        dataset_yaml = DATASET_DIR / "dataset.yaml"
        if not dataset_yaml.exists():
            dataset_yaml.write_text(
                f"path: {DATASET_DIR}\ntrain: images\nval: images\nnc: 10\nnames: ['plato1','plato2','plato3','plato4','plato5','plato6','plato7','plato8','plato9','plato10']\n"
            )

        device = "cpu"
        results = model.train(data=str(dataset_yaml), epochs=10, imgsz=640, device=device)
        model.save(str(MODEL_PATH))
        logger.info("Entrenamiento completado")
        return True
    except ImportError:
        logger.warning("ultralytics no instalado. Saltando fine-tune.")
        return False
    except Exception as exc:
        logger.error("Error en entrenamiento: %s", exc)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    imagenes = recopilar_imagenes()
    logger.info("Imagenes recopiladas: %d", len(imagenes))
    if imagenes:
        entrenar()
