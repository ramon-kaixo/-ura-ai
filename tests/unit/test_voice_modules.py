from __future__ import annotations

"""Tests para core/voice/ — tts_piper, anker_pipeline, anker_mac_pipeline.

Las dependencias de hardware (sounddevice, soundfile, torch, whisper, numpy)
estan instaladas; los sinks de audio se mockean para no tocar hardware real.
"""

import pytest

pytestmark = pytest.mark.slow
pytest.importorskip("torch")


import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest


class TestPiperTTSMotor:
    @pytest.fixture
    def tts(self, tmp_path, monkeypatch):
        from core.voice import tts_piper as mod

        monkeypatch.setattr(mod, "VOICES_DIR", tmp_path / "voices")
        (tmp_path / "voices").mkdir()
        (tmp_path / "voices" / "es_ES-davefx-medium.onnx").write_bytes(b"modelo")
        (tmp_path / "voices" / "es_ES-davefx-medium.onnx.json").write_text("{}")
        (tmp_path / "voices" / "es_ES-davefx-medium.onnx.onnx").write_bytes(b"x")
        piper = tmp_path / "piper"
        piper.write_text("#!/bin/sh\nexit 0")
        piper.chmod(0o755)
        monkeypatch.setattr(mod, "PIPER_BIN", str(piper))
        with mock.patch.object(mod.sd, "query_devices", return_value=[]):
            from core.voice.tts_piper import PiperTTSMotor

            return PiperTTSMotor(stt_pipeline=None)

    def test_init_find_devices(self, tts) -> None:
        assert tts.model_path.endswith("onnx")
        assert tts.output_wav == "/tmp/ura_tts_output.wav"

    def test_init_voice_no_existe(self, tmp_path, monkeypatch) -> None:
        from core.voice import tts_piper as mod

        monkeypatch.setattr(mod, "VOICES_DIR", tmp_path / "nope")
        with pytest.raises(FileNotFoundError):
            from core.voice.tts_piper import PiperTTSMotor

            PiperTTSMotor()

    def test_repr(self, tts) -> None:
        assert "PiperTTSMotor" in repr(tts)

    def test_hablar_asincrono_vacio(self, tts) -> None:
        tts.hablar_asincrono("   ")  # no debe crear thread

    def test_hablar_asincrono_thread(self, tts, monkeypatch) -> None:
        thread = mock.Mock()
        monkeypatch.setattr("threading.Thread", lambda *a, **k: thread)
        tts.hablar_asincrono("hola")
        thread.start.assert_called_once()

    def test_speak_to_file(self, tts, monkeypatch, tmp_path) -> None:
        proc = mock.Mock()
        proc.communicate.return_value = (b"", b"")
        monkeypatch.setattr("subprocess.Popen", mock.Mock(return_value=proc))
        out = tmp_path / "out.wav"
        ruta = tts.speak_to_file("hola", str(out))
        assert ruta == str(out)
        proc.communicate.assert_called_once_with(input="hola")

    def test_speak_to_file_con_pipeline(self, tts, monkeypatch, tmp_path) -> None:
        pipeline = mock.Mock()
        tts.pipeline = pipeline
        proc = mock.Mock()
        proc.communicate.return_value = (b"", b"")
        monkeypatch.setattr("subprocess.Popen", mock.Mock(return_value=proc))
        tts.speak_to_file("hola", str(tmp_path / "o.wav"))
        assert pipeline.is_playing_tts is False  # restaurado tras finally


