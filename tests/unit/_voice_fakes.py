"""Fakes de dependencias de hardware para motor/core/voice (TASK-20260820-005).

torch, whisper, sounddevice y soundfile NO están instalados en el .venv de
test; los módulos de voice los importan a nivel de módulo. Este helper los
registra en sys.modules ANTES de importar motor.core.voice.* para que los
tests puedan instanciar las clases y mockear el hardware.
"""

from __future__ import annotations

import sys
import types


def _register(name: str) -> types.ModuleType:
    if name not in sys.modules:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
    return sys.modules[name]


SOUNDDEVICE = _register("sounddevice")
SOUNDFILE = _register("soundfile")
TORCH = _register("torch")
WHISPER = _register("whisper")

SOUNDDEVICE.query_devices = lambda: []
SOUNDDEVICE.InputStream = None
SOUNDDEVICE.play = None
SOUNDDEVICE.wait = None

SOUNDFILE.read = None

TORCH.cuda = types.SimpleNamespace(is_available=lambda: True)
TORCH.backends = types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: True))
TORCH.cuda.is_available = lambda: True

WHISPER.load_model = None
WHISPER.load_audio = None
WHISPER.pad_or_trim = None
