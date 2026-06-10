import json
import subprocess
from pathlib import Path


def _ffprobe(ruta: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(ruta),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return {}


def extraer_video(ruta: Path) -> dict:
    data = _ffprobe(ruta)
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    video_info = {}
    if video_streams:
        v = video_streams[0]
        video_info = {
            "codec": v.get("codec_name", ""),
            "resolucion": f"{v.get('width','?')}x{v.get('height','?')}",
            "fps": v.get("r_frame_rate", ""),
            "bitrate_video": v.get("bit_rate", ""),
        }

    audio_info = {}
    if audio_streams:
        a = audio_streams[0]
        audio_info = {
            "codec_audio": a.get("codec_name", ""),
            "canales": a.get("channels", 0),
            "sample_rate": a.get("sample_rate", ""),
            "bitrate_audio": a.get("bit_rate", ""),
        }

    return {
        "tipo": "video",
        "metadatos": {
            "duracion_seg": round(float(fmt.get("duration", 0)), 1),
            "formato": fmt.get("format_name", ""),
            "bitrate_total": fmt.get("bit_rate", ""),
            "tamano_bytes": int(fmt.get("size", 0)),
            "pistas_video": len(video_streams),
            "pistas_audio": len(audio_streams),
            **video_info,
            **audio_info,
        },
        "texto_plano": "",
        "ruta": str(ruta),
    }


def extraer_audio(ruta: Path) -> dict:
    return extraer_video(ruta) | {"tipo": "audio"}
