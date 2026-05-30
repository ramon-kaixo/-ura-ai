#!/usr/bin/env python3
"""Agente de Instagram — Publica contenido via Graph API de Meta."""

import json
import subprocess
import sys
import os
import time
import random
from pathlib import Path

BASE = Path.home() / "URA" / "ura_ia_1972"
API_VERSION = "v22.0"


def crear_contenedor_media(ig_user_id: str, media_url: str, caption: str, token: str) -> str:
    payload = json.dumps({"image_url": media_url, "caption": caption, "access_token": token})
    result = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            f"https://graph.facebook.com/{API_VERSION}/{ig_user_id}/media",
            "-d",
            payload,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        return json.loads(result.stdout).get("id", "")
    return ""


def publicar_media(ig_user_id: str, creation_id: str, token: str) -> bool:
    result = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            f"https://graph.facebook.com/{API_VERSION}/{ig_user_id}/media_publish",
            "-d",
            f"creation_id={creation_id}&access_token={token}",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0 and "error" not in result.stdout.lower()


if __name__ == "__main__":
    IG_USER_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    if not IG_USER_ID or not ACCESS_TOKEN:
        print("Configurar INSTAGRAM_BUSINESS_ACCOUNT_ID e INSTAGRAM_ACCESS_TOKEN")
        sys.exit(1)
    contenido_dir = BASE / "docs" / "marketing"
    posts = sorted(contenido_dir.glob("post_instagram_*.json"))
    for post_file in posts[:2]:
        with open(post_file) as f:
            post_data = json.load(f)
        caption = (
            post_data.get("texto", "Nuevo contenido de URA")
            + "\n\n"
            + " ".join(post_data.get("hashtags", []))
        )
        media_url = post_data.get("imagen_url", "")
        if not media_url:
            continue
        print(f"  Publicando: {caption[:50]}...")
        creation_id = crear_contenedor_media(IG_USER_ID, media_url, caption, ACCESS_TOKEN)
        if creation_id:
            time.sleep(random.randint(5, 15))
            if publicar_media(IG_USER_ID, creation_id, ACCESS_TOKEN):
                print(f"    OK publicado: {creation_id}")
            else:
                print("    Error al publicar")
        time.sleep(random.randint(30, 60))
    print("OK Agente de Instagram completado")
