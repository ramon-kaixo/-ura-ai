"""Cobertura 100x100 de motor/core/voice/anker_pipeline.py (TASK-20260820-005).

Cubre AnkerDeterministicPipeline: init (cuda/cpu, DB), _find_anker_device,
_find_default_input, _audio_callback, listen_and_transcribe,
transcribe_from_file, _apply_deterministic_rules, learn_correction y el
context manager __enter__/__exit__.
"""

from __future__ import annotations

import sqlite3
from unittest import mock

import numpy as np
import pytest

from tests.unit._voice_fakes import SOUNDDEVICE, TORCH, WHISPER

pytest.importorskip("sounddevice")


def _stt_model(text="  hola mundo  "):
    m = mock.MagicMock()
    m.transcribe.return_value = {"text": text}
    return m


class TestInit:
    def test_ok_cuda(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        monkeypatch.setattr(mod.sd, "query_devices", lambda: [])
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"), model_size="tiny")
        assert p.device == "cuda"
        assert p.device_index is None
        assert p.is_playing_tts is False
        assert p.sample_rate == 16000
        assert p.block_size == 480

    def test_ok_con_dispositivo(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        devs = [{"name": "USB PowerConf S500", "max_input_channels": 1}]
        monkeypatch.setattr(mod.sd, "query_devices", lambda: devs)
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        assert p.device_index == 0

    def test_sin_cuda_raise(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: False)
        with pytest.raises(RuntimeError):
            mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))

    def test_db_creada(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        db = tmp_path / "c.db"
        mod.AnkerDeterministicPipeline(db_path=str(db))
        with sqlite3.connect(db) as conn:
            tabs = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert ("corrections",) in tabs


class TestFindDevices:
    def test_anker_device(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        devs = [{"name": "USB PowerConf S500", "max_input_channels": 2}]
        with mock.patch.object(SOUNDDEVICE, "query_devices", return_value=devs):
            assert p._find_anker_device() == 0

    def test_anker_device_sin_match(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        with mock.patch.object(SOUNDDEVICE, "query_devices", return_value=[{"name": "X", "max_input_channels": 1}]):
            assert p._find_anker_device() is None

    def test_anker_device_excepcion(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        with mock.patch.object(SOUNDDEVICE, "query_devices", side_effect=RuntimeError("x")):
            assert p._find_anker_device() is None

    def test_default_input(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        with mock.patch.object(SOUNDDEVICE, "query_devices", return_value=[{"name": "Mic", "max_input_channels": 1}]):
            assert p._find_default_input() == 0

    def test_default_input_none(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        with mock.patch.object(SOUNDDEVICE, "query_devices", return_value=[]):
            assert p._find_default_input() is None

    def test_default_input_solo_salida(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        # device con max_input_channels==0 -> condicion falsa -> sigue iterando
        with mock.patch.object(
            SOUNDDEVICE,
            "query_devices",
            return_value=[
                {"name": "Speaker", "max_input_channels": 0},
                {"name": "Mic", "max_input_channels": 1},
            ],
        ):
            assert p._find_default_input() == 1

    def test_default_input_excepcion(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        with mock.patch.object(SOUNDDEVICE, "query_devices", side_effect=RuntimeError("x")):
            assert p._find_default_input() is None


class TestAudioCallback:
    def test_playing_descarta(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p.is_playing_tts = True
        p._audio_callback(np.zeros((480, 1)), None, None, None)
        assert p.audio_queue.empty()

    def test_no_playing_encola(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p._audio_callback(np.zeros((480, 1)), None, None, None)
        assert p.audio_queue.qsize() == 1


class _FakeStream:
    def __init__(self, chunks=5, pipeline=None) -> None:
        self._chunks = chunks
        self._pipeline = pipeline

    def __enter__(self):
        if self._pipeline is not None:
            for _ in range(self._chunks):
                self._pipeline._audio_callback(np.zeros((480, 1), dtype=np.float32), None, None, None)
        return self

    def __exit__(self, *a):
        return None


def _llenar_cola(p, n=5):
    for _ in range(n):
        p.audio_queue.put(np.zeros((480, 1), dtype=np.float32))


class TestListenAndTranscribe:
    def test_sin_dispositivo(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p.device_index = None
        assert p.listen_and_transcribe(1.0) == ("", "")

    def test_stream_error(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p.device_index = 0
        with mock.patch.object(SOUNDDEVICE, "InputStream", side_effect=RuntimeError("no device")):
            assert p.listen_and_transcribe(1.0) == ("", "")

    def test_sin_audio(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p.device_index = 0
        with mock.patch.object(SOUNDDEVICE, "InputStream", return_value=_FakeStream(0)):
            assert p.listen_and_transcribe(0.1) == ("", "")

    def test_ok(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model(" hola  mundo "))
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p.device_index = 0
        _llenar_cola(p, 5)
        with mock.patch.object(SOUNDDEVICE, "InputStream", return_value=_FakeStream(20, p)):
            raw, final = p.listen_and_transcribe(0.1)
        assert raw == "hola  mundo"
        assert final == "hola mundo"
        assert p.audio_queue.qsize() == 17


class TestTranscribeFromFile:
    def test_ok(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model("  texto raw  "))
        monkeypatch.setattr(WHISPER, "load_audio", lambda path: np.zeros(16000))
        monkeypatch.setattr(WHISPER, "pad_or_trim", lambda audio: audio)
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        raw, final = p.transcribe_from_file("/tmp/no_existe.wav")
        assert raw == "texto raw"
        assert final == "texto raw"


class TestReglasDeterministas:
    def test_texto_vacio(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        assert p._apply_deterministic_rules("") == ""
        assert p._apply_deterministic_rules("   ") == ""

    def test_aplica_reglas(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        db = tmp_path / "c.db"
        p = mod.AnkerDeterministicPipeline(db_path=str(db))
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO corrections VALUES ('hemby', 'GB10'), ('codex', 'ura_codex')",
            )
            conn.commit()
        assert p._apply_deterministic_rules("  HEMBY y CODEX  ") == "GB10 y ura_codex"

    def test_sin_reglas(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        assert p._apply_deterministic_rules("  Hola   Mundo  ") == "hola mundo"


class TestLearnCorrection:
    def test_ok(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        db = tmp_path / "c.db"
        p = mod.AnkerDeterministicPipeline(db_path=str(db))
        p.learn_correction(" hola ", "HOLA!")
        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT wrong_text, correct_text FROM corrections").fetchone()
        assert row == ("hola", "HOLA!")

    def test_key_vacio(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p.learn_correction("  ", "X")

    def test_val_vacio(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p.learn_correction("hola", "  ")

    def test_igual(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db"))
        p.learn_correction("hola", "HOLA")

    def test_reemplaza(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_pipeline as mod

        monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        db = tmp_path / "c.db"
        p = mod.AnkerDeterministicPipeline(db_path=str(db))
        p.learn_correction("hola", "NUEVO")
        p.learn_correction("hola", "REPLACED")
        with sqlite3.connect(db) as conn:
            rows = conn.execute("SELECT count(*) FROM corrections").fetchone()
        assert rows == (1,)


def test_context_manager(tmp_path, monkeypatch) -> None:
    import motor.core.voice.anker_pipeline as mod

    monkeypatch.setattr(TORCH.cuda, "is_available", lambda: True)
    monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
    with mod.AnkerDeterministicPipeline(db_path=str(tmp_path / "c.db")) as p:
        assert p.sample_rate == 16000
