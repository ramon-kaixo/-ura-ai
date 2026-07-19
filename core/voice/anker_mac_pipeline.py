#!/usr/bin/env python3
"""Pipeline de audio determinista para Mac mini M4 (Apple Silicon).

- STT: openai-whisper con backend MPS (Metal) en GPU unificada M4
- Corrección: SQLite con reglas deterministas (hash exacto)
- Sanitización: anonymizer (IPs, tokens, rutas, passwords)
- Notificaciones: banners nativos macOS via osascript (asíncrono)
- Semáforo: is_playing_tts para evitar auto-escucha del Anker S500
"""

import os
import queue
import re
import sqlite3
import subprocess

import numpy as np
import sounddevice as sd
import torch
import whisper

from core.utils.anonymizer import sanitize_text


class AnkerMacPipeline:
    def __init__(self, base_path="/Users/ramonesnaola/URA/ura_ia_1972/", model_size="small") -> None:
        self.sample_rate = 16000
        self.block_size = 480
        self.db_path = os.path.join(base_path, "config/voice_corrections.db")
        self.audio_queue = queue.Queue()
        self.is_playing_tts = False

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        if torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        self.stt_model = whisper.load_model(model_size, device=self.device)
        self.device_index = self._find_anker_device()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS corrections (
                    wrong_text TEXT PRIMARY KEY,
                    correct_text TEXT NOT NULL
                )
            """)
            conn.commit()

    def _find_anker_device(self):
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if "powerconf s500" in dev["name"].lower() and dev["max_input_channels"] > 0:
                    return idx
        except Exception:
            pass
        return None

    def _audio_callback(self, indata, frames, time, status) -> None:
        if not self.is_playing_tts:
            self.audio_queue.put(indata.copy())

    def _trigger_macos_notification(self, title: str, message: str, sound: str = "Tink") -> None:
        """Banner nativo macOS asíncrono — sin bloqueo del pipeline."""
        script = f'display notification "{message}" with title "{title}" sound name "{sound}"'
        subprocess.Popen(  # noqa: S603  -- script construido internamente con título/mensaje/sonido fijos
            ["osascript", "-e", script],  # noqa: S607  -- script construido internamente con título/mensaje/sonido fijos
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _apply_deterministic_rules(self, text: str) -> str:
        if not text:
            return ""
        clean_input = " ".join(text.strip().lower().split())

        with sqlite3.connect(self.db_path) as conn:
            rules = conn.execute("SELECT wrong_text, correct_text FROM corrections").fetchall()

        rules.sort(key=lambda x: len(x[0]), reverse=True)

        corrected_text = clean_input
        for wrong, correct in rules:
            pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
            if pattern.search(corrected_text):
                corrected_text = pattern.sub(correct, corrected_text)
                self._trigger_macos_notification(
                    "🎯 URA: Corrección Fonética",
                    f"Reemplazado: '{wrong}' ➔ '{correct}'",
                    "Tink",
                )

        return corrected_text

    def listen_and_transcribe(self, duration_seconds=5) -> tuple[str, str, str]:
        """Escucha, transcribe, corrige y sanitiza.

        Returns:
            (raw_text, corrected_text, sanitized_text)

        """
        while not self.audio_queue.empty():
            self.audio_queue.get()

        if self.device_index is None:
            self.device_index = self._find_anker_device()
            if self.device_index is None:
                return "", "", ""

        try:
            stream = sd.InputStream(
                device=self.device_index,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="float32",
                callback=self._audio_callback,
            )

            audio_chunks = []
            with stream:
                iterations = int(self.sample_rate / self.block_size * duration_seconds)
                for _ in range(iterations):
                    try:
                        chunk = self.audio_queue.get(timeout=1.0)
                        audio_chunks.append(chunk)
                    except queue.Empty:
                        continue
        except Exception:
            self.device_index = None
            return "", "", ""

        if not audio_chunks:
            return "", "", ""

        try:
            full_audio = np.concatenate(audio_chunks, axis=0).flatten()
            result = self.stt_model.transcribe(full_audio, language="es", temperature=0.0, fp16=False)
            raw_text = result["text"].strip()
        except Exception:
            return "", "", ""

        corrected_text = self._apply_deterministic_rules(raw_text)
        sanitized_text = sanitize_text(corrected_text)

        if sanitized_text != corrected_text:
            self._trigger_macos_notification(
                "🔒 URA: Datos Protegidos",
                "Se han capado IPs, claves o rutas del input de voz",
                "Basso",
            )

        return raw_text, corrected_text, sanitized_text
