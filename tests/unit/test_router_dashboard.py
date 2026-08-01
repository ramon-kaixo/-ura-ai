"""Tests para dashboard (core/model_router/dashboard.py)."""

import json
import sys
import threading
import time

import pytest

sys.path.insert(0, ".")
from core.model_router.dashboard import _dashboard_json, _render_dashboard


class _LatencyGuard:
    def __enter__(self):
        return self

    def __exit__(self, *a) -> None:
        pass


@pytest.fixture
def dashboard_ctx(monkeypatch):
    """Desactiva red: latencia determinista y modelos fake."""
    monkeypatch.setattr(
        "core.model_router.proxy._update_asus_latency",
        lambda: None,
    )
    monkeypatch.setattr("core.model_router.proxy._asus_latency_lock", _LatencyGuard())
    monkeypatch.setattr("core.model_router.proxy._asus_latency_ms", -1.0)
    monkeypatch.setattr("core.model_router.proxy._asus_latency_updated", 0)
    monkeypatch.setattr(
        "core.model_router.proxy._fallback_count_last_hour",
        lambda: 0,
    )
    monkeypatch.setattr(
        "core.model_router.proxy._get_active_backend_label",
        lambda: "Local Mac",
    )
    monkeypatch.setattr(
        "core.model_router.model_selection.obtener_modelos_disponibles",
        lambda url=None: {"qwen3:32b", "qwen2.5:7b"},
    )
    monkeypatch.setattr(
        "core.model_router.model_selection.MODELO_ROUTES",
        {"razonamiento": {"modelos": ["qwen3:32b"], "descripcion": "Razonamiento"}},
    )
    yield


class TestRenderDashboard:
    def test_html_contains_placeholders_replaced(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "AUTO")
        monkeypatch.setattr("core.model_router.router.get_ollama_url", lambda: "http://ollama:11434")
        html = _render_dashboard()
        for placeholder in ("{sc}", "{bl}", "{bu}", "{lc}", "{al}", "{lu}", "{fc}", "{fbc}", "{asel}", "{tsel}", "{esel}", "{ph}"):
            assert placeholder not in html
        assert "AUTO" in html
        assert "http://ollama:11434" in html

    def test_power_hints_per_mode(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "TURBO")
        html = _render_dashboard()
        assert "Fallback local bloqueado" in html
        assert "selected" in html
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "ECO")
        html = _render_dashboard()
        assert "Mac local" in html

    def test_latency_negative_renders_na(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.proxy._asus_latency_ms", -1.0)
        html = _render_dashboard()
        assert "N/A" in html
        assert "ASUS no accesible" in html

    def test_latency_high_renders_alert(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.proxy._asus_latency_ms", 350.0)
        monkeypatch.setattr("core.model_router.proxy._asus_latency_updated", time.time())
        html = _render_dashboard()
        assert "350.0 ms" in html
        assert "alta" in html

    def test_latency_ok_renders_green(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.proxy._asus_latency_ms", 42.0)
        monkeypatch.setattr("core.model_router.proxy._asus_latency_updated", time.time())
        html = _render_dashboard()
        assert "42.0 ms" in html
        assert "value-green" in html

    def test_fallback_count_0_green(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr(
            "core.model_router.proxy._fallback_count_last_hour",
            lambda: 0,
        )
        html = _render_dashboard()
        assert 'id="fallback-count">0</div>' in html

    def test_fallback_count_high_red(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr(
            "core.model_router.proxy._fallback_count_last_hour",
            lambda: 9,
        )
        html = _render_dashboard()
        assert 'id="fallback-count">9</div>' in html
        assert "value-red" in html


class TestDashboardJson:
    def test_json_shape(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "AUTO")
        monkeypatch.setattr("core.model_router.router.get_ollama_url", lambda: "http://ollama:11434")
        data = json.loads(_dashboard_json("127.0.0.1"))
        assert data["power_mode"] == "AUTO"
        assert data["backend_url"] == "http://ollama:11434"
        assert data["fallback_count_1h"] == 0
        models = {m["name"] for m in data["models"]}
        assert models == {"qwen3:32b", "qwen2.5:7b"}

    def test_json_turbo_forces_remote(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "TURBO")
        data = json.loads(_dashboard_json("192.168.1.50"))
        assert data["backend_label"] == "ASUS Remoto"

    def test_json_eco_forces_local(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.router.POWER_MODE", "ECO")
        data = json.loads(_dashboard_json("192.168.1.50"))
        assert data["backend_label"] == "Local Mac"

    def test_json_model_tasks_resolved(self, dashboard_ctx, monkeypatch) -> None:
        data = json.loads(_dashboard_json())
        qwen = next(m for m in data["models"] if m["name"] == "qwen3:32b")
        assert "razonamiento" in qwen["tasks"]

    def test_json_empty_models(self, dashboard_ctx, monkeypatch) -> None:
        monkeypatch.setattr(
            "core.model_router.model_selection.obtener_modelos_disponibles",
            lambda url=None: set(),
        )
        data = json.loads(_dashboard_json())
        assert data["models"] == []

    def test_json_lock_used(self, dashboard_ctx, monkeypatch) -> None:
        acquired = threading.Lock()

        class _TrackingGuard:
            def __init__(self):
                self.entered = False

            def __enter__(self):
                self.entered = True
                return self

            def __exit__(self, *a) -> None:
                pass

        guard = _TrackingGuard()
        monkeypatch.setattr("core.model_router.proxy._asus_latency_lock", guard)
        json.loads(_dashboard_json())
        assert guard.entered
        assert acquired is not None
