#!/usr/bin/env python3
"""Agente de Resenas de Google — Monitoriza, analiza y responde resenas."""

import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, UTC

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"
OUTPUT_DIR = BASE / "docs" / "resenas"


def listar_resenas(account_id: str, location_id: str, token: str) -> list:
    result = subprocess.run(
        [
            "curl",
            "-s",
            "-H",
            f"Authorization: Bearer {token}",
            f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        return json.loads(result.stdout).get("reviews", [])
    return []


def analizar_resena(review: dict) -> dict:
    prompt = f"""Eres el gerente de un bar de copas en Pamplona. Analiza esta resena de Google y genera una respuesta profesional y cercana. Indica el sentimiento (positivo, negativo, neutro) y prioridad (alta, media, baja).

Resena: {review.get("comment", "Sin comentario")}
Puntuacion: {review.get("starRating", "N/A")} estrellas
Autor: {review.get("reviewer", {}).get("displayName", "Anonimo")}

Responde UNICAMENTE con JSON: {{"sentimiento": "...", "prioridad": "...", "respuesta": "..."}}"""
    payload = json.dumps(
        {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    try:
        r = subprocess.run(
            ["curl", "-s", GX10_URL, "-d", payload], capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            return json.loads(json.loads(r.stdout)["message"]["content"])
    except:
        pass
    return {"sentimiento": "neutro", "prioridad": "baja", "respuesta": "Gracias por tu opinion."}


def responder_resena(
    account_id: str, location_id: str, review_id: str, respuesta: str, token: str
) -> bool:
    result = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "PUT",
            f"https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews/{review_id}/reply",
            "-H",
            f"Authorization: Bearer {token}",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps({"comment": respuesta}),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode == 0


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    account_id = os.getenv("GOOGLE_BUSINESS_ACCOUNT_ID", "")
    location_id = os.getenv("GOOGLE_BUSINESS_LOCATION_ID", "")
    token = os.getenv("GOOGLE_ACCESS_TOKEN", "")
    if not account_id or not location_id or not token:
        print(
            "Configurar GOOGLE_BUSINESS_ACCOUNT_ID, GOOGLE_BUSINESS_LOCATION_ID, GOOGLE_ACCESS_TOKEN"
        )
        sys.exit(1)
    resenas = listar_resenas(account_id, location_id, token)
    informe = {
        "fecha": datetime.now(UTC).isoformat(),
        "total": len(resenas),
        "procesadas": [],
    }
    for resena in resenas:
        analisis = analizar_resena(resena)
        if analisis.get("prioridad") in ("alta", "media"):
            analisis["respondida"] = responder_resena(
                account_id, location_id, resena["reviewId"], analisis["respuesta"], token
            )
        else:
            analisis["respondida"] = False
        informe["procesadas"].append(analisis)
    output = OUTPUT_DIR / f"informe_resenas_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output, "w") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    print(f"OK  {len(resenas)} resenas en {output.name}")
