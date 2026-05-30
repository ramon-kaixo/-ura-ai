#!/usr/bin/env python3
"""Agente de Voz Accesible — Ojos y manos de URA para el usuario."""

import json
import subprocess
from typing import Any

from faster_whisper import WhisperModel
import sounddevice as sd
import numpy as np
import pyautogui
import pytesseract
from PIL import Image

MODELO_LLM: str = "qwen3:32b"
GX10_URL: str = "http://10.164.1.99:11434/api/chat"
TASA: int = 16000

print("   Cargando modelo STT...")
modelo_stt: WhisperModel = WhisperModel("base", device="cpu", compute_type="int8")


def escuchar(duracion: int = 5) -> str:
    """Escucha audio del micrófono y transcribe a texto.

    Args:
        duracion: Duración de la grabación en segundos.

    Returns:
        Texto transcrito del audio.
    """
    audio: np.ndarray = sd.rec(int(duracion * TASA), samplerate=TASA, channels=1)
    sd.wait()
    audio = audio.flatten().astype(np.float32)
    segs: Any
    segs, _ = modelo_stt.transcribe(audio, language="es")
    return " ".join([s.text for s in segs])


def ver_pantalla() -> str:
    """Captura el estado actual de la pantalla y extrae texto.

    Returns:
        String con apps abiertas y texto detectado en pantalla.
    """
    try:
        r: subprocess.CompletedProcess = subprocess.run(
            ["osascript", "-e", 'tell app "System Events" to get name of every process'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        apps: str = r.stdout.strip()
    except Exception:
        apps = ""
    captura: Image.Image = pyautogui.screenshot()
    texto: str = pytesseract.image_to_string(captura, lang="spa")
    return f"Apps abiertas: {apps}\nTexto en pantalla:\n{texto[:1000]}"


def decir(texto: str) -> None:
    """Sintetiza voz a partir de texto usando macOS say.

    Args:
        texto: Texto a sintetizar.
    """
    subprocess.run(["say", texto])


def ejecutar(orden: str, contexto: str) -> dict[str, Any]:
    """Envía orden al LLM en GX10 y devuelve acción estructurada.

    Args:
        orden: Comando del usuario.
        contexto: Contexto de pantalla actual.

    Returns:
        Diccionario con 'accion' y 'parametros'.
    """
    prompt: str = (
        f"Eres URA Accesible. Pantalla: {contexto[:1500]}\n"
        f"Usuario: {orden}\n"
        f'Responde JSON: {{"accion":"clic|escribir|leer|decir|abrir","parametros":{{}}}}'
    )
    payload: str = json.dumps(
        {
            "model": MODELO_LLM,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
    )
    try:
        r: subprocess.CompletedProcess = subprocess.run(
            ["curl", "-s", GX10_URL, "-d", payload],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(json.loads(r.stdout)["message"]["content"])
    except Exception:
        return {"accion": "decir", "parametros": {"texto": "No entendi"}}


if __name__ == "__main__":
    print("   URA Accesible — di 'URA' para activar")
    while True:
        comando: str = escuchar(5)
        if "ura" in comando.lower():
            decir("Que necesita")
            orden: str = escuchar(6)
            ctx: str = ver_pantalla()
            d: dict[str, Any] = ejecutar(orden, ctx)
            a: str = d.get("accion", "decir")
            p: dict[str, Any] = d.get("parametros", {})
            if a == "clic":
                pyautogui.click(p.get("x", 500), p.get("y", 500))
                decir("Hecho")
            elif a == "escribir":
                pyautogui.write(p.get("texto", ""))
                decir("Escrito")
            elif a == "leer":
                decir(ctx[:500])
            elif a == "abrir":
                subprocess.run(["open", "-a", p.get("app", "")])
                decir("Abierto")
            else:
                decir(p.get("texto", "No se que hacer"))
