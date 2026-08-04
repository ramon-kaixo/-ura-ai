"""Tests para generate_index.py y block_reviewer.py."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.generate_index import build_index, extract_calls, extract_functions, main as gi_main
from scripts.pro.tuneladora.pipeline.block_reviewer import _do_review, _get_diff, review_block


def _cfg(tmp_path: Path) -> Configuration:
    cfg = Configuration()
    cfg.ura_root = tmp_path
    cfg.tuneladora_dir = tmp_path / "tuneladora"
    cfg.tuneladora_dir.mkdir(parents=True, exist_ok=True)
    cfg.knowledge_db = tmp_path / "kb.db"
    cfg.ollama_url = "http://localhost:11434"
    cfg.review_model = "qwen"
    cfg.timeout_llm = 30
    return cfg


class TestExtractFunctions:
    def test_funciones_y_clases(self, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("def foo():\n    pass\nclass Bar:\n    pass\nasync def baz():\n    pass\n")
        funcs = extract_functions(f)
        names = {(x["name"], x["type"]) for x in funcs}
        assert names == {("foo", "function"), ("Bar", "class"), ("baz", "function")}

    def test_syntax_error(self, tmp_path: Path) -> None:
        f = tmp_path / "b.py"
        f.write_text("def roto(:\n")
        assert extract_functions(f) == []


class TestExtractCalls:
    def test_atributo_y_nombre(self, tmp_path: Path) -> None:
        f = tmp_path / "c.py"
        f.write_text("config.get('a')\nprint('x')\n")
        calls = extract_calls(f)
        assert ("config", "get") in calls
        assert ("module", "print") in calls

    def test_syntax_error(self, tmp_path: Path) -> None:
        f = tmp_path / "d.py"
        f.write_text("def roto(:\n")
        assert extract_calls(f) == []


class TestBuildIndex:
    def test_con_archivos(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        src = tmp_path / "scripts" / "pro" / "tuneladora"
        src.mkdir(parents=True)
        f = src / "mod.py"
        f.write_text("def func1():\n    pass\nclass Cls1:\n    pass\n")
        with mock.patch(
            "scripts.pro.tuneladora.generate_index.SemanticMemory",
            return_value=mock.Mock(),
        ) as m_sem:
            index = build_index(cfg, changed_files=[f])
        assert index["stats"]["functions"] == 2
        assert index["stats"]["classes"] == 1
        assert index["stats"]["files"] == 1
        m_sem.return_value.learn_concept.assert_called()
        index_file = cfg.tuneladora_dir / "repo_index.json"
        assert index_file.exists()
        data = json.loads(index_file.read_text())
        assert data["stats"]["files"] == 1

    def test_sin_archivos_descubre(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        src = tmp_path / "scripts" / "pro" / "tuneladora"
        src.mkdir(parents=True)
        (src / "m.py").write_text("def x():\n    pass\n")
        with mock.patch(
            "scripts.pro.tuneladora.generate_index.SemanticMemory",
            return_value=mock.Mock(),
        ):
            index = build_index(cfg)
        assert index["stats"]["files"] == 1


class TestBlockReviewer:
    def test_review_block_lanza_thread(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        with mock.patch("scripts.pro.tuneladora.pipeline.block_reviewer._do_review") as m_do:
            review_block(cfg, "bloque1", head="abc", tests=["t1"], api_diff="api")
        assert m_do.call_count == 1
        args = m_do.call_args[0]
        assert args[1] == "bloque1"
        assert args[2] == "abc"
        assert args[3] == ["t1"]

    def test_do_review_ok(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        resp = SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"response": "# hallazgos"},
        )
        with mock.patch(
            "scripts.pro.tuneladora.pipeline.block_reviewer.requests.post",
            return_value=resp,
        ) as m_post, mock.patch(
            "scripts.pro.tuneladora.pipeline.block_reviewer._get_diff",
            return_value="+diff",
        ):
            _do_review(cfg, "b1", "head1", ["t1"], "api")
        files = list((cfg.tuneladora_dir / "reviews").glob("block_b1_*.md"))
        assert len(files) == 1
        assert "# hallazgos" in files[0].read_text()
        prompt = m_post.call_args[1]["json"]["prompt"]
        assert "+diff" in prompt
        assert "t1" in prompt

    def test_do_review_llm_falla(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        with mock.patch(
            "scripts.pro.tuneladora.pipeline.block_reviewer.requests.post",
            side_effect=RuntimeError("conn"),
        ), mock.patch(
            "scripts.pro.tuneladora.pipeline.block_reviewer._get_diff",
            return_value="",
        ):
            _do_review(cfg, "b2", "", [], "")
        files = list((cfg.tuneladora_dir / "reviews").glob("block_b2_*.md"))
        assert "Error generating review" in files[0].read_text()

    def test_get_diff_con_head(self, tmp_path: Path) -> None:
        with mock.patch(
            "scripts.pro.tuneladora.pipeline.block_reviewer.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="+++ diff largo"),
        ) as m_run:
            out = _get_diff(tmp_path, head="abc123")
        assert "diff largo" in out
        assert "HEAD..abc123" in m_run.call_args[0][0]

    def test_get_diff_sin_head(self, tmp_path: Path) -> None:
        with mock.patch(
            "scripts.pro.tuneladora.pipeline.block_reviewer.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=""),
        ):
            assert _get_diff(tmp_path) == "(no diff)"

    def test_get_diff_error(self, tmp_path: Path) -> None:
        with mock.patch(
            "scripts.pro.tuneladora.pipeline.block_reviewer.subprocess.run",
            mock.Mock(side_effect=OSError("x")),
        ):
            out = _get_diff(tmp_path)
        assert "error" in out


class TestGenerateIndexMain:
    def test_main(self, monkeypatch, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        monkeypatch.setattr("sys.argv", ["generate_index.py"])
        monkeypatch.setattr(
            "scripts.pro.tuneladora.generate_index.Configuration",
            lambda: cfg,
        )
        with mock.patch("scripts.pro.tuneladora.generate_index.subprocess.run") as m_run:
            m_run.return_value = SimpleNamespace(returncode=0, stdout="a.py\n")
            with mock.patch("scripts.pro.tuneladora.generate_index.build_index") as m_build:
                gi_main()
        m_build.assert_called_once()
