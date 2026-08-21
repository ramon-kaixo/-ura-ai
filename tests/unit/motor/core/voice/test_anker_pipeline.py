"""Tests de AnkerDeterministicPipeline contra la API actual.

Firma actual (motor/core/voice/anker_pipeline.py):
``__init__(db_path=DB_PATH, model_size=DEFAULT_MODEL)``

Diferencias con la API antigua reflejadas aquí:
- ``use_cuda``/``sample_rate``/``block_size`` ya NO son parámetros:
  son constantes de módulo (SAMPLE_RATE=16000, BLOCK_SIZE=480).
- ``_find_*_device`` devuelven ``int | None`` (índice físico), no dict.
- El constructor lanza RuntimeError si ``torch.cuda.is_available()`` es False.
"""

import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from motor.core.voice.anker_pipeline import AnkerDeterministicPipeline

DEVICES_ANKER = [
    {"name": "Anker PowerConf S500", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
    {"name": "Default Input", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
]
DEVICES_SIN_ANKER = [
    {"name": "Default Input", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
]
DEVICES_SIN_ENTRADA = [
    {"name": "Solo Salida", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
]


def _pipeline_con_mocks(
    db_path: str | Path,
    query_devices: list[dict] | None = None,
    cuda: bool = True,
) -> tuple[AnkerDeterministicPipeline, MagicMock, MagicMock]:
    """Construye el pipeline con todos los mocks de dependencias externas."""
    stt = MagicMock()
    with (
        patch("torch.cuda.is_available", return_value=cuda),
        patch("sounddevice.query_devices", return_value=query_devices or DEVICES_ANKER),
        patch("whisper.load_model", return_value=stt) as mock_load,
    ):
        pipe = AnkerDeterministicPipeline(db_path=db_path, model_size="small")
    return pipe, stt, mock_load


def test_init_success() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        pipe, stt, mock_load = _pipeline_con_mocks(db_path)
        assert pipe.db_path == db_path
        assert pipe.sample_rate == 16000
        assert pipe.block_size == 480
        assert pipe.device == "cuda"
        assert pipe.device_index == 0
        assert pipe.stt_model is stt
        mock_load.assert_called_once_with("small", device="cuda")


def test_init_sin_cuda_raise() -> None:
    with tempfile.TemporaryDirectory() as tmpdir, pytest.raises(RuntimeError, match="CUDA no disponible"):
        _pipeline_con_mocks(Path(tmpdir) / "test.db", cuda=False)


def test_init_fallback_al_default_input() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db", query_devices=DEVICES_SIN_ANKER)
        assert pipe.device_index == 0


def test_init_sin_dispositivo_de_entrada() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db", query_devices=DEVICES_SIN_ENTRADA)
        assert pipe.device_index is None


def test_find_anker_device() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db")
    with patch("sounddevice.query_devices", return_value=DEVICES_ANKER):
        assert pipe._find_anker_device() == 0
    with patch("sounddevice.query_devices", return_value=DEVICES_SIN_ANKER):
        assert pipe._find_anker_device() is None


def test_find_anker_device_ante_error_de_audio() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db")
    with patch("sounddevice.query_devices", side_effect=RuntimeError("sin backend de audio")):
        assert pipe._find_anker_device() is None
        assert pipe._find_default_input() is None


def test_find_default_input() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db")
    with patch("sounddevice.query_devices", return_value=DEVICES_ANKER):
        assert pipe._find_default_input() == 0
    with patch("sounddevice.query_devices", return_value=DEVICES_SIN_ENTRADA):
        assert pipe._find_default_input() is None


def test_init_db_crea_la_tabla_corrections() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        _pipeline_con_mocks(db_path)
        with sqlite3.connect(db_path) as conn:
            tablas = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert any(row[0] == "corrections" for row in tablas)


def test_apply_deterministic_rules_orden_longitud_y_limites() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db")
        pipe.learn_correction("hemby", "GB10")
        pipe.learn_correction("codex", "ura_codex")
        assert pipe._apply_deterministic_rules("el hemby y el codex") == "el GB10 y el ura_codex"
        assert pipe._apply_deterministic_rules("HEMBY rapido") == "GB10 rapido"
        assert pipe._apply_deterministic_rules("hembys") == "hembys"
        assert pipe._apply_deterministic_rules("") == ""


def test_learn_correction_ignora_vacios_e_iguales() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db")
        pipe.learn_correction("", "x")
        pipe.learn_correction("  ", "x")
        pipe.learn_correction("hola", "HOLA")
        assert pipe._apply_deterministic_rules("hola") == "hola"
        pipe.learn_correction("hola", "mundo")
        assert pipe._apply_deterministic_rules("hola") == "mundo"


def test_transcribe_from_file_con_correccion() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        pipe, stt, _ = _pipeline_con_mocks(db_path)
        pipe.learn_correction("hemby", "GB10")
        stt.transcribe.return_value = {"text": " el hemby "}
        audio = np.zeros((16000,), dtype=np.float32)
        with (
            patch("whisper.load_audio", return_value=audio),
            patch("whisper.pad_or_trim", return_value=audio),
        ):
            raw, final = pipe.transcribe_from_file("/tmp/fake.wav")
        assert raw == "el hemby"
        assert final == "el GB10"


def test_listen_and_transcribe_sin_dispositivo() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db", query_devices=DEVICES_SIN_ENTRADA)
        assert pipe.listen_and_transcribe() == ("", "")


def test_listen_and_transcribe_stream_falla_devuelve_vacio() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db")
        with patch("sounddevice.InputStream", side_effect=RuntimeError("boom")):
            assert pipe.listen_and_transcribe() == ("", "")


def test_listen_and_transcribe_happy_path() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        pipe, stt, _ = _pipeline_con_mocks(db_path)
        pipe.learn_correction("hemby", "GB10")
        chunk = np.zeros((480, 1), dtype=np.float32)
        stream_mock = MagicMock()

        def _entrar_stream() -> MagicMock:
            for _ in range(3):
                pipe.audio_queue.put(chunk.copy())
            return stream_mock

        stream_mock.__enter__.side_effect = _entrar_stream
        stream_mock.__exit__.return_value = False
        stt.transcribe.return_value = {"text": "  hemby  "}
        with patch("sounddevice.InputStream", return_value=stream_mock):
            raw, final = pipe.listen_and_transcribe(duration_seconds=0.1)
        assert raw == "hemby"
        assert final == "GB10"


def test_audio_callback_descarta_cuando_suena_tts() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        pipe, _, _ = _pipeline_con_mocks(Path(tmpdir) / "test.db")
        chunk = np.zeros((3,), dtype=np.float32)
        pipe.is_playing_tts = True
        pipe._audio_callback(chunk, 3, None, None)
        assert pipe.audio_queue.empty()
        pipe.is_playing_tts = False
        pipe._audio_callback(chunk, 3, None, None)
        assert pipe.audio_queue.qsize() == 1
        assert np.array_equal(pipe.audio_queue.get(), chunk)
