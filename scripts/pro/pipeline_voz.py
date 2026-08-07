#!/usr/bin/env python3
"""Orquestador central del pipeline de voz URA (Anker S500 + Whisper GPU + Piper TTS).

Flujo:
  Captura Mic (Anker S500, 16kHz) → Whisper GPU (fp16, temp=0) → Corrector SQLite
  → Sanitizador (IPs, tokens, rutas) → LLM (Ollama) → Piper TTS (thread) → Altavoz

El semáforo is_playing_tts aisla el micrófono durante la respuesta.

Migrado a motor.core.voice en F7 (los imports directos de motor evitan el
doble-módulo de los shims core.voice.*).
"""

import sys
import time

from core.utils.anonymizer import sanitize_text
from motor.core.voice.anker_pipeline import AnkerDeterministicPipeline
from motor.core.voice.tts_piper import PiperTTSMotor


def ejecutar_bucle_seguro() -> None:
    """Bucle principal: escucha → transcribe → corrige → sanitiza → responde."""
    try:
        pipeline_stt = AnkerDeterministicPipeline()
        motor_tts = PiperTTSMotor(stt_pipeline=pipeline_stt)
    except (RuntimeError, FileNotFoundError):
        sys.exit(1)

    try:
        while True:

            if pipeline_stt.device_index is None:
                time.sleep(10)
                continue

            _raw_text, corrected_text = pipeline_stt.listen_and_transcribe(duration_seconds=5)

            if not corrected_text:
                continue

            clean_text = sanitize_text(corrected_text)

            # ── Placeholder LLM ──────────────────────────────────
            # Aquí conectarás con Ollama:
            #   respuesta = ollama.generate(model="qwen3:32b-q8_0", prompt=clean_text)
            respuesta_llm = f"Entendido. Procesando '{clean_text[:50]}' en el nodo GB10 con Blackwell y Qdrant."

            # ── Respuesta con mute de seguridad ─────────────────

            pipeline_stt.is_playing_tts = True
            motor_tts.hablar_asincrono(respuesta_llm)

            time.sleep(0.1)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    ejecutar_bucle_seguro()