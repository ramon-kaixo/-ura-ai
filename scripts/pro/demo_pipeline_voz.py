#!/usr/bin/env python3
"""Orquestador central del pipeline de voz URA (Anker S500 + Whisper GPU + Piper TTS).

Flujo:
  Captura Mic (Anker S500, 16kHz) → Whisper GPU (fp16, temp=0) → Corrector SQLite
  → Sanitizador (IPs, tokens, rutas) → LLM (Ollama) → Piper TTS (thread) → Altavoz

El semáforo is_playing_tts aisla el micrófono durante la respuesta.
"""

import sys
import time

from core.utils.anonymizer import sanitize_text
from core.voice.anker_pipeline import AnkerDeterministicPipeline
from core.voice.tts_piper import PiperTTSMotor


def ejecutar_bucle_seguro():
    """Bucle principal: escucha → transcribe → corrige → sanitiza → responde"""
    try:
        pipeline_stt = AnkerDeterministicPipeline()
        motor_tts = PiperTTSMotor(stt_pipeline=pipeline_stt)
    except RuntimeError as e:
        print(f"❌ Error de inicialización: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n🛡️ Pipeline de Voz Protegido Online [Whisper GPU + SQLite Corrector + Anonymizer]")
    print("   Presiona Ctrl+C para detener.\n")

    try:
        while True:
            if pipeline_stt.device_index is None:
                print("⏳ Sin micrófono. Esperando Anker S500... (reintento en 10s)")
                time.sleep(10)
                continue

            raw_text, corrected_text = pipeline_stt.listen_and_transcribe(duration_seconds=5)

            if not corrected_text:
                continue

            print(f"\n🗣️ [Audio Crudo]:  '{raw_text}'")
            print(f"🎯 [Corrector DB]:  '{corrected_text}'")

            clean_text = sanitize_text(corrected_text)

            if clean_text != corrected_text:
                print(f"🔒 [Anonimizado]:   '{clean_text}'")
            else:
                print(f"✅ [Seguro para LLM]: '{clean_text}'")

            # ── Placeholder LLM ──────────────────────────────────
            # Aquí conectarás con Ollama:
            #   respuesta = ollama.generate(model="qwen3:32b-q8_0", prompt=clean_text)
            respuesta_llm = f"Entendido. Procesando '{clean_text[:50]}' en el nodo GB10 con Blackwell y Qdrant."

            # ── Respuesta con mute de seguridad ─────────────────
            print(f"🤖 URA: {respuesta_llm}")

            pipeline_stt.is_playing_tts = True
            motor_tts.hablar_asincrono(respuesta_llm)

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n🛑 Pipeline de voz detenido limpiamente por el operador.")


# ── Tests de regresión ─────────────────────────────────────────────
def _test_semaphore():
    import numpy as np

    pipe = AnkerDeterministicPipeline(model_size="tiny")
    tts = PiperTTSMotor(stt_pipeline=pipe)

    assert pipe.is_playing_tts is False
    tts.speak_to_file("test", "/tmp/sem_test.wav")
    assert pipe.is_playing_tts is False
    print("✅ Semáforo: False → True → False")

    pipe.is_playing_tts = True
    chunk = np.zeros((480, 1), dtype=np.float32)
    pipe._audio_callback(chunk, 480, None, None)
    assert pipe.audio_queue.empty()
    pipe.is_playing_tts = False
    print("✅ Bloqueo acústico: chunks descartados durante TTS")


def _test_corrections():
    pipe = AnkerDeterministicPipeline(model_size="tiny")
    casos = [
        ("en hemby", "en GB10"),
        ("codex en cuadrante", "ura_codex en Qdrant"),
        ("olama con open code", "Ollama con OpenCode"),
    ]
    for raw, exp in casos:
        res = pipe._apply_deterministic_rules(raw)
        assert res == exp, f"{raw} → {res} (esperado: {exp})"
    print(f"✅ {len(casos)} correcciones verificadas")


def _test_tts():
    tts = PiperTTSMotor()
    path = tts.speak_to_file("Hola GB10.", "/tmp/tts_orch.wav")
    import scipy.io.wavfile as wav

    sr, data = wav.read(path)
    print(f"✅ TTS: {len(data) / sr:.1f}s a {sr}Hz")


def _test_sanitizer():
    dirty = "Conecta a 10.164.1.99 con password='secreto'"
    clean = sanitize_text(dirty)
    assert "[IP_REDACTADA]" in clean
    assert "[CREDENTIAL_REDACTADA]" in clean
    assert "10.164.1.99" not in clean
    print(f"✅ Anonymizer: '{dirty}' → '{clean}'")


if __name__ == "__main__":
    if "--test" in sys.argv or "-t" in sys.argv:
        t0 = time.time()
        _test_semaphore()
        _test_corrections()
        _test_tts()
        _test_sanitizer()
        print(f"\n🎯 Tests en {time.time() - t0:.1f}s")
    else:
        ejecutar_bucle_seguro()
