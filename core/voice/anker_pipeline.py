#!/usr/bin/env python3
"""Pipeline de audio determinista para Anker PowerConf S500.

Captura raw 16kHz/16bit desde el micrófono Anker vía sounddevice,
transcribe con openai-whisper en GPU (PyTorch CUDA), aplica corrección
determinista por hash exacto desde SQLite, y gestiona el semáforo
is_playing_tts para evitar auto-escucha.
"""

import os
import queue
import re
import sqlite3
from pathlib import Path

import numpy as np
import sounddevice as sd
import torch
import whisper

DB_PATH = Path(os.path.join(Path(__file__).resolve().parent, "..", "..", "config", "voice_corrections.db"))  # noqa: PTH118
DEFAULT_MODEL = "small"
SAMPLE_RATE = 16000
BLOCK_SIZE = 480  # 30ms a 16kHz


class AnkerDeterministicPipeline:
    def __init__(self, db_path: str = DB_PATH, model_size: str = DEFAULT_MODEL) -> None:
        self.sample_rate = SAMPLE_RATE
        self.block_size = BLOCK_SIZE
        self.db_path = db_path
        self.audio_queue: queue.Queue = queue.Queue()
        self.is_playing_tts: bool = False

        os.makedirs(Path(self.db_path).parent, exist_ok=True)  # noqa: PTH103
        self._init_db()

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.device != "cuda":
            msg = "CUDA no disponible en PyTorch para GPU Blackwell."
            raise RuntimeError(msg)

        self.device_index = self._find_anker_device() or self._find_default_input()
        if self.device_index is None:
            pass

        self.stt_model = whisper.load_model(model_size, device=self.device)

    # ── DB ─────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS corrections (  wrong_text TEXT PRIMARY KEY,  correct_text TEXT NOT NULL)",
            )
            conn.commit()

    # ── Hardware ────────────────────────────────────────────────────

    def _find_anker_device(self) -> int | None:
        """Busca el índice físico del Anker PowerConf S500."""
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if "powerconf s500" in dev["name"].lower() and dev["max_input_channels"] > 0:
                    return idx
        except Exception:  # noqa: S110
            pass
        return None

    def _find_default_input(self) -> int | None:
        """Encuentra cualquier dispositivo de entrada disponible."""
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev["max_input_channels"] > 0:
                    return idx
        except Exception:  # noqa: S110
            pass
        return None

    # ── Audio callback ─────────────────────────────────────────────

    def _audio_callback(self, indata, frames, time, status) -> None:
        """Callback de alta velocidad. Descarta bits si el altavoz está emitiendo TTS."""
        if self.is_playing_tts:
            return
        self.audio_queue.put(indata.copy())

    # ── Captura + transcripción ────────────────────────────────────

    def listen_and_transcribe(self, duration_seconds: float = 5.0) -> tuple[str, str]:
        """Escucha, transcribe y corrige. Devuelve (raw_text, corrected_text)."""
        if self.device_index is None:
            return "", ""

        while not self.audio_queue.empty():
            self.audio_queue.get()

        try:
            stream = sd.InputStream(
                device=self.device_index,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="float32",
                callback=self._audio_callback,
            )
        except Exception:
            return "", ""

        audio_chunks = []

        with stream:
            iterations = int(self.sample_rate / self.block_size * duration_seconds)
            for _ in range(iterations):
                try:
                    chunk = self.audio_queue.get(timeout=1.0)
                    audio_chunks.append(chunk)
                except queue.Empty:
                    continue

        if not audio_chunks:
            return "", ""

        full_audio = np.concatenate(audio_chunks, axis=0).flatten()

        result = self.stt_model.transcribe(
            full_audio,
            language="es",
            temperature=0.0,
            fp16=True,
        )

        raw_text = result["text"].strip()
        final_text = self._apply_deterministic_rules(raw_text)

        return raw_text, final_text

    def transcribe_from_file(self, wav_path: str) -> tuple[str, str]:
        """Transcribe un archivo WAV (para testing sin micrófono)."""
        audio = whisper.load_audio(wav_path)
        audio = whisper.pad_or_trim(audio)

        result = self.stt_model.transcribe(
            audio,
            language="es",
            temperature=0.0,
            fp16=True,
        )
        raw_text = result["text"].strip()
        final_text = self._apply_deterministic_rules(raw_text)
        return raw_text, final_text

    # ── Corrección determinista ────────────────────────────────────

    def _apply_deterministic_rules(self, text: str) -> str:
        """Aplica sustituciones quirúrgicas ordenando por longitud descendente con límites de palabra."""
        if not text:
            return ""

        clean_input = " ".join(text.strip().lower().split())

        with sqlite3.connect(self.db_path) as conn:
            rules = conn.execute("SELECT wrong_text, correct_text FROM corrections").fetchall()

        rules.sort(key=lambda x: len(x[0]), reverse=True)

        corrected_text = clean_input
        for wrong, correct in rules:
            pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
            corrected_text = pattern.sub(correct, corrected_text)

        return corrected_text

    def learn_correction(self, raw_stt_output: str, user_corrected_text: str) -> None:
        """Inyecta un mapeo hash exacto desde la UI al detectar una corrección manual."""
        key = " ".join(raw_stt_output.strip().lower().split())
        val = user_corrected_text.strip()

        if not key or not val or key == val.lower():
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO corrections (wrong_text, correct_text) VALUES (?, ?)",
                (key, val),
            )
            conn.commit()

    # ── TTS semáforo ───────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ── Demo ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    pipeline = AnkerDeterministicPipeline(model_size="tiny")

    sr = SAMPLE_RATE
    t = np.linspace(0, 2, int(sr * 2), endpoint=False)
    test_audio = (np.sin(440 * 2 * np.pi * t) * 0.1).astype(np.float32)

    tmp_wav = "/tmp/test_whisper_gx10.wav"  # noqa: S108
    import scipy.io.wavfile as wav

    wav.write(tmp_wav, sr, test_audio)

    raw, final = pipeline.transcribe_from_file(tmp_wav)

    pipeline.learn_correction("hemby", "GB10")
    pipeline.learn_correction("codex", "ura_codex")
    pipeline.learn_correction("qdrant", "Qdrant")
