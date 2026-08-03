"""Tests para motor/assistant/web_search.py y motor/cli/cmd_pipeline.py."""
from __future__ import annotations

from unittest import mock

import pytest

from motor.assistant.web_search import WebSearch


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *a, **k):
        return self._resp


class TestWebSearch:
    @pytest.mark.asyncio
    async def test_search_ok(self, monkeypatch) -> None:
        html = (
            '<a class="result__a" href="x">Titulo 1</a>\n'
            '<div class="result__snippet">Snippet 1</div>\n'
            '<a class="result__a" href="y">Titulo 2</a>\n'
            '<div class="result__snippet">Snippet 2</div>\n'
        )
        resp = FakeResp(200, html)
        monkeypatch.setattr("motor.assistant.web_search.httpx.AsyncClient", lambda *a, **k: FakeClient(resp))
        ws = WebSearch()
        results = await ws.search("test", max_results=2)
        assert len(results) == 2
        assert results[0]["title"] == "Titulo 1"
        assert results[0]["snippet"] == "Snippet 1"

    @pytest.mark.asyncio
    async def test_search_status_no_200(self, monkeypatch) -> None:
        resp = FakeResp(500, "")
        monkeypatch.setattr("motor.assistant.web_search.httpx.AsyncClient", lambda *a, **k: FakeClient(resp))
        assert await WebSearch().search("q") == []

    @pytest.mark.asyncio
    async def test_search_excepcion(self, monkeypatch) -> None:
        class ClienteRoto:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                raise OSError("net")

        monkeypatch.setattr("motor.assistant.web_search.httpx.AsyncClient", lambda *a, **k: ClienteRoto())
        assert await WebSearch().search("q") == []

    def test_parse_results(self) -> None:
        html = (
            '<a class="result__a" href="1">Primero</a>\n'
            '<div class="result__snippet">snip1</div>\n'
            '<a class="result__a" href="2">Segundo</a>\n'
        )
        ws = WebSearch()
        results = ws._parse_results(html, 5)
        assert len(results) == 2
        assert results[0]["title"] == "Primero"
        assert results[1]["snippet"] == ""

    def test_parse_limita(self) -> None:
        html = "\n".join(f'<div class="result__a">{i}</div>' for i in range(10))
        results = WebSearch()._parse_results(html, 3)
        assert len(results) == 3

    def test_parse_sin_resultados(self) -> None:
        assert WebSearch()._parse_results("<html>vacio</html>", 5) == []


class TestCmdPipeline:
    def test_cmd_pipeline(self, monkeypatch) -> None:
        from motor.cli.cmd_pipeline import cmd_pipeline

        orch = mock.Mock()
        orch.run.return_value = mock.Mock(ok=True)
        monkeypatch.setattr("motor.cli.cmd_pipeline.Orchestrator", mock.Mock(return_value=orch))
        monkeypatch.setattr("motor.cli.cmd_pipeline.sys.exit", mock.Mock())
        config = mock.Mock()
        args = mock.Mock()
        args.dry_run = True
        cmd_pipeline(config, args)
        orch.run.assert_called_once_with(dry_run=True)

    def test_cmd_scan(self, monkeypatch) -> None:
        from motor.cli.cmd_pipeline import cmd_scan

        sc = mock.Mock()
        monkeypatch.setattr("motor.cli.cmd_pipeline.Scanner", mock.Mock(return_value=sc))
        cmd_scan(mock.Mock())
        sc.run.assert_called_once()

    def test_cmd_diagnose(self, monkeypatch) -> None:
        from motor.cli.cmd_pipeline import cmd_diagnose

        qdrant = mock.Mock()
        monkeypatch.setattr("motor.cli.cmd_pipeline.QdrantClient", mock.Mock(instancia=lambda c: qdrant))
        diag = mock.Mock()
        monkeypatch.setattr("motor.cli.cmd_pipeline.Diagnostico", mock.Mock(return_value=diag))
        cmd_diagnose(mock.Mock())
        diag.run.assert_called_once()

    def test_cmd_calibrate_sin_baseline(self, monkeypatch, tmp_path) -> None:
        from motor.cli.cmd_pipeline import cmd_calibrate

        cal = mock.Mock()
        cal.hay_baseline = False
        monkeypatch.setattr("motor.cli.cmd_pipeline.Calibration", mock.Mock(return_value=cal))
        sc = mock.Mock()
        sc.run.return_value = mock.Mock()
        monkeypatch.setattr("motor.cli.cmd_pipeline.Scanner", mock.Mock(return_value=sc))
        config = mock.Mock()
        config.deploy_dir = str(tmp_path)
        args = mock.Mock()
        args.force = False
        cmd_calibrate(config, args)
        cal.learn.assert_called_once()

    def test_cmd_calibrate_con_baseline_sin_force(self, monkeypatch, tmp_path) -> None:
        from motor.cli.cmd_pipeline import cmd_calibrate

        cal = mock.Mock()
        cal.hay_baseline = True
        monkeypatch.setattr("motor.cli.cmd_pipeline.Calibration", mock.Mock(return_value=cal))
        exit_called = []

        def _fake_exit(code):
            exit_called.append(code)
            raise SystemExit(code)

        monkeypatch.setattr("motor.cli.cmd_pipeline.sys.exit", mock.Mock(side_effect=_fake_exit))
        config = mock.Mock()
        config.deploy_dir = str(tmp_path)
        args = mock.Mock()
        args.force = False
        with pytest.raises(SystemExit):
            cmd_calibrate(config, args)
        assert exit_called == [1]

    def test_cmd_calibrate_con_trends(self, monkeypatch, tmp_path) -> None:
        from motor.cli.cmd_pipeline import ARCHIVO_TRENDS, cmd_calibrate

        cal = mock.Mock()
        cal.hay_baseline = False
        monkeypatch.setattr("motor.cli.cmd_pipeline.Calibration", mock.Mock(return_value=cal))
        monkeypatch.setattr("motor.cli.cmd_pipeline.Scanner", mock.Mock(return_value=mock.Mock()))
        config = mock.Mock()
        config.deploy_dir = str(tmp_path)
        (tmp_path / ARCHIVO_TRENDS).write_text('{"a": 1}\n{"b": 2}\n')
        args = mock.Mock()
        args.force = False
        cmd_calibrate(config, args)
        trends = cal.learn.call_args.args[1]
        assert len(trends) == 2
