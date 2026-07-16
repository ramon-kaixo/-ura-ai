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


def testear() -> None:

    t0 = time.perf_counter()
    pipeline = AnkerMacPipeline()
    time.perf_counter() - t0

    if pipeline.device_index is None:
        return

    duracion = 3.0

    t1 = time.perf_counter()
    _raw, _corrected, _clean = pipeline.listen_and_transcribe(duration_seconds=duracion)
    t_total = time.perf_counter() - t1

    latencia_inferencia = t_total - duracion

    if latencia_inferencia < 0.5:
        pass
    else:
        pass


if __name__ == "__main__":
    testear()
