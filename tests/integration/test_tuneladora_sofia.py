"""Tests para scripts/pro/tuneladora/pipeline/sofia.py."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.pipeline.sofia import Sofia, SofiaHallazgo, SofiaReport


def _cfg() -> Configuration:
    cfg = Configuration()
    cfg.ollama_url = "http://localhost:11434"
    cfg.timeout_llm = 30
    return cfg


class TestShouldReview:
    def test_diff_vacio_y_api_vacio(self) -> None:
        s = Sofia(_cfg())
        assert s.should_review("", "", False, 0) is False

    def test_diff_pequeno_normal_no_revisa(self) -> None:
        s = Sofia(_cfg())
        assert s.should_review("+cambio", "", False, 1) is False

    def test_diff_grande_revisa(self) -> None:
        s = Sofia(_cfg())
        assert s.should_review("x" * 10001, "", False, 1) is True

    def test_muchos_archivos(self) -> None:
        s = Sofia(_cfg())
        assert s.should_review("", "api", False, 11) is True

    def test_tests_modificados(self) -> None:
        s = Sofia(_cfg())
        assert s.should_review("+c", "", True, 0) is True

    def test_solo_api_diff(self) -> None:
        s = Sofia(_cfg())
        assert s.should_review("", "cambio api", False, 0) is True


class TestParseResponse:
    def test_json_directo(self) -> None:
        s = Sofia(_cfg())
        raw = json.dumps(
            {
                "hallazgos": [{"tipo": "critico", "archivo": "a.py", "linea": 3, "mensaje": "m", "sugerencia": "s"}],
                "resumen": "r",
            }
        )
        report = s._parse_response(raw)
        assert report is not None
        assert report.hallazgos[0].tipo == "critico"
        assert report.hallazgos[0].linea == 3
        assert report.resumen == "r"

    def test_json_envuelto_en_texto(self) -> None:
        s = Sofia(_cfg())
        raw = 'Aquí va: {"hallazgos": [], "resumen": "ok"} fin'
        report = s._parse_response(raw)
        assert report is not None
        assert report.resumen == "ok"

    def test_sin_json(self) -> None:
        s = Sofia(_cfg())
        assert s._parse_response("texto sin json") is None

    def test_json_invalido_dentro(self) -> None:
        s = Sofia(_cfg())
        assert s._parse_response("{no es json}") is None

    def test_hallazgo_sin_campos(self) -> None:
        s = Sofia(_cfg())
        raw = json.dumps({"hallazgos": [{"tipo": "info"}], "resumen": ""})
        report = s._parse_response(raw)
        assert report.hallazgos[0].archivo == ""
        assert report.hallazgos[0].linea == 0


class TestReview:
    def test_no_revisa_sin_cambios(self) -> None:
        s = Sofia(_cfg())
        with mock.patch("requests.post") as m_post:
            report = s.review("", "", "", 0)
        assert report.hallazgos == []
        m_post.assert_not_called()

    def test_llm_exitoso(self) -> None:
        s = Sofia(_cfg())
        resp = SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {
                "response": json.dumps(
                    {
                        "hallazgos": [{"tipo": "advertencia", "archivo": "b.py", "linea": 1, "mensaje": "x"}],
                        "resumen": "r",
                    }
                )
            },
        )
        with mock.patch("requests.post", return_value=resp) as m_post:
            report = s.review("x" * 10001, "", "", 1)
        assert report.n_advertencias == 1
        assert report.modelo == "qwen2.5-coder:14b"
        assert report.duracion_ms >= 0
        m_post.assert_called_once()
        payload = m_post.call_args[1]["json"]
        assert payload["options"]["temperature"] == 0

    def test_llm_falla_silencioso(self) -> None:
        s = Sofia(_cfg())
        with mock.patch("requests.post", side_effect=RuntimeError("conn")):
            report = s.review("x" * 10001, "", "", 1)
        assert report.hallazgos == []
        assert report.n_criticos == 0

    def test_respuesta_no_json(self) -> None:
        s = Sofia(_cfg())
        resp = SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"response": "no json"},
        )
        with mock.patch("requests.post", return_value=resp):
            report = s.review("x" * 10001, "", "", 1)
        assert report.hallazgos == []
        assert report.duracion_ms >= 0

    def test_prompt_incluye_datos(self) -> None:
        s = Sofia(_cfg())
        resp = SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"response": '{"hallazgos": [], "resumen": "ok"}'},
        )
        with mock.patch("requests.post", return_value=resp) as m_post:
            s.review("+diff real", "test_mod", "api_x", 1)
        prompt = m_post.call_args[1]["json"]["prompt"]
        assert "+diff real" in prompt
        assert "test_mod" in prompt
        assert "api_x" in prompt


class TestDataclasses:
    def test_sofia_hallazgo_defaults(self) -> None:
        h = SofiaHallazgo(tipo="info", archivo="a", linea=0, mensaje="m")
        assert h.sugerencia == ""

    def test_sofia_report_defaults(self) -> None:
        r = SofiaReport()
        assert r.hallazgos == []
        assert r.n_criticos == 0
        assert r.modelo == ""
