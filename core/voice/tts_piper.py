#!/usr/bin/env python3
"""Motor de síntesis TTS local con Piper para URA.

Integra el semáforo is_playing_tts del AnkerDeterministicPipeline
para evitar bucles acústicos (auto-escucha del micrófono mientras
el altavoz Anker S500 emite la respuesta).
"""

import contextlib
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
PIPER_BIN = Path("~/.local/bin/piper").expanduser()
DEFAULT_VOICE = "es_ES-davefx-medium.onnx"


class PiperTTSMotor:
    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        stt_pipeline: Optional["AnkerDeterministicPipeline"] = None,
    ) -> None:
        self.model_path = str(VOICES_DIR / voice)
        self.config_path = f"{self.model_path}.json"
        self.output_wav = "/tmp/ura_tts_output.wav"  # noqa: S108
        self.pipeline = stt_pipeline

        self.device_index = self._find_anker_output_device()

        if not Path(self.model_path).exists():
            msg = (
                f"Modelo de voz no encontrado: {self.model_path}\n"
                f"Descarga voces desde: https://rhasspy.github.io/piper-samples/"
            )
            raise FileNotFoundError(
                msg,
            )
        if not Path(self.config_path).exists():
            msg = f"Config {self.config_path} no encontrada"
            raise FileNotFoundError(msg)
        if not Path(PIPER_BIN).exists():
            msg = f"piper CLI no encontrado en {PIPER_BIN}. Ejecuta: pip install piper-tts --break-system-packages"
            raise RuntimeError(
                msg,
            )

        Path(self.model_path).stat().st_size  # noqa: B018

    def _find_anker_output_device(self) -> int | None:
        """Busca el índice físico de salida (output) del Anker S500."""
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                name = dev["name"].lower()
                if "powerconf s500" in name and dev["max_output_channels"] > 0:
                    return idx
        except Exception:  # noqa: S110
            pass
        return None

    def _execute_piper_and_play(self, text: str) -> None:
        """Hilo secundario: sintetiza con Piper y reproduce en el Anker."""
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
            proc = subprocess.Popen(  # noqa: S603  -- PIPER_BIN desde env fallback, rutas internas
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=text)

            if not Path(self.output_wav).exists():
                return

            data, fs = sf.read(self.output_wav)
            sd.play(data, samplerate=fs, device=self.device_index)
            sd.wait()

        except Exception:  # noqa: S110
            pass
        finally:
            if self.pipeline is not None:
                self.pipeline.is_playing_tts = False
            if Path(self.output_wav).exists():
                with contextlib.suppress(BaseException):
                    os.remove(self.output_wav)  # noqa: PTH107

    def hablar_asincrono(self, text: str) -> None:
        """Punto de entrada principal sin bloqueo para el orquestador."""
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
            proc = subprocess.Popen(  # noqa: S603  -- mismo patrón
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
        return f"<PiperTTSMotor voice={Path(self.model_path).name}>"
