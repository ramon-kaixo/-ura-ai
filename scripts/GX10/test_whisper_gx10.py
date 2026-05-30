#!/usr/bin/env python3
"""Test Whisper en GX10 con formato multipart correcto."""

import struct
import math
import json
import os

os.environ["PATH"] = os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")

# Generar WAV simple (tono 440Hz)
SAMPLE_RATE = 16000
DURATION = 2
FREQUENCY = 440
n_samples = SAMPLE_RATE * DURATION

wav_path = "/tmp/test_whisper.wav"
with open(wav_path, "wb") as f:
    f.write(b"RIFF")
    f.write(struct.pack("<I", 36 + n_samples * 2))
    f.write(b"WAVE")
    f.write(b"fmt ")
    f.write(struct.pack("<I", 16))
    f.write(struct.pack("<H", 1))
    f.write(struct.pack("<H", 1))
    f.write(struct.pack("<I", SAMPLE_RATE))
    f.write(struct.pack("<I", SAMPLE_RATE * 2))
    f.write(struct.pack("<H", 2))
    f.write(struct.pack("<H", 16))
    f.write(b"data")
    f.write(struct.pack("<I", n_samples * 2))
    for i in range(n_samples):
        sample = int(math.sin(2 * math.pi * FREQUENCY * i / SAMPLE_RATE) * 32767)
        f.write(struct.pack("<h", sample))

print(f"WAV generado: {wav_path}")

# Test 1: Enviar con curl (simulando el script de grabación)
import subprocess

result = subprocess.run(
    ["curl", "-s", "-X", "POST", "http://127.0.0.1:8090/transcribe", "-F", f"audio=@{wav_path}"],
    capture_output=True,
    text=True,
    timeout=30,
)
print("Whisper stdout:", result.stdout[:500])
if result.stderr:
    print("Whisper stderr:", result.stderr[:200])

# Parsear resultado
try:
    data = json.loads(result.stdout)
    if "text" in data:
        print(f"\n✅ Whisper transcribió: '{data['text']}'")
        print(f"   Correcciones: {data.get('corrections_applied', 0)}")
        print(f"   Modelo: {data.get('model', 'N/A')}")
    elif "error" in data:
        print(f"\n❌ Whisper error: {data['error']}")
except json.JSONDecodeError:
    print("No se pudo parsear respuesta JSON")

# Test 2: Health endpoint
print("\n--- Health check ---")
result2 = subprocess.run(
    ["curl", "-s", "http://127.0.0.1:8090/health"], capture_output=True, text=True
)
print("Health:", result2.stdout[:200])

# Test 3: Langfuse - verificar versión
print("\n--- Langfuse ---")
result3 = subprocess.run(
    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:3000/api/health"],
    capture_output=True,
    text=True,
)
print(f"Langfuse API health status: {result3.stdout.strip()}")

result4 = subprocess.run(
    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:3000/api/v1/traces"],
    capture_output=True,
    text=True,
)
print(f"Langfuse API traces status: {result4.stdout.strip()}")
