"""Tests for core/agents/telemetry.py."""

from unittest.mock import MagicMock, patch

from motor.core.agents.telemetry import Telemetria


class TestCheckOllama:
    def test_con_llm_inyectado(self):
        mock_llm = MagicMock()
        mock_llm.health.return_value = {"status": "ok", "modelos_disponibles": ["a", "b"]}
        tel = Telemetria(llm=mock_llm)
        assert tel._check_ollama() == "2 modelos"

    def test_con_llm_down(self):
        mock_llm = MagicMock()
        mock_llm.health.return_value = {"status": "error"}
        tel = Telemetria(llm=mock_llm)
        assert tel._check_ollama() == "down"

    @patch("motor.core.llm.health", return_value={"status": "ok", "modelos_disponibles": ["x"]})
    def test_fallback_a_motor(self, mock_health):
        tel = Telemetria(llm=None)
        assert tel._check_ollama() == "1 modelos"
        mock_health.assert_called_once()


class TestLlmStats:
    def test_con_config(self, tmp_path, monkeypatch):
        config = tmp_path / "chunk_config.json"
        config.write_text('{"chunk_actual": 4096, "modelo": "qwen", "historico": [1, 2]}')
        monkeypatch.setattr("motor.core.agents.telemetry.NERVIOSO", tmp_path)
        result = Telemetria.llm_stats()
        assert result["chunk_actual"] == 4096
        assert result["modelo"] == "qwen"
        assert result["historico_ajustes"] == 2

    def test_sin_config(self, tmp_path, monkeypatch):
        monkeypatch.setattr("motor.core.agents.telemetry.NERVIOSO", tmp_path)
        result = Telemetria.llm_stats()
        assert result["chunk_actual"] == 8192
        assert result["modelo"] == "?"


class TestF821Count:
    @patch("motor.core.agents.telemetry.subprocess.run")
    def test_cuenta_errores(self, mock_run):
        mock_run.return_value.stdout = "F821\nF821\nF821\n"
        result = Telemetria.f821_count()
        assert result == 3
        mock_run.assert_called_once()

    @patch("motor.core.agents.telemetry.subprocess.run", side_effect=Exception("boom"))
    def test_error(self, mock_run):
        result = Telemetria.f821_count()
        assert result == -1


class TestReporteCompleto:
    def test_estructura(self):
        tel = Telemetria()
        with (
            patch.object(tel, "hardware", return_value={"ram": 1000}),
            patch.object(tel, "red", return_value={"router": "ok"}),
            patch.object(tel, "llm_stats", return_value={"modelo": "qwen"}),
            patch.object(tel, "f821_count", return_value=5),
        ):
            result = tel.reporte_completo()
            assert "hardware" in result
            assert "red" in result
            assert "llm" in result
            assert "f821" in result
            assert result["f821"] == 5


class TestHardware:
    def test_con_psutil(self):
        fake_vm = MagicMock()
        fake_vm.total = 16 * 1024 * 1024 * 1024
        fake_vm.available = 8 * 1024 * 1024 * 1024
        fake_vm.percent = 50.0
        with patch.dict(
            "sys.modules",
            {
                "psutil": MagicMock(
                    virtual_memory=MagicMock(return_value=fake_vm), cpu_percent=MagicMock(return_value=20.0)
                )
            },
        ):
            result = Telemetria.hardware()
        assert result["ram_total_mb"] == 16384
        assert result["ram_pct"] == 50.0

    def test_sin_psutil_proc(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "psutil", None)
        cm = MagicMock()
        cm.__enter__.return_value.__iter__.return_value = iter(
            ["MemTotal:       121920 kB", "MemAvailable:    65536 kB"]
        )
        with patch("motor.core.agents.telemetry.Path.open", return_value=cm):
            result = Telemetria.hardware()
        assert result["ram_libre_mb"] == 64

    def test_sin_psutil_exception(self, monkeypatch):
        import os
        import sys

        monkeypatch.setitem(sys.modules, "psutil", None)
        with patch("builtins.open", side_effect=OSError("no /proc")):
            result = Telemetria.hardware()
        # El fallback detecta la RAM real del host (no hardcode) — debe ser > 0.
        expected = (os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")) // (1024 * 1024)
        assert result["ram_total_mb"] == expected


class TestRed:
    def test_ok(self):
        fake_r = MagicMock()
        fake_r.status_code = 200
        fake_r.text = "ok"
        with (
            patch("httpx.get", return_value=fake_r) as mock_get,
            patch.object(Telemetria, "_check_ollama", return_value="3 modelos"),
        ):
            tel = Telemetria()
            result = tel.red()
        assert result["model_router"] == "ok"
        assert result["ollama"] == "3 modelos"
        mock_get.assert_called_once()

    def test_router_error(self):
        with (
            patch("httpx.get", side_effect=Exception("conn")),
            patch.object(Telemetria, "_check_ollama", return_value="down"),
        ):
            tel = Telemetria()
            result = tel.red()
        assert result["model_router"] == "down"

    def test_ollama_error(self):
        fake_r = MagicMock()
        fake_r.status_code = 200
        fake_r.text = "ok"
        with (
            patch("httpx.get", return_value=fake_r),
            patch.object(Telemetria, "_check_ollama", side_effect=Exception("boom")),
        ):
            tel = Telemetria()
            result = tel.red()
        assert result["ollama"] == "down"


class TestCheckOllamaExtra:
    def test_modelos_no_lista(self):
        mock_llm = MagicMock()
        mock_llm.health.return_value = {"status": "ok", "modelos_disponibles": "notalist"}
        tel = Telemetria(llm=mock_llm)
        assert tel._check_ollama() == "down"


class TestShadowHealth:
    def test_on_layer_start(self, caplog):
        tel = Telemetria()
        tel.on_layer_start(1, "test")

    def test_on_layer_end(self):
        tel = Telemetria()
        tel.on_layer_end(1, "test", "ok", 12.5)
