"""Archivo de texto limpio: guarda el texto extraído de cada fuente para siempre."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("memoria.archivo")

ARCHIVO_DIR = Path.home() / ".nervioso" / "archivo"


def guardar_texto(texto: str, metadatos: dict, hash_origen: str, fuente: str) -> Path | None:
    if not texto.strip():
        return None

    ARCHIVO_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    slug = fuente.split("//")[-1].split("?")[0].replace("/", "_")[:60] or "fuente"
    nombre = f"{slug}_{ts}_{hash_origen[:12]}.txt"
    ruta = ARCHIVO_DIR / nombre

    contenido = json.dumps({
        "fuente": fuente,
        "hash": hash_origen,
        "fecha_archivado": datetime.now(timezone.utc).isoformat(),
        "metadatos": metadatos,
    }, ensure_ascii=False, indent=2)

    ruta.write_text(contenido + "\n---\n" + texto, encoding="utf-8")
    log.info(f"Archivo: {len(texto)} chars → {ruta.name}")

    return ruta


def buscar_en_archivo(hash_origen: str) -> str | None:
    for f in ARCHIVO_DIR.glob("*.txt"):
        if hash_origen[:12] in f.name:
            parts = f.read_text(encoding="utf-8").split("\n---\n", 1)
            return parts[1] if len(parts) > 1 else None
    return None


def listar_archivo(limit: int = 20) -> list[dict]:
    files = sorted(ARCHIVO_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    resultados = []
    for f in files:
        try:
            header = f.read_text(encoding="utf-8").split("\n---\n")[0]
            meta = json.loads(header)
            meta["ruta"] = str(f)
            meta["tamano_bytes"] = f.stat().st_size
            resultados.append(meta)
        except Exception:
            pass
    return resultados
