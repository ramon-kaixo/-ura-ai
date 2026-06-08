#!/usr/bin/env python3
"""vision_provider.py — Motor de visión con fallback Ollama → Gemini API."""

import base64, json, logging, os, time
from pathlib import Path
from typing import Optional
import httpx

log = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_VISION_MODEL = "llama3.2-vision:11b"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
ENV_FILE = Path(os.path.expanduser("~/.config/opencode/.env"))


def _load_gemini_key() -> Optional[str]:
    if not ENV_FILE.exists():
        return None
    try:
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'").strip('"')
                if key and key != "TU_API_KEY_AQUI":
                    return key
    except Exception:
        pass
    return None


def analyze_image(image_b64: str, prompt: str = "Describe this image briefly in English.", timeout: int = 120) -> dict:
    start = time.time()
    result = _try_ollama(image_b64, prompt, timeout // 2)
    if result and "error" not in result:
        result["provider"] = "ollama"
        result["timing"] = round(time.time() - start, 2)
        log.info("Vision via Ollama: %.2fs", result["timing"])
        return result
    log.warning("Ollama vision failed: %s", result.get("error", "unknown"))
    api_key = _load_gemini_key()
    if not api_key:
        return {"provider": "none", "error": "Ollama failed and no Gemini API key", "description": "", "timing": round(time.time() - start, 2)}
    result = _try_gemini(image_b64, prompt, api_key, timeout)
    if result and "error" not in result:
        result["provider"] = "gemini"
        result["timing"] = round(time.time() - start, 2)
        log.info("Vision via Gemini API: %.2fs", result["timing"])
        return result
    return {"provider": "none", "error": "Both providers failed", "timing": round(time.time() - start, 2)}


def _try_ollama(image_b64: str, prompt: str, timeout: int) -> Optional[dict]:
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": OLLAMA_VISION_MODEL, "messages": [{"role": "user", "content": prompt, "images": [image_b64]}], "stream": False}, timeout=timeout)
        if resp.status_code != 200:
            return {"error": f"Ollama HTTP {resp.status_code}"}
        data = resp.json()
        return {"description": data.get("message", {}).get("content", ""), "raw": data}
    except httpx.TimeoutException:
        return {"error": "Ollama timeout"}
    except Exception as e:
        return {"error": str(e)}


def _try_gemini(image_b64: str, prompt: str, api_key: str, timeout: int) -> Optional[dict]:
    model = "gemini-2.0-flash"
    url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}]}], "generationConfig": {"maxOutputTokens": 500, "temperature": 0.4}}
    try:
        resp = httpx.post(url, json=payload, timeout=timeout)
        if resp.status_code != 200:
            return {"error": f"Gemini HTTP {resp.status_code}: {resp.text[:300]}"}
        data = resp.json()
        candidates = data.get("candidates", [])
        description = "".join(part.get("text", "") for part in (candidates[0].get("content", {}).get("parts", []) if candidates else []))
        return {"description": description, "raw": data}
    except httpx.TimeoutException:
        return {"error": "Gemini timeout"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        import httpx as _h
        r = _h.post("http://localhost:4097/api/gui/screenshot", timeout=30)
        for c in r.json().get("result", {}).get("content", []):
            if c.get("type") == "image":
                result = analyze_image(c["data"], "What do you see?")
                print(json.dumps(result, indent=2)[:500])
                break
