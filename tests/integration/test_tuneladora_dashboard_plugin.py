"""Tests para scripts/pro/tuneladora/plugins/dashboard.py."""

from __future__ import annotations

import io
from unittest import mock

from scripts.pro.tuneladora.plugins.dashboard import DashboardHandler, DashboardPlugin


def _make_handler(path: str) -> DashboardHandler:
    handler = object.__new__(DashboardHandler)
    handler.path = path
    handler.wfile = io.BytesIO()
    handler.send_response = mock.Mock()
    handler.send_header = mock.Mock()
    handler.end_headers = mock.Mock()
    return handler


class TestDashboardHandler:
    def test_root_envia_html(self) -> None:
        h = _make_handler("/")
        h._send_html()
        body = h.wfile.getvalue().decode()
        assert "URA Tuneladora" in body
        assert "RUNNING" in body
        h.send_response.assert_called_with(200)

    def test_api_status_envia_json(self) -> None:
        h = _make_handler("/api/status")
        h._send_json()
        import json

        data = json.loads(h.wfile.getvalue().decode())
        assert data == {"running": True, "pipelines": ["health", "cleanup", "audit"]}
        h.send_response.assert_called_with(200)

    def test_do_get_root(self) -> None:
        h = _make_handler("/")
        h._send_html = mock.Mock()
        h.do_GET()
        h._send_html.assert_called_once()

    def test_do_get_api(self) -> None:
        h = _make_handler("/api/status")
        h._send_json = mock.Mock()
        h.do_GET()
        h._send_json.assert_called_once()

    def test_do_get_404(self) -> None:
        h = _make_handler("/no-existe")
        h.do_GET()
        h.send_response.assert_called_with(404)

    def test_log_message_silencioso(self) -> None:
        h = _make_handler("/")
        h.log_message("formato %s", "arg")  # no debe lanzar


class TestDashboardPlugin:
    def test_start_monta_servidor(self) -> None:
        engine = mock.Mock()
        plugin = DashboardPlugin(engine, port=0)
        server = mock.Mock()
        with mock.patch("scripts.pro.tuneladora.plugins.dashboard.HTTPServer", return_value=server) as m_http:
            plugin.start()
        m_http.assert_called_once()
        server.serve_forever.assert_called_once()
