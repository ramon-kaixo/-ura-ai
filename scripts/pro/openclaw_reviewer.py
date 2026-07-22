#!/usr/bin/env python3
"""OpenClaw Reviewer — Revisor Independiente con qwen2.5-coder:q8_0.

Uso:
  python3 openclaw_reviewer.py original.py refactorizado.py
  python3 openclaw_reviewer.py original.py refactorizado.py --json
"""

PLUGIN = {
    "name": "openclaw_reviewer",
    "phase": "post",
    "timeout": 120,
    "blocking": False,
    "needs_file": False,
}

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", os.environ.get("OLLAMA_URL", "http://10.164.1.99:11434"))
MODEL = os.environ.get("REVIEWER_MODEL", "qwen2.5-coder:q8_0")
TIMEOUT = int(os.environ.get("REVIEWER_TIMEOUT", "180"))


def llamar_ollama(prompt: str, model: str = MODEL, timeout: int = TIMEOUT) -> str:
    """Llama a Ollama con el modelo revisor."""
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 1024},
        },
    ).encode()

    req = urllib.request.Request(  # noqa: S310
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return json.loads(r.read()).get("response", "")


def revisar(
    codigo_original: str,
    codigo_refactorizado: str,
    nombre_archivo: str = "desconocido",
) -> dict:
    """Envía código al revisor q8_0 y obtiene veredicto.

    Returns:
        {veredicto, razones, confianza, tiempo_s, modelo}

    """
    prompt = f"""Eres un revisor de código Python. Tu trabajo es revisar refactores y decidir si son correctos.

ARCHIVO: {nombre_archivo}

CÓDIGO ORIGINAL:
```python
{codigo_original[:8000]}
```

CÓDIGO REFACTORIZADO:
```python
{codigo_refactorizado[:8000]}
```

Evalúa:
1. ¿El refactor mantiene el mismo comportamiento?
2. ¿Hay errores de lógica introducidos?
3. ¿La estructura del código mejoró realmente?
4. ¿Hay variables o funciones que desaparecieron?
5. ¿La indentación es correcta?

Responde EXACTAMENTE en este formato JSON (solo JSON, sin markdown):
{{
  "veredicto": "APROBAR" o "RECHAZAR",
  "razones": ["razon 1", "razon 2"],
  "confianza": 0.0-1.0,
  "problemas": ["problema 1"] o []
}}
"""

    t0 = time.time()
    try:
        respuesta = llamar_ollama(prompt)
        elapsed = time.time() - t0

        # Intentar parsear JSON (puede venir envuelto en ```json)
        respuesta_limpia = respuesta.strip()
        if "```json" in respuesta_limpia:
            respuesta_limpia = respuesta_limpia.split("```json")[1].split("```")[0].strip()
        elif "```" in respuesta_limpia:
            respuesta_limpia = respuesta_limpia.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(respuesta_limpia)
        except json.JSONDecodeError:
            # Fallback: extraer campos manualmente
            data = {
                "veredicto": "APROBAR" if "APROBAR" in respuesta else "RECHAZAR",
                "razones": [respuesta[:200]],
                "confianza": 0.5,
                "problemas": [] if "APROBAR" in respuesta else [respuesta[:200]],
            }

        data["tiempo_s"] = round(elapsed, 1)
        data["modelo"] = MODEL
        return data

    except Exception as e:
        return {
            "veredicto": "RECHAZAR",
            "razones": [f"Error del revisor: {e}"],
            "confianza": 0.0,
            "problemas": ["Revisor no disponible"],
            "tiempo_s": round(time.time() - t0, 1),
            "modelo": MODEL,
        }


def revisar_archivos(ruta_original: Path, ruta_refactorizado: Path) -> dict:
    """Revisa dos archivos: original vs refactorizado."""
    if not ruta_original.exists() or not ruta_refactorizado.exists():
        return {"veredicto": "RECHAZAR", "razones": ["Archivo no encontrado"]}

    orig = ruta_original.read_text()
    refac = ruta_refactorizado.read_text()

    nombre = str(ruta_original).replace(str(Path.home()) + "/URA/ura_ia_1972/", "")
    return revisar(orig, refac, nombre)


def scan_project() -> None:
    root = Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="OpenClaw Reviewer Independiente")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("original", nargs="?", help="Archivo original")
    parser.add_argument("refactorizado", nargs="?", help="Archivo refactorizado")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    if not args.original or not args.refactorizado:
        parser.print_help()
        sys.exit(1)

    resultado = revisar_archivos(Path(args.original), Path(args.refactorizado))

    if args.json:
        pass
    else:
        "✅" if resultado["veredicto"] == "APROBAR" else "❌"
        for _r in resultado.get("razones", []):
            pass
        if resultado.get("problemas"):
            for _p in resultado["problemas"]:
                pass

    sys.exit(0 if resultado["veredicto"] == "APROBAR" else 1)


if __name__ == "__main__":
    main()
