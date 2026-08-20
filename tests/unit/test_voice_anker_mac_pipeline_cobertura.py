"""Cobertura 100x100 de motor/core/voice/anker_mac_pipeline.py (TASK-20260820-005).

Cubre AnkerMacPipeline: init (mps/cpu, DB), _init_db, _find_anker_device,
_audio_callback, _trigger_macos_notification, _apply_deterministic_rules y
listen_and_transcribe (incl. sanitize_text y notificaciones).
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


def _make(tmp_path, monkeypatch, mps=True):
    import motor.core.voice.anker_mac_pipeline as mod

    monkeypatch.setattr(TORCH.backends.mps, "is_available", lambda: mps)
    monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
    monkeypatch.setattr(mod.sd, "query_devices", lambda: [])
    return mod, mod.AnkerMacPipeline(base_path=str(tmp_path) + "/")


class TestInit:
    def test_ok_mps(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch, mps=True)
        assert p.device == "mps"
        assert p.device_index is None

    def test_ok_cpu(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch, mps=False)
        assert p.device == "cpu"

    def test_db_creada(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with sqlite3.connect(p.db_path) as conn:
            tabs = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert ("corrections",) in tabs

    def test_con_dispositivo(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_mac_pipeline as mod

        monkeypatch.setattr(TORCH.backends.mps, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        devs = [{"name": "USB PowerConf S500", "max_input_channels": 1}]
        monkeypatch.setattr(mod.sd, "query_devices", lambda: devs)
        p = mod.AnkerMacPipeline(base_path=str(tmp_path) + "/")
        assert p.device_index == 0


class TestFindAnkerDevice:
    def test_match(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with mock.patch.object(
            SOUNDDEVICE,
            "query_devices",
            return_value=[{"name": "PowerConf S500", "max_input_channels": 2}],
        ):
            assert p._find_anker_device() == 0

    def test_no_match(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with mock.patch.object(SOUNDDEVICE, "query_devices", return_value=[{"name": "X", "max_input_channels": 1}]):
            assert p._find_anker_device() is None

    def test_excepcion(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with mock.patch.object(SOUNDDEVICE, "query_devices", side_effect=RuntimeError("x")):
            assert p._find_anker_device() is None

    def test_no_input_channels_continua(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with mock.patch.object(
            SOUNDDEVICE,
            "query_devices",
            return_value=[
                {"name": "PowerConf S500", "max_input_channels": 0},
                {"name": "PowerConf S500", "max_input_channels": 1},
            ],
        ):
            assert p._find_anker_device() == 1


class TestAudioCallback:
    def test_playing_descarta(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        p.is_playing_tts = True
        p._audio_callback(np.zeros((480, 1)), None, None, None)
        assert p.audio_queue.empty()

    def test_no_playing_encola(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        p._audio_callback(np.zeros((480, 1)), None, None, None)
        assert p.audio_queue.qsize() == 1


class TestNotificacion:
    def test_sound_valido(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with mock.patch("subprocess.Popen") as popen:
            p._trigger_macos_notification("Titulo", "Mensaje", "Glass")
        popen.assert_called_once()
        script = popen.call_args.args[0][2]
        assert 'sound name "Glass"' in script
        assert '"Titulo"' in script

    def test_sound_invalido_default(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with mock.patch("subprocess.Popen") as popen:
            p._trigger_macos_notification("T", "M", "NotARealSound")
        script = popen.call_args.args[0][2]
        assert 'sound name "Tink"' in script

    def test_escape_comillas(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with mock.patch("subprocess.Popen") as popen:
            p._trigger_macos_notification('Ti"tulo', 'Me"nsaje\\x')
        script = popen.call_args.args[0][2]
        assert '\\"' in script


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


class TestReglasDeterministas:
    def test_texto_vacio(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        assert p._apply_deterministic_rules("") == ""
        assert p._apply_deterministic_rules("   ") == ""

    def test_aplica_reglas_con_notificacion(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_mac_pipeline as mod

        monkeypatch.setattr(TORCH.backends.mps, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerMacPipeline(base_path=str(tmp_path) + "/")
        with sqlite3.connect(p.db_path) as conn:
            conn.execute("INSERT INTO corrections VALUES ('hemby', 'GB10')")
            conn.commit()
        with mock.patch("subprocess.Popen") as popen:
            out = p._apply_deterministic_rules("  HEMBY  ")
        assert out == "GB10"
        popen.assert_called_once()

    def test_sin_match_sin_notificacion(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        with sqlite3.connect(p.db_path) as conn:
            conn.execute("INSERT INTO corrections VALUES ('hemby', 'GB10')")
            conn.commit()
        with mock.patch("subprocess.Popen") as popen:
            out = p._apply_deterministic_rules("  hola mundo  ")
        assert out == "hola mundo"
        popen.assert_not_called()


class TestListenAndTranscribe:
    def test_sin_dispositivo(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        assert p.listen_and_transcribe(1.0) == ("", "", "")

    def test_device_index_presente_no_rebusca(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_mac_pipeline as mod

        monkeypatch.setattr(TORCH.backends.mps, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerMacPipeline(base_path=str(tmp_path) + "/")
        p.device_index = 0
        # el while drena la cola (no vacia al inicio)
        _llenar_cola(p, 3)
        with mock.patch.object(SOUNDDEVICE, "InputStream", return_value=_FakeStream(20, p)):
            raw, _corr, _san = p.listen_and_transcribe(0.1)
        assert raw == "hola mundo"

    def test_rebusca_encuentra(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_mac_pipeline as mod

        monkeypatch.setattr(TORCH.backends.mps, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model())
        p = mod.AnkerMacPipeline(base_path=str(tmp_path) + "/")
        assert p.device_index is None  # init sin dispositivo
        # en listen_and_transcribe la rebusca encuentra el Anker
        with mock.patch.object(
            SOUNDDEVICE,
            "query_devices",
            return_value=[{"name": "PowerConf S500", "max_input_channels": 1}],
        ), mock.patch.object(SOUNDDEVICE, "InputStream", return_value=_FakeStream(20, p)):
            raw, _corr, _san = p.listen_and_transcribe(0.1)
        assert p.device_index == 0
        assert raw == "hola mundo"

    def test_stream_error(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        p.device_index = 0
        with mock.patch.object(SOUNDDEVICE, "InputStream", side_effect=RuntimeError("no device")):
            assert p.listen_and_transcribe(1.0) == ("", "", "")
        assert p.device_index is None

    def test_sin_audio(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        p.device_index = 0
        with mock.patch.object(SOUNDDEVICE, "InputStream", return_value=_FakeStream(0)):
            assert p.listen_and_transcribe(0.1) == ("", "", "")

    def test_ok_con_sanitize(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_mac_pipeline as mod

        monkeypatch.setattr(TORCH.backends.mps, "is_available", lambda: True)
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: _stt_model("  hola 192.168.1.5 mundo  "))
        p = mod.AnkerMacPipeline(base_path=str(tmp_path) + "/")
        p.device_index = 0
        with (
            mock.patch.object(SOUNDDEVICE, "InputStream", return_value=_FakeStream(20, p)),
            mock.patch("subprocess.Popen") as popen,
        ):
            raw, corrected, sanitized = p.listen_and_transcribe(0.1)
        assert raw == "hola 192.168.1.5 mundo"
        assert "192.168.1.5" in corrected
        assert "192.168.1.5" not in sanitized
        # sanitized != corrected -> notificacion de datos protegidos
        popen.assert_called_once()

    def test_ok_sin_sanitize(self, tmp_path, monkeypatch) -> None:
        _mod, p = _make(tmp_path, monkeypatch)
        p.device_index = 0
        with (
            mock.patch.object(SOUNDDEVICE, "InputStream", return_value=_FakeStream(20, p)),
            mock.patch("subprocess.Popen") as popen,
        ):
            raw, corrected, sanitized = p.listen_and_transcribe(0.1)
        assert raw == "hola mundo"
        assert sanitized == corrected
        popen.assert_not_called()

    def test_error_transcribe(self, tmp_path, monkeypatch) -> None:
        import motor.core.voice.anker_mac_pipeline as mod

        monkeypatch.setattr(TORCH.backends.mps, "is_available", lambda: True)
        model = mock.MagicMock()
        model.transcribe.side_effect = RuntimeError("stt down")
        monkeypatch.setattr(WHISPER, "load_model", lambda *a, **k: model)
        monkeypatch.setattr(mod.sd, "query_devices", lambda: [])
        p = mod.AnkerMacPipeline(base_path=str(tmp_path) + "/")
        p.device_index = 0
        with mock.patch.object(SOUNDDEVICE, "InputStream", return_value=_FakeStream(20, p)):
            assert p.listen_and_transcribe(0.1) == ("", "", "")
