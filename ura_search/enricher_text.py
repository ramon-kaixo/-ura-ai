#!/usr/bin/env python3
"""enricher_text.py — Enriquece texto con IA local (ASUS GX10).

Lee de la cola de .nervioso/ura_search/cola/ (ya procesado por agentes),
usa deepseek-coder:6.7b para resumir y nomic-embed-text para embeddings.
Solo procesa items que el agente marcó como relevantes.

Uso:
  python3 -m ura_search.enricher_text --all
  python3 -m ura_search.enricher_text --categoria legal
"""
import argparse, json, logging, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import urllib.request

LOG_PATH = Path(__file__).parent / "data" / "enricher.log"
COLA_DIR = Path.home() / ".nervioso" / "ura_search" / "cola"
OUTPUT_DIR = Path.home() / ".nervioso" / "ura_search" / "enriquecido"
LOG_PATH.parent.mkdir(exist_ok=True); OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("enricher")

OLLAMA_URL = "http://localhost:11434"
MODEL_TEXT = "deepseek-coder:6.7b"
MODEL_EMBED = "nomic-embed-text"


def _ollama_complete(prompt: str, model: str = MODEL_TEXT, max_tokens: int = 512) -> Optional[str]:
    """Llama a un modelo de Ollama para completar texto."""
    try:
        data = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": max_tokens}}).encode()
        req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        log.warning("Ollama error (%s): %s", model, e)
        return None


def _ollama_embed(text: str) -> Optional[list[float]]:
    """Genera embedding con nomic-embed-text."""
    try:
        data = json.dumps({"model": MODEL_EMBED, "input": text[:3000]}).encode()
        req = urllib.request.Request(f"{OLLAMA_URL}/api/embed", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("embeddings", [None])[0]
    except Exception as e:
        log.warning("Embedding error: %s", e)
        return None


def _leer_resultado_agente(categoria: str) -> list[dict]:
    """Lee los archivos .meta.json procesados por los agentes Docker."""
    items = []
    cat_dir = COLA_DIR / categoria
    if not cat_dir.exists():
        return items
    for meta_file in sorted(cat_dir.glob("*.meta.json")):
        try:
            data = json.loads(meta_file.read_text())
            # Buscar el .html o .txt asociado
            base = meta_file.stem.replace(".meta", "")
            content_file = list(cat_dir.glob(f"{base}.*"))
            contenido = ""
            if content_file:
                contenido = content_file[0].read_text(encoding="utf-8", errors="replace")[:5000]
            data["contenido"] = contenido
            items.append(data)
        except Exception as e:
            log.debug("Error leyendo %s: %s", meta_file.name, e)
    log.info("  %s: %d items en cola", categoria, len(items))
    return items


def enriquecer(categoria: str, force: bool = False) -> int:
    """Procesa todos los items de una categoría."""
    items = _leer_resultado_agente(categoria)
    output_cat = OUTPUT_DIR / categoria
    output_cat.mkdir(exist_ok=True, parents=True)
    procesados = 0

    for item in items:
        sha = item.get("url", item.get("sha256", "unknown"))[:16]
        output_file = output_cat / f"{sha}.enriched.json"
        if output_file.exists() and not force:
            continue

        contenido = item.get("contenido", "") or item.get("transcripcion", "")
        if not contenido or len(contenido) < 50:
            continue

        log.info("  → %s (%d chars)", item.get("titulo", sha)[:50], len(contenido))

        # 1. Resumen con deepseek
        resumen = _ollama_complete(f"Resume este texto en 3 líneas:\n\n{contenido[:2000]}")
        time.sleep(0.5)  # evitar saturar Ollama

        # 2. Embedding con nomic
        embedding = _ollama_embed(contenido[:2000])

        # 3. Clasificación
        categoria_texto = _ollama_complete(
            f"Clasifica este texto en UNA categoría: legal, cocina, diseño, programacion, hosteleria, general.\n\n{contenido[:1000]}")

        resultado = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "fuente": item.get("fuente", item.get("source", "")),
            "titulo": item.get("titulo", ""),
            "url": item.get("url", ""),
            "categoria_asignada": (categoria_texto or "general").strip().lower(),
            "resumen": resumen or "",
            "embedding": embedding[:8] if embedding else [],  # solo primeros 8 para vista previa
            "tiene_embedding": embedding is not None,
            "original": contenido[:500],
        }
        output_file.write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
        procesados += 1

    return procesados


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--categoria", help="Categoría a procesar")
    p.add_argument("--all", action="store_true", help="Procesar todas las categorías")
    p.add_argument("--force", action="store_true", help="Reprocesar aunque ya exista")
    args = p.parse_args()

    categorias = ["legal", "diseno", "programacion", "hosteleria", "video", "general"]
    if args.categoria:
        categorias = [args.categoria]

    total = 0
    for cat in categorias:
        log.info("Procesando: %s", cat)
        p = enriquecer(cat, force=args.force)
        total += p

    log.info("✅ Total enriquecidos: %d", total)

if __name__ == "__main__":
    main()