class TestAnkerPipeline:
    @pytest.fixture
    def pipeline(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.voice.anker_pipeline.DB_PATH", str(tmp_path / "corrections.db"))
        from core.voice.anker_pipeline import AnkerDeterministicPipeline

        with mock.patch.object(__import__("sounddevice"), "query_devices", return_value=[]):
            with mock.patch("whisper.load_model"):
                p = AnkerDeterministicPipeline(db_path=str(tmp_path / "corrections.db"))
        return p

    def test_init_db(self, pipeline) -> None:
        assert Path(pipeline.db_path).exists()

    def test_find_anker_device(self, pipeline, monkeypatch) -> None:
        devs = [{"name": "PowerConf S500", "max_input_channels": 2}, {"name": "otro", "max_input_channels": 1}]
        monkeypatch.setattr("core.voice.anker_pipeline.sd.query_devices", lambda: devs)
        assert pipeline._find_anker_device() == 0

    def test_find_anker_device_no_existe(self, pipeline, monkeypatch) -> None:
        monkeypatch.setattr("core.voice.anker_pipeline.sd.query_devices", lambda: [{"name": "x", "max_input_channels": 0}])
        assert pipeline._find_anker_device() is None

    def test_find_anker_error(self, pipeline, monkeypatch) -> None:
        monkeypatch.setattr("core.voice.anker_pipeline.sd.query_devices", mock.Mock(side_effect=OSError("no audio")))
        assert pipeline._find_anker_device() is None

    def test_find_default_input(self, pipeline, monkeypatch) -> None:
        devs = [{"name": "mic", "max_input_channels": 1}]
        monkeypatch.setattr("core.voice.anker_pipeline.sd.query_devices", lambda: devs)
        assert pipeline._find_default_input() == 0

    def test_audio_callback_tts_playing(self, pipeline) -> None:
        pipeline.is_playing_tts = True
        indata = np.zeros((10, 1))
        pipeline._audio_callback(indata, 10, None, None)
        assert pipeline.audio_queue.empty()

    def test_audio_callback_normal(self, pipeline) -> None:
        pipeline.is_playing_tts = False
        indata = np.zeros((10, 1))
        pipeline._audio_callback(indata, 10, None, None)
        assert not pipeline.audio_queue.empty()
        pipeline.audio_queue.get()

    def test_apply_rules_vacio(self, pipeline) -> None:
        assert pipeline._apply_deterministic_rules("") == ""

    def test_apply_rules_sin_correcciones(self, pipeline) -> None:
        assert pipeline._apply_deterministic_rules("Hola Mundo") == "hola mundo"

    def test_learn_y_aplicar(self, pipeline) -> None:
        pipeline.learn_correction("quiero compra leche", "quiero comprar leche")
        out = pipeline._apply_deterministic_rules("quiero compra leche")
        assert out == "quiero comprar leche"

    def test_learn_invalido(self, pipeline) -> None:
        pipeline.learn_correction("", "x")  # key vacio
        pipeline.learn_correction("x", "")  # val vacio
        pipeline.learn_correction("igual", "IGUAL")  # key == val.lower()
        assert pipeline._apply_deterministic_rules("igual") == "igual"

    def test_learn_reemplaza(self, pipeline) -> None:
        pipeline.learn_correction("hola amigo", "hola compi")
        pipeline.learn_correction("hola amigo", "hola camarada")
        assert pipeline._apply_deterministic_rules("hola amigo") == "hola camarada"

    def test_transcribe_sin_device(self, pipeline) -> None:
        pipeline.device_index = None
        assert pipeline.listen_and_transcribe(1.0) == ("", "")

    def test_transcribe_stream_error(self, pipeline, monkeypatch) -> None:
        pipeline.device_index = 0
        monkeypatch.setattr("core.voice.anker_pipeline.sd.InputStream", mock.Mock(side_effect=OSError("no device")))
        assert pipeline.listen_and_transcribe(1.0) == ("", "")

    def test_transcribe_sin_audio(self, pipeline, monkeypatch) -> None:
        pipeline.device_index = 0
        stream = mock.Mock()
        stream.__enter__ = mock.Mock(return_value=stream)
        stream.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr("core.voice.anker_pipeline.sd.InputStream", mock.Mock(return_value=stream))
        monkeypatch.setattr(pipeline.audio_queue, "get", mock.Mock(side_effect=__import__("queue").Empty()))
        assert pipeline.listen_and_transcribe(1.0) == ("", "")

    def test_transcribe_ok(self, pipeline, monkeypatch) -> None:
        pipeline.device_index = 0
        chunk = np.zeros((480, 1), dtype=np.float32)
        stream = mock.Mock()
        stream.__enter__ = mock.Mock(return_value=stream)
        stream.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr("core.voice.anker_pipeline.sd.InputStream", mock.Mock(return_value=stream))
        def _get(timeout=None):
            if _get.called:
                raise __import__("queue").Empty()
            _get.called = True
            return chunk

        _get.called = False
        monkeypatch.setattr(pipeline.audio_queue, "get", mock.Mock(side_effect=_get))

        result = {"text": "quiero compra leche"}
        stt = mock.Mock()
        stt.transcribe.return_value = result
        pipeline.stt_model = stt
        pipeline.learn_correction("quiero compra leche", "quiero comprar leche")

        raw, final = pipeline.listen_and_transcribe(1.0)
        assert raw == "quiero compra leche"
        assert final == "quiero comprar leche"

    def test_context_manager(self, pipeline) -> None:
        with pipeline as p:
            assert p is pipeline


class TestAnkerMacPipeline:
    @pytest.fixture
    def mac(self, tmp_path, monkeypatch):
        from core.voice.anker_mac_pipeline import AnkerMacPipeline

        with mock.patch.object(__import__("sounddevice"), "query_devices", return_value=[]):
            with mock.patch("whisper.load_model"):
                p = AnkerMacPipeline(base_path=str(tmp_path) + "/", model_size="tiny")
        return p

    def test_init(self, mac) -> None:
        assert mac.sample_rate == 16000
        assert mac.is_playing_tts is False

    def test_audio_callback(self, mac) -> None:
        mac.is_playing_tts = False
        indata = np.zeros((10, 1))
        mac._audio_callback(indata, 10, None, None)
        assert not mac.audio_queue.empty()
        mac.audio_queue.get()

    def test_audio_callback_tts(self, mac) -> None:
        mac.is_playing_tts = True
        mac._audio_callback(np.zeros((10, 1)), 10, None, None)
        assert mac.audio_queue.empty()

    def test_trigger_notification_sound_valido(self, mac, monkeypatch) -> None:
        popen = mock.Mock()
        monkeypatch.setattr("core.voice.anker_mac_pipeline.subprocess.Popen", popen)
        mac._trigger_macos_notification("Título", "Mensaje", "Tink")
        cmd = popen.call_args.args[0]
        assert cmd[0] == "osascript"
        assert "Tink" in cmd[2]

    def test_trigger_notification_sound_invalido(self, mac, monkeypatch) -> None:
        popen = mock.Mock()
        monkeypatch.setattr("core.voice.anker_mac_pipeline.subprocess.Popen", popen)
        mac._trigger_macos_notification("T", "M", "NoExiste")
        cmd = popen.call_args.args[0]
        assert "Tink" in cmd[2]  # fallback

    def test_apply_rules_con_correccion_y_notificacion(self, mac, monkeypatch) -> None:
        mac.learn_correction if hasattr(mac, "learn_correction") else None
        with sqlite3.connect(mac.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO corrections VALUES (?, ?)", ("hola amigo", "hola compi"))
            conn.commit()
        notif = mock.Mock()
        monkeypatch.setattr(mac, "_trigger_macos_notification", notif)
        out = mac._apply_deterministic_rules("Hola Amigo")
        assert out == "hola compi"
        notif.assert_called_once()

    def test_listen_sin_device(self, mac) -> None:
        mac.device_index = None
        assert mac.listen_and_transcribe(1) == ("", "", "")

    def test_listen_stream_error(self, mac, monkeypatch) -> None:
        mac.device_index = 0
        monkeypatch.setattr("core.voice.anker_mac_pipeline.sd.InputStream", mock.Mock(side_effect=OSError("x")))
        assert mac.listen_and_transcribe(1) == ("", "", "")

    def test_listen_transcribe_y_sanitiza(self, mac, monkeypatch) -> None:
        mac.device_index = 0
        chunk = np.zeros((480, 1), dtype=np.float32)
        stream = mock.Mock()
        stream.__enter__ = mock.Mock(return_value=stream)
        stream.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr("core.voice.anker_mac_pipeline.sd.InputStream", mock.Mock(return_value=stream))
        # queue.get devuelve el chunk una vez, luego Empty (iteraciones cortas)
        def _get(timeout=None):
            if _get.called:
                raise __import__("queue").Empty()
            _get.called = True
            return chunk

        _get.called = False
        monkeypatch.setattr(mac.audio_queue, "get", mock.Mock(side_effect=_get))
        stt = mock.Mock()
        stt.transcribe.return_value = {"text": "hola mundo"}
        mac.stt_model = stt
        monkeypatch.setattr("core.voice.anker_mac_pipeline.sanitize_text", mock.Mock(return_value="hola mundo"))
        raw, corr, san = mac.listen_and_transcribe(1)
        assert raw == "hola mundo"
        assert san == "hola mundo"
