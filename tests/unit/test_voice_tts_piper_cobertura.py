"""Cobertura 100x100 de motor/core/voice/tts_piper.py (TASK-20260820-005).

Cubre PiperTTSMotor: init (modelo/config/piper faltantes o presentes),
_find_anker_output_device, _execute_piper_and_play, hablar_asincrono y
speak_to_file, con subprocess/sounddevice/soundfile mockeados.
"""

from __future__ import annotations

from unittest import mock

import pytest

from tests.unit._voice_fakes import SOUNDDEVICE, SOUNDFILE

pytest.importorskip("sounddevice")


@pytest.fixture()
def tts(tmp_path, monkeypatch):
    from motor.core.voice import tts_piper as mod

    monkeypatch.setattr(mod, "VOICES_DIR", tmp_path / "voices")
    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "es_ES-davefx-medium.onnx").write_bytes(b"modelo")
    (tmp_path / "voices" / "es_ES-davefx-medium.onnx.json").write_text("{}")
    piper = tmp_path / "piper"
    piper.write_text("#!/bin/sh\nexit 0")
    piper.chmod(0o755)
    monkeypatch.setattr(mod, "PIPER_BIN", str(piper))
    monkeypatch.setattr(mod.sd, "query_devices", lambda: [])
    from motor.core.voice.tts_piper import PiperTTSMotor

    return mod, PiperTTSMotor(stt_pipeline=None)


class TestInit:
    def test_ok(self, tts) -> None:
        _mod, motor = tts
        assert motor.model_path.endswith("onnx")
        assert motor.device_index is None

    def test_modelo_no_existe(self, tmp_path, monkeypatch) -> None:
        from motor.core.voice import tts_piper as mod

        monkeypatch.setattr(mod, "VOICES_DIR", tmp_path / "nope")
        with pytest.raises(FileNotFoundError):
            mod.PiperTTSMotor()

    def test_config_no_existe(self, tmp_path, monkeypatch) -> None:
        from motor.core.voice import tts_piper as mod

        monkeypatch.setattr(mod, "VOICES_DIR", tmp_path / "voices")
        (tmp_path / "voices").mkdir()
        (tmp_path / "voices" / "es_ES-davefx-medium.onnx").write_bytes(b"modelo")
        monkeypatch.setattr(mod, "PIPER_BIN", str(tmp_path / "piper"))
        (tmp_path / "piper").write_text("#!/bin/sh\nexit 0")
        (tmp_path / "piper").chmod(0o755)
        with pytest.raises(FileNotFoundError):
            mod.PiperTTSMotor()

    def test_piper_no_existe(self, tmp_path, monkeypatch) -> None:
        from motor.core.voice import tts_piper as mod

        monkeypatch.setattr(mod, "VOICES_DIR", tmp_path / "voices")
        (tmp_path / "voices").mkdir()
        (tmp_path / "voices" / "es_ES-davefx-medium.onnx").write_bytes(b"modelo")
        (tmp_path / "voices" / "es_ES-davefx-medium.onnx.json").write_text("{}")
        monkeypatch.setattr(mod, "PIPER_BIN", str(tmp_path / "missing-piper"))
        with pytest.raises(RuntimeError):
            mod.PiperTTSMotor()


class TestFindDevice:
    def test_encuentra_anker(self, tts) -> None:
        _mod, motor = tts
        devs = [{"name": "USB PowerConf S500", "max_output_channels": 2}]
        with mock.patch.object(SOUNDDEVICE, "query_devices", return_value=devs):
            assert motor._find_anker_output_device() == 0

    def test_sin_match(self, tts) -> None:
        _mod, motor = tts
        devs = [{"name": "HDMI", "max_output_channels": 2}]
        with mock.patch.object(SOUNDDEVICE, "query_devices", return_value=devs):
            assert motor._find_anker_output_device() is None

    def test_excepcion(self, tts) -> None:
        _mod, motor = tts
        with mock.patch.object(SOUNDDEVICE, "query_devices", side_effect=RuntimeError("x")):
            assert motor._find_anker_output_device() is None


