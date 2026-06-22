#!/usr/bin/env python3
"""Benchmark de latencia del pipeline de voz en Mac mini M4.

Mide:
  - Tiempo de carga del modelo Whisper en MPS
  - Latencia de inferencia (MPS/Metal)
  - Tiempo total del proceso captura→transcripción→corrección

Ejecutar con Anker S500 conectado por USB-C:
  python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/test_latencia_mac.py
"""

import sys
import time

BASE_PATH = "/Users/ramonesnaola/URA/ura_ia_1972/"
sys.path.append(BASE_PATH)

from core.voice.anker_mac_pipeline import AnkerMacPipeline


def testear():
    print("🧠 Diagnóstico de latencia en Apple Silicon M4")
    print("=" * 50)

    t0 = time.perf_counter()
    pipeline = AnkerMacPipeline()
    t_carga = time.perf_counter() - t0
    print(f"⏱️  Carga de Whisper en MPS: {t_carga:.2f}s")

    if pipeline.device_index is None:
        print("\n❌ Anker S500 no detectado. Conéctalo por USB-C y reintenta.")
        return

    duracion = 3.0
    print(f"\n🎙️  Capturando {duracion}s de audio (di una palabra técnica)...")

    t1 = time.perf_counter()
    raw, corrected, clean = pipeline.listen_and_transcribe(duration_seconds=duracion)
    t_total = time.perf_counter() - t1

    latencia_inferencia = t_total - duracion

    print("\n" + "=" * 50)
    print("📊 RESULTADOS")
    print("=" * 50)
    print(f"🗣️  Crudo:       '{raw}'")
    print(f"🎯  Corregido:   '{corrected}'")
    print(f"🔒  Sanitizado:  '{clean}'")
    print("-" * 50)
    print(f"⏱️  Ventana capturada:     {duracion:.1f}s")
    print(f"⏱️  Tiempo total proceso:   {t_total:.3f}s")
    print(f"⚡  Latencia inferencia:    {latencia_inferencia * 1000:.1f}ms")
    print("-" * 50)

    if latencia_inferencia < 0.5:
        print("🚀 Rendimiento óptimo (< 500ms)")
    else:
        print("⚠️  Rendimiento moderado. Revisa procesos en segundo plano.")

    print("=" * 50)


if __name__ == "__main__":
    testear()
