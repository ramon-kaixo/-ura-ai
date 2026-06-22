#!/usr/bin/env python3
"""Motor de síntesis TTS local con Piper para URA.

Integra el semáforo is_playing_tts del AnkerDeterministicPipeline
para evitar bucles acústicos (auto-escucha del micrófono mientras
el altavoz Anker S500 emite la respuesta).
"""

import os
import subprocess
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import sounddevice as sd
import soundfile as sf

if TYPE_CHECKING:
    from .anker_pipeline import AnkerDeterministicPipeline

VOICES_DIR = Path(__file__).resolve().parent / "voices"
PIPER_BIN = os.path.expanduser("~/.local/bin/piper")
DEFAULT_VOICE = "es_ES-davefx-medium.onnx"


class PiperTTSMotor:
    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        stt_pipeline: Optional["AnkerDeterministicPipeline"] = None,
    ):
        self.model_path = str(VOICES_DIR / voice)
        self.config_path = f"{self.model_path}.json"
        self.output_wav = "/tmp/ura_tts_output.wav"
        self.pipeline = stt_pipeline

        self.device_index = self._find_anker_output_device()

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Modelo de voz no encontrado: {self.model_path}\n"
                f"Descarga voces desde: https://rhasspy.github.io/piper-samples/",
            )
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config {self.config_path} no encontrada")
        if not os.path.exists(PIPER_BIN):
            raise RuntimeError(
                f"piper CLI no encontrado en {PIPER_BIN}. Ejecuta: pip install piper-tts --break-system-packages",
            )

        size = os.path.getsize(self.model_path)
        print(f"🗣️ TTS motor listo: {voice} ({size / 1024 / 1024:.0f} MB)")

    def _find_anker_output_device(self) -> int | None:
        """Busca el índice físico de salida (output) del Anker S500"""
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                name = dev["name"].lower()
                if "powerconf s500" in name and dev["max_output_channels"] > 0:
                    print(f"🔊 Anker S500 (salida) detectado en índice {idx}")
                    return idx
        except Exception as e:
            print(f"⚠️ Error escaneando salidas de audio: {e}")
        return None

    def _execute_piper_and_play(self, text: str):
        """Hilo secundario: sintetiza con Piper y reproduce en el Anker"""
        if self.pipeline is not None:
            self.pipeline.is_playing_tts = True

        try:
            cmd = [
                PIPER_BIN,
                "--model",
                self.model_path,
                "--output-file",
                self.output_wav,
            ]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=text)

            if not os.path.exists(self.output_wav):
                print("❌ Piper no generó el archivo de audio.")
                return

            data, fs = sf.read(self.output_wav)
            sd.play(data, samplerate=fs, device=self.device_index)
            sd.wait()

        except Exception as e:
            print(f"❌ Fallo en reproducción Piper: {e}")
        finally:
            if self.pipeline is not None:
                self.pipeline.is_playing_tts = False
            if os.path.exists(self.output_wav):
                try:
                    os.remove(self.output_wav)
                except:
                    pass

    def hablar_asincrono(self, text: str):
        """Punto de entrada principal sin bloqueo para el orquestador"""
        if not text.strip():
            return
        t = threading.Thread(
            target=self._execute_piper_and_play,
            args=(text,),
            daemon=True,
        )
        t.start()

    def speak_to_file(self, text: str, output_path: str) -> str:
        """Sintetiza a WAV sin reproducir (para tests)."""
        if self.pipeline is not None:
            self.pipeline.is_playing_tts = True
        try:
            cmd = [PIPER_BIN, "--model", self.model_path, "--output-file", output_path]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=text)
            return output_path
        finally:
            if self.pipeline is not None:
                self.pipeline.is_playing_tts = False

    def __repr__(self) -> str:
        return f"<PiperTTSMotor voice={os.path.basename(self.model_path)}>"
