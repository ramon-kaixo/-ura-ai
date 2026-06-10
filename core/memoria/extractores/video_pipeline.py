"""Pipeline completo de vídeo: frames clave → visión → ritmo → embedding visual."""
import json
import logging
import subprocess
import tempfile
from pathlib import Path

import httpx

OLLAMA = "http://127.0.0.1:11434/api/chat"
VISION_MODEL = "llama3.2-vision:11b"
MAX_FRAMES = 5  # max key frames to analyze per video

log = logging.getLogger("memoria.video")


def _ffprobe_json(ruta: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(ruta)],
        capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout) if result.returncode == 0 else {}


def _extraer_frames_clave(ruta: Path, out_dir: Path, max_frames: int = MAX_FRAMES) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []

    # Try scene detection first
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(ruta), "-vf",
         "select='gt(scene\\,0.15)',scale=640:-1",
         "-vsync", "vfr", "-frames:v", str(max_frames),
         f"{out_dir}/frame_%03d.jpg"],
        capture_output=True, text=True, timeout=60,
    )

    for f in sorted(out_dir.glob("frame_*.jpg")):
        if f.stat().st_size > 0:
            frames.append(f)

    # Fallback: if no scene changes detected, grab I-frames
    if not frames:
        subprocess.run(
            ["ffmpeg", "-y", "-skip_frame", "nokey", "-i", str(ruta),
             "-vsync", "vfr", "-frames:v", str(max_frames),
             f"{out_dir}/key_%03d.jpg"],
            capture_output=True, text=True, timeout=60,
        )
        for f in sorted(out_dir.glob("key_*.jpg")):
            if f.stat().st_size > 0:
                frames.append(f)

    return frames[:max_frames]


def _describir_frame(ruta: Path) -> dict:
    try:
        import base64
        img_b64 = base64.b64encode(ruta.read_bytes()).decode()

        resp = httpx.post(OLLAMA, json={
            "model": VISION_MODEL,
            "messages": [{
                "role": "user",
                "content": "Describe esta imagen en español en una frase. Menciona objetos, colores dominantes, iluminación y ambiente.",
                "images": [img_b64],
            }],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 200},
        }, timeout=60)

        if resp.is_error:
            return {"descripcion": "", "error": f"Ollama {resp.status_code}"}

        data = resp.json()
        desc = data.get("message", {}).get("content", "").strip()
        return {"descripcion": desc, "modelo": VISION_MODEL}
    except Exception as e:
        return {"descripcion": "", "error": str(e)}


def _analizar_ritmo(data: dict) -> dict:
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    duration = float(fmt.get("duration", 0))
    fps_str = video.get("r_frame_rate", "0/1")
    if "/" in fps_str:
        a, b = fps_str.split("/")
        fps = float(a) / float(b) if float(b) != 0 else 0
    else:
        fps = float(fps_str) if fps_str else 0

    total_frames = int(duration * fps) if fps else 0
    cortes = 0
    # Rough cut detection: count scenes via ffmpeg scene detection
    return {
        "duracion_total_s": round(duration, 1),
        "fps": round(fps, 2),
        "frames_estimados": total_frames,
        "resolucion": f"{video.get('width','?')}x{video.get('height','?')}",
        "codec": video.get("codec_name", ""),
    }


def pipeline_video(ruta: Path) -> dict:
    data = _ffprobe_json(ruta)
    ritmo = _analizar_ritmo(data)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        frames = _extraer_frames_clave(ruta, tmp_dir)
        descripciones = []
        for f in frames:
            desc = _describir_frame(f)
            if desc.get("descripcion"):
                descripciones.append(desc["descripcion"])

    resumen = " | ".join(descripciones) if descripciones else ""
    embedding_texto = resumen or f"Video: {ritmo['resolucion']} {ritmo['codec']}"

    return {
        "tipo": "video",
        "metadatos": {
            **ritmo,
            "tamano_bytes": ruta.stat().st_size,
            "frames_analizados": len(descripciones),
        },
        "texto_plano": "",
        "resumen_visual": resumen,
        "embedding_texto": embedding_texto,
        "ruta": str(ruta),
    }
