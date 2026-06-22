#!/usr/bin/env python3
"""Siembra el diccionario de corrección de voz con términos técnicos de URA.

Ejecutar una vez tras la instalación del pipeline de audio.
"""

import os
import sqlite3

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "voice_corrections.db"))

# Formato: (mal_escuchado, texto_correcto)
# Whisper temperature=0 es determinista: fallará igual siempre.
# Por eso estas correcciones son permanentes.
CORRECCIONES = [
    # Hardware URA
    ("hemby", "GB10"),
    ("ember", "GB10"),
    ("g x 10", "GB10"),
    ("g por 10", "GB10"),
    ("black well", "Blackwell"),
    ("grace black well", "Grace Blackwell"),
    # Proyecto y plataforma
    ("codex", "ura_codex"),
    ("codice", "ura_codex"),
    ("q d rant", "Qdrant"),
    ("cuadrante", "Qdrant"),
    ("olama", "Ollama"),
    ("ollama la", "Ollama"),
    ("open code", "OpenCode"),
    ("open claw", "OpenClaw"),
    ("tuneladora", "tuneladora"),
    # Infraestructura
    ("sistema d", "systemd"),
    ("docker compose", "Docker Compose"),
    ("g p u", "GPU"),
    ("cuda", "CUDA"),
    # Desarrollo
    ("ast", "AST"),
    ("linter", "linter"),
    ("pytest", "pytest"),
    ("ruff", "Ruff"),
    # Pipeline de voz
    ("piter", "Piper"),
    ("foster whisper", "faster-whisper"),
    # Agentes y watchers
    ("ura watcher", "ura_watcher"),
    # Términos de voz reincidentes
    ("escúchame", "escúchame"),
    ("detente", "detente"),
    ("despierta", "despierta"),
]


def seed():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS corrections (  wrong_text TEXT PRIMARY KEY,  correct_text TEXT NOT NULL)")

    inserted = 0
    skipped = 0
    for wrong, correct in CORRECCIONES:
        key = " ".join(wrong.strip().lower().split())
        val = correct.strip()
        if key == val.lower():
            skipped += 1
            continue
        try:
            conn.execute(
                "INSERT OR REPLACE INTO corrections (wrong_text, correct_text) VALUES (?, ?)",
                (key, val),
            )
            inserted += 1
        except Exception as e:
            print(f"  Error: {key} → {val}: {e}")

    conn.commit()
    conn.close()
    print(f"✅ {inserted} correcciones insertadas, {skipped} omitidas (auto-regex)")
    print(f"📁 {DB_PATH}")


if __name__ == "__main__":
    seed()
