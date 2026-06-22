#!/usr/bin/env python3
"""Orquestador del pipeline de voz URA para Mac mini M4.

  - Instancia única vía fcntl.flock (evita colisiones CoreAudio)
  - Captura SIGTERM/SIGINT para liberar resources limpiamente
  - Bucle: escucha → transcribe → corrige → sanitiza → LLM → TTS
  - Semáforo is_playing_tts gestionado por el motor TTS

Ejecutar:
  python3 scripts/pro/demo_pipeline_mac.py

Daemon launchd:
  Ver com.ura.voice.plist en LaunchAgents.
"""

import fcntl
import signal
import sys
import time

BASE_PATH = "/Users/ramonesnaola/URA/ura_ia_1972/"
sys.path.append(BASE_PATH)

from core.voice.anker_mac_pipeline import AnkerMacPipeline
from core.voice.tts_piper import PiperTTSMotor

_lock_file = None


def _adquirir_instancia_unica():
    global _lock_file
    lock_path = "/tmp/com.ura.voice.lock"
    try:
        _lock_file = open(lock_path, "w")
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("❌ Ya existe una instancia activa del pipeline de voz.")
        sys.exit(0)


def _liberar_y_salir(signum, frame):
    print("\n🛑 Señal de parada recibida. Liberando hardware...")
    global _lock_file
    if _lock_file:
        try:
            fcntl.flock(_lock_file, fcntl.LOCK_UN)
            _lock_file.close()
        except Exception:
            pass
    sys.exit(0)


def ejecutar_nodo_voz():
    _adquirir_instancia_unica()

    signal.signal(signal.SIGTERM, _liberar_y_salir)
    signal.signal(signal.SIGINT, _liberar_y_salir)

    print("🚀 Levantando Nodo de Voz URA en Mac mini M4...")

    try:
        pipeline = AnkerMacPipeline(base_path=BASE_PATH)
        motor_tts = PiperTTSMotor(stt_pipeline=pipeline)
    except Exception as e:
        print(f"❌ Fallo crítico de inicialización: {e}", file=sys.stderr)
        sys.exit(1)

    print("✅ Pipeline de voz listo. Esperando comandos...\n")

    while True:
        if pipeline.device_index is None:
            print("⏳ Buscando Anker S500 por USB-C... (reintento 10s)", flush=True)
            time.sleep(10)
            pipeline.device_index = pipeline._find_anker_device()
            continue

        raw, corrected, clean = pipeline.listen_and_transcribe(duration_seconds=5)

        if not clean:
            continue

        print(f"\n🗣️  Crudo:      '{raw}'")
        print(f"🎯 Corregido:  '{corrected}'")
        print(f"🔒 Sanitizado: '{clean}'")

        try:
            from agents.laia_agent import procesar_bucle_ura

            respuesta = procesar_bucle_ura(clean)
        except ImportError:
            # Placeholder hasta que exista laia_agent
            respuesta = f"Entendido. Procesando '{clean[:50]}' en Mac mini M4 con MPS y Qdrant."
        except Exception as e:
            respuesta = f"Error en laia_agent: {e}"

        if not respuesta:
            continue

        print(f"🤖 URA: {respuesta}")

        pipeline.is_playing_tts = True
        motor_tts.hablar_asincrono(respuesta)


if __name__ == "__main__":
    ejecutar_nodo_voz()
