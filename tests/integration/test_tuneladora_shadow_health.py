"""Tests para scripts/pro/tuneladora/shadow/shadow_health.py."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.shadow.shadow_health import (
    ROLLBACK_RULES,
    LayerResult,
    ShadowHealth,
    main,
)


def _cfg() -> Configuration:
    return Configuration()


class TestInit:
    def test_defaults(self) -> None:
        sh = ShadowHealth(_cfg())
        assert sh.layers == list(range(8))
        assert sh.fail_fast is True
        assert sh._diff_hash != ""

    def test_layers_personalizados(self) -> None:
        sh = ShadowHealth(_cfg(), layers=[0, 3])
        assert sh.layers == [0, 3]

    def test_fail_fast_false(self) -> None:
        sh = ShadowHealth(_cfg(), fail_fast=False)
        assert sh.fail_fast is False


class TestCacheKey:
    def test_key_con_hash(self) -> None:
        sh = ShadowHealth(_cfg())
        k1 = sh._cache_key(1)
        k2 = sh._cache_key(1)
        assert k1 == k2
        assert "shadow_l1" in k1


class TestVerdict:
    def test_ok(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(0, "env", "OK")]
        assert sh._verdict() == "OK"

    def test_warn(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(0, "env", "WARN")]
        assert sh._verdict() == "WARN"

    def test_fail_prioridad(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(0, "env", "WARN"), LayerResult(1, "s", "FAIL")]
        assert sh._verdict() == "FAIL"

    def test_abort_prioridad_maxima(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(0, "env", "ABORT")]
        assert sh._verdict() == "ABORT"


class TestShouldRollback:
    def test_rollback_requerido(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(1, "static", "FAIL")]
        assert sh._should_rollback() is True

    def test_sin_rollback(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(0, "env", "FAIL")]  # layer 0 rule = none
        assert sh._should_rollback() is False

    def test_warn_no_rollback(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(1, "static", "WARN")]
        assert sh._should_rollback() is False


class TestRunLayer:
    def test_capa_desconocida_skip(self) -> None:
        sh = ShadowHealth(_cfg())
        result = sh.run_layer(9)
        assert result.status == "SKIP"

    def test_handler_ok_y_cache(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._layer0_env = mock.Mock(return_value=LayerResult(0, "env", "OK", checks=[{"a": 1}]))
        r1 = sh.run_layer(0)
        sh.run_layer(0)
        assert r1.status == "OK"
        assert sh._layer0_env.call_count == 1  # segundo viene de cache

    def test_handler_error(self) -> None:
        sh = ShadowHealth(_cfg())

        def boom():
            raise RuntimeError("x")

        sh._layer0_env = boom
        result = sh.run_layer(0)
        assert result.status == "FAIL"
        assert "x" in result.error


class TestRunAll:
    def test_todo_ok(self) -> None:
        sh = ShadowHealth(_cfg(), layers=[0, 3])
        sh.run_layer = mock.Mock(return_value=LayerResult(0, "x", "OK"))
        results = sh.run_all()
        assert len(results) == 2
        assert sh._duration_ms >= 0

    def test_fail_fast_aborta(self) -> None:
        sh = ShadowHealth(_cfg(), layers=[0, 1, 2])
        sh.run_layer = mock.Mock(
            side_effect=[LayerResult(0, "env", "OK"), LayerResult(1, "static", "FAIL")]
        )
        results = sh.run_all()
        assert len(results) == 2  # para en layer 1

    def test_layer_invalido_skip(self) -> None:
        sh = ShadowHealth(_cfg(), layers=[-1, 8])
        sh.run_layer = mock.Mock(return_value=LayerResult(0, "x", "OK"))
        results = sh.run_all()
        assert results == []


class TestRender:
    def test_json(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(0, "env", "OK", checks=[], duration_ms=5.0)]
        sh._duration_ms = 100.0
        import json

        data = json.loads(sh.render_json())
        assert data["verdict"] == "OK"
        assert data["rollback"] is False
        assert data["layers"][0]["layer"] == 0

    def test_text(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(1, "static", "FAIL")]
        text = sh.render_text()
        assert "FAIL" in text
        assert "Rollback required" in text


class TestLayersConcretos:
    def test_layer0_env(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._layer0_env = mock.Mock(return_value=LayerResult(0, "env", "OK"))
        r = sh.run_layer(0)
        assert r.status == "OK"

    def test_layer1_sin_diff_files(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._diff_files = []
        r = sh._layer1_static()
        assert r.status == "SKIP"

    def test_layer2_sin_diff_files(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._diff_files = []
        r = sh._layer2_runtime()
        assert r.status == "SKIP"

    def test_layer3_sin_diff_files(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._diff_files = []
        r = sh._layer3_shadow()
        assert r.status == "OK"

    def test_layer4_chaos_ok(self) -> None:
        sh = ShadowHealth(_cfg())
        with mock.patch(
            "scripts.pro.tuneladora.shadow.shadow_health.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="5 passed", stderr=""),
        ):
            r = sh._layer4_chaos()
        assert r.status == "OK"

    def test_layer4_chaos_fail(self) -> None:
        sh = ShadowHealth(_cfg())
        with mock.patch(
            "scripts.pro.tuneladora.shadow.shadow_health.subprocess.run",
            return_value=SimpleNamespace(returncode=1, stdout="", stderr="err"),
        ):
            r = sh._layer4_chaos()
        assert r.status == "FAIL"

    def test_layer5_y_6_skip(self) -> None:
        sh = ShadowHealth(_cfg())
        assert sh._layer5_regression().status == "SKIP"
        assert sh._layer6_trend().status == "SKIP"

    def test_layer7_promotion(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._results = [LayerResult(0, "env", "OK")]
        assert sh._layer7_promotion().status == "OK"
        sh._results = [LayerResult(0, "env", "WARN")]
        assert sh._layer7_promotion().status == "WARN"
        sh._results = [LayerResult(0, "env", "FAIL")]
        assert sh._layer7_promotion().status == "FAIL"

    def test_rollback_rules(self) -> None:
        assert ROLLBACK_RULES[0] == "none"
        assert ROLLBACK_RULES[1] == "full"
        assert ROLLBACK_RULES[7] == "full"


class TestMain:
    def test_all_json_exit_0(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["shadow_health.py", "--json"])
        sh = mock.Mock()
        sh.run_all.return_value = []
        sh.render_json.return_value = "{}"
        sh._verdict.return_value = "OK"
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.shadow_health.ShadowHealth", lambda *a, **k: sh)
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0

    def test_rango_layers(self, monkeypatch) -> None:
        capturado: dict = {}

        class FakeSH:
            def __init__(self, cfg, layers, fail_fast):
                capturado["layers"] = layers
                capturado["fail_fast"] = fail_fast

            def run_all(self):
                return []

            def _verdict(self):
                return "FAIL"

            def render_text(self):
                return "x"

        monkeypatch.setattr("sys.argv", ["shadow_health.py", "--layer", "1-3", "--no-fail-fast"])
        monkeypatch.setattr("scripts.pro.tuneladora.shadow.shadow_health.ShadowHealth", FakeSH)
        with pytest.raises(SystemExit) as e:
            main()
        assert capturado["layers"] == [1, 2, 3]
        assert capturado["fail_fast"] is False
        assert e.value.code == 1


class TestEnsureDiffCache:
    def test_git_error_silencioso(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.shadow_health.subprocess.run",
            mock.Mock(side_effect=OSError("no git")),
        )
        sh = ShadowHealth.__new__(ShadowHealth)
        sh.cfg = _cfg()
        sh._diff_files = []
        sh._diff_hash = ""
        sh._ensure_diff_cache()
        assert sh._diff_files == []
        assert sh._diff_hash == ""

    def test_filtra_no_py(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "scripts.pro.tuneladora.shadow.shadow_health.subprocess.run",
            lambda *a, **k: SimpleNamespace(
                returncode=0,
                stdout="a.py\nb.txt\nc.py\n",
                stderr="",
            ),
        )
        sh = ShadowHealth.__new__(ShadowHealth)
        sh.cfg = _cfg()
        sh._ensure_diff_cache()
        assert sh._diff_files == ["a.py", "c.py"]


class TestLayersConDiffFiles:
    def test_layer1_static_con_archivos(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._diff_files = ["a.py"]
        runner = mock.Mock()
        runner.phase_static.return_value = [
            SimpleNamespace(status="OK"), SimpleNamespace(status="WARN")
        ]
        sh._get_or_create_runner = mock.Mock(return_value=runner)
        r = sh._layer1_static()
        assert r.status == "WARN"

    def test_layer2_runtime_con_archivos(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._diff_files = ["a.py"]
        runner = mock.Mock()
        runner.phase_dynamic.return_value = [SimpleNamespace(status="FAIL")]
        sh._get_or_create_runner = mock.Mock(return_value=runner)
        r = sh._layer2_runtime()
        assert r.status == "FAIL"

    def test_layer3_con_archivos(self) -> None:
        sh = ShadowHealth(_cfg())
        sh._diff_files = ["a.py"]
        with mock.patch(
            "scripts.pro.tuneladora.shadow.shadow_health.run_layer3",
            return_value=[SimpleNamespace(status="WARN"), SimpleNamespace(status="OK")],
        ):
            r = sh._layer3_shadow()
        assert r.status == "WARN"

    def test_layer4_timeout(self) -> None:
        sh = ShadowHealth(_cfg())
        import subprocess as _sp
        with mock.patch(
            "scripts.pro.tuneladora.shadow.shadow_health.subprocess.run",
            mock.Mock(side_effect=_sp.TimeoutExpired(cmd="pytest", timeout=120)),
        ):
            r = sh._layer4_chaos()
        assert r.status == "FAIL"
        assert "Timeout" in r.error
