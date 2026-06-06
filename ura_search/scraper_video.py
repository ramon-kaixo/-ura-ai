#!/usr/bin/env python3
"""scraper_video.py — Descarga transcripciones de YouTube vía yt-dlp.

Uso:
  python3 -m ura_search.scraper_video --url https://youtube.com/watch?v=...
  python3 -m ura_search.scraper_video --batch lista.txt
"""
import argparse, json, logging, re, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
COLA_DIR = Path.home() / ".nervioso" / "ura_search" / "cola" / "video"
LOG_PATH = DATA_DIR / "scraper_video.log"

DATA_DIR.mkdir(exist_ok=True); COLA_DIR.mkdir(exist_ok=True, parents=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("scraper_video")

def extract_transcript(url: str) -> dict:
    """Extrae transcripción de un video de YouTube usando yt-dlp.
    
    Returns dict con: titulo, canal, duracion, transcripcion, thumbnail
    """
    t0 = time.time()
    result = {"url": url, "status": "error", "titulo": "", "transcripcion": ""}
    
    try:
        # Obtener metadatos + transcripción
        cmd = [
            "/home/ramon/.local/bin/yt-dlp", "--skip-download", "--write-auto-subs", "--sub-langs", "es,-en",
            "--convert-subs", "srt", "--output", str(DATA_DIR / "%(id)s.%(ext)s"),
            "--print", "%(title)s",
            "--print", "%(channel)s",
            "--print", "%(duration)s",
            "--print", "%(thumbnail)s",
            url
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        lines = r.stdout.strip().split("\n")
        if len(lines) >= 4:
            result["titulo"] = lines[0]
            result["canal"] = lines[1]
            result["duracion"] = int(lines[2]) if lines[2].isdigit() else 0
            result["thumbnail"] = lines[3]
        
        # Buscar archivo SRT generado
        video_id = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]+)', url)
        if video_id:
            vid = video_id.group(1)
            srt_file = list(DATA_DIR.glob(f"{vid}*.{vid}*.srt")) or list(DATA_DIR.glob(f"{vid}*.srt"))
            if srt_file:
                text = srt_file[0].read_text(encoding="utf-8", errors="replace")
                # Limpiar SRT: quitar numeros, timestamps, lineas vacias
                lines = [l.strip() for l in text.split("\n") if l.strip() and not l.strip().isdigit() and "-->" not in l]
                result["transcripcion"] = " ".join(lines)
                srt_file[0].unlink(missing_ok=True)
        
        result["status"] = "ok" if result["transcripcion"] else "no_transcript"
        result["elapsed"] = round(time.time() - t0, 2)
        
        if result["transcripcion"]:
            # Guardar en cola
            sha = __import__("hashlib").sha256(result["transcripcion"].encode()).hexdigest()[:16]
            (COLA_DIR / f"{sha}.txt").write_text(result["transcripcion"], encoding="utf-8")
            (COLA_DIR / f"{sha}.meta.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            log.info("✅ %s — %s (%s)", result["titulo"][:60], url, f"{result['elapsed']}s")
    
    except subprocess.TimeoutExpired:
        log.error("⏰ Timeout: %s", url)
        result["error"] = "timeout"
    except FileNotFoundError:
        log.error("❌ yt-dlp no instalado. Ejecuta: pip install yt-dlp")
        result["error"] = "/home/ramon/.local/bin/yt-dlp not found"
    except Exception as e:
        log.error("❌ %s: %s", url, e)
        result["error"] = str(e)
    
    return result

def extract_batch(urls: list[str], max_workers: int = 2) -> list[dict]:
    """Procesa una lista de URLs."""
    results = []
    for url in urls[:max_workers]:
        r = extract_transcript(url)
        results.append(r)
    return results

def main():
    p = argparse.ArgumentParser(description="URA-Search: scraper de video")
    p.add_argument("--url", help="URL de YouTube")
    p.add_argument("--batch", help="Archivo con URLs (una por línea)")
    args = p.parse_args()
    
    if args.url:
        r = extract_transcript(args.url)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    elif args.batch:
        urls = Path(args.batch).read_text().strip().split("\n")
        rr = extract_batch(urls)
        ok = sum(1 for r in rr if r["status"] == "ok")
        print(f"\nProcesadas: {len(rr)}. OK: {ok}")
    else:
        p.print_help()

if __name__ == "__main__":
    main()
