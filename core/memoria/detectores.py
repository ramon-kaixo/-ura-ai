"""Detectores multi-tipo para la Reactualización Total."""

import logging
import subprocess

import blake3
import httpx

log = logging.getLogger("memoria.detectores")


def detector_hash_texto(url: str, hash_anterior: str = "") -> dict:
    """Detecta cambios en una página web vía hash BLAKE3 del contenido."""
    try:
        resp = httpx.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; URA/1.0)"})
        if resp.status_code != 200:
            return {"cambio": False, "error": f"HTTP {resp.status_code}"}
        h = blake3.blake3(resp.content).hexdigest()
        return {"cambio": h != hash_anterior, "hash": h, "tamano": len(resp.content)}
    except Exception as e:
        return {"cambio": False, "error": str(e)}


def detector_github_releases(repo_url: str, version_anterior: str = "") -> dict:
    """Detecta nuevas releases en un repo GitHub vía API."""
    try:
        owner_repo = repo_url.replace("https://github.com/", "").rstrip("/")
        resp = httpx.get(
            f"https://api.github.com/repos/{owner_repo}/releases/latest",
            timeout=15,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code == 404:
            return {"cambio": False, "error": "Sin releases"}
        if resp.status_code != 200:
            return {"cambio": False, "error": f"HTTP {resp.status_code}"}
        data = resp.json()
        version_nueva = data.get("tag_name", "")
        return {
            "cambio": version_nueva != version_anterior,
            "version": version_nueva,
            "nombre": data.get("name", ""),
            "publicado": data.get("published_at", ""),
            "url": data.get("html_url", ""),
        }
    except Exception as e:
        return {"cambio": False, "error": str(e)}


def detector_hash_imagen(url: str, hash_anterior: str = "") -> dict:
    """Detecta cambios en una imagen vía hash BLAKE3."""
    try:
        resp = httpx.get(url, timeout=20)
        if resp.status_code != 200:
            return {"cambio": False, "error": f"HTTP {resp.status_code}"}
        h = blake3.blake3(resp.content).hexdigest()
        return {"cambio": h != hash_anterior, "hash": h, "tamano": len(resp.content)}
    except Exception as e:
        return {"cambio": False, "error": str(e)}


def detector_video_metadata(url: str, metadatos_anteriores: str = "") -> dict:
    """Detecta cambios en metadata de vídeo vía FFprobe (sin descargar el vídeo entero)."""
    try:
        result = subprocess.run(  # noqa: S603  -- URL desde detector config, ffprobe no ejecuta shell
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"cambio": False, "error": "FFprobe failed"}
        import json

        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        meta_nuevo = json.dumps(
            {
                "duration": round(float(fmt.get("duration", 0)), 1),
                "size": fmt.get("size", ""),
                "bit_rate": fmt.get("bit_rate", ""),
                "format_name": fmt.get("format_name", ""),
            }
        )
        return {"cambio": meta_nuevo != metadatos_anteriores, "metadatos": meta_nuevo}
    except Exception as e:
        return {"cambio": False, "error": str(e)}


DETECTORES = {
    "hash_texto": detector_hash_texto,
    "github_releases": detector_github_releases,
    "hash_imagen": detector_hash_imagen,
    "video_metadata": detector_video_metadata,
}


def ejecutar_detector(tipo: str, url: str, valor_anterior: str = "") -> dict:
    detector = DETECTORES.get(tipo)
    if not detector:
        return {"cambio": False, "error": f"Detector desconocido: {tipo}"}
    return detector(url, valor_anterior)