class TestExecutePiper:
    def test_ok(self, tts, tmp_path, monkeypatch) -> None:
        _mod, motor = tts
        wav = tmp_path / "out.wav"
        wav.write_bytes(b"RIFF")
        motor.output_wav = str(wav)
        proc = mock.MagicMock()
        with (
            mock.patch("subprocess.Popen", return_value=proc) as popen,
            mock.patch.object(SOUNDFILE, "read", return_value=([0.1, 0.2], 16000)),
            mock.patch.object(SOUNDDEVICE, "play") as play,
            mock.patch.object(SOUNDDEVICE, "wait") as wait,
        ):
            motor._execute_piper_and_play("hola")
        popen.assert_called_once()
        assert proc.communicate.call_count == 1
        play.assert_called_once()
        wait.assert_called_once()
        assert not wav.exists()

    def test_ok_con_pipeline(self, tts, tmp_path) -> None:
        _mod, motor = tts
        pipeline = mock.MagicMock()
        pipeline.is_playing_tts = False
        motor.pipeline = pipeline
        wav = tmp_path / "out.wav"
        wav.write_bytes(b"RIFF")
        motor.output_wav = str(wav)
        with (
            mock.patch("subprocess.Popen", return_value=mock.MagicMock()),
            mock.patch.object(SOUNDFILE, "read", return_value=([0.1], 16000)),
            mock.patch.object(SOUNDDEVICE, "play"),
            mock.patch.object(SOUNDDEVICE, "wait"),
        ):
            motor._execute_piper_and_play("hola")
        assert pipeline.is_playing_tts is False

    def test_sin_wav_generado(self, tts, tmp_path) -> None:
        _mod, motor = tts
        motor.output_wav = str(tmp_path / "no-existe.wav")
        with mock.patch("subprocess.Popen", return_value=mock.MagicMock()):
            motor._execute_piper_and_play("hola")

    def test_excepcion_capturada(self, tts, tmp_path) -> None:
        _mod, motor = tts
        wav = tmp_path / "out.wav"
        wav.write_bytes(b"RIFF")
        motor.output_wav = str(wav)
        with mock.patch("subprocess.Popen", side_effect=RuntimeError("boom")):
            motor._execute_piper_and_play("hola")
        assert not wav.exists()

    def test_pipeline_sin_tts_flag(self, tts) -> None:
        _mod, motor = tts
        pipeline = mock.MagicMock()
        motor.pipeline = pipeline
        # sin wav: no hay sf.read ni play, pero finally resetea el flag
        motor.output_wav = "/tmp/no-existe-ura.wav"
        with mock.patch("subprocess.Popen", return_value=mock.MagicMock()):
            motor._execute_piper_and_play("x")
        assert pipeline.is_playing_tts is False


class TestHablarAsync:
    def test_texto_vacio_no_crea_thread(self, tts) -> None:
        _mod, motor = tts
        with mock.patch("threading.Thread") as th:
            motor.hablar_asincrono("   ")
        th.assert_not_called()

    def test_crea_thread_daemon(self, tts) -> None:
        _mod, motor = tts
        with mock.patch("threading.Thread") as th:
            motor.hablar_asincrono("hola")
        th.assert_called_once()
        kwargs = th.call_args.kwargs
        assert kwargs["daemon"] is True
        assert kwargs["target"] == motor._execute_piper_and_play
        assert kwargs["args"] == ("hola",)


class TestSpeakToFile:
    def test_ok(self, tts) -> None:
        _mod, motor = tts
        out = "/tmp/ura_test_speak.wav"
        proc = mock.MagicMock()
        with mock.patch("subprocess.Popen", return_value=proc) as popen:
            assert motor.speak_to_file("texto", out) == out
        popen.assert_called_once()
        assert proc.communicate.call_count == 1

    def test_con_pipeline(self, tts) -> None:
        _mod, motor = tts
        pipeline = mock.MagicMock()
        motor.pipeline = pipeline
        with mock.patch("subprocess.Popen", return_value=mock.MagicMock()):
            motor.speak_to_file("texto", "/tmp/ura_test_speak2.wav")
        assert pipeline.is_playing_tts is False


def test_repr(tts) -> None:
    _mod, motor = tts
    assert "PiperTTSMotor" in repr(motor)
