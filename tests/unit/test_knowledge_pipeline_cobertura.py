"""Cobertura 100x100 de knowledge/engine/pipeline.py (TASK-20260815-003).

Cubre todas las etapas del pipeline DAG (snapshot, compile, verify,
archive, qdrant, rule_eval, ci) y la clase Pipeline (init, run,
run_compile_chain) inyectando módulos fake en sys.modules: los imports
de etapa son dinámicos dentro de pipeline.py.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine.pipeline import (
    Pipeline,
    PipelineResult,
    Stage,
    _run_archive,
    _run_ci,
    _run_compile,
    _run_qdrant,
    _run_rule_eval,
    _run_snapshot,
    _run_verify,
)


class FakeRuleConn:
    """Conexión sqlite fake para el stage rule_eval."""

    def __init__(self, rows: list[dict[str, Any]], edges: list[dict[str, str]]) -> None:
        self._rows = rows
        self._edges = edges
        self._last = ""
        self.closed = False

    def execute(self, sql: str) -> FakeRuleConn:
        self._last = sql
        return self

    def fetchall(self) -> list[Any]:
        return self._rows if "kg_nodes" in self._last else self._edges

    def close(self) -> None:
        self.closed = True


class FakeRuleEvaluator:
    """RuleEvaluator fake con findings de severidades mixtas."""

    def evaluate(
        self,
        documents: list[dict[str, Any]],
        all_node_ids: set[str],
        all_relation_targets: set[str],
    ) -> list[SimpleNamespace]:
        self.seen = (documents, all_node_ids, all_relation_targets)
        return [
            SimpleNamespace(severity="ERROR"),
            SimpleNamespace(severity="WARN"),
        ]


def _install(monkeypatch: pytest.MonkeyPatch, name: str, **attrs: Any) -> None:
    """Registra un módulo fake en sys.modules (los imports de etapa son dinámicos)."""
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    monkeypatch.setitem(sys.modules, name, mod)


def _break_import(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Fuerza ImportError en el import dinámico de una etapa."""
    monkeypatch.setitem(sys.modules, name, None)


def _compile_ok(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(
        success=True,
        documents_total=5,
        documents_changed=2,
        errors=[],
        warnings=["w1"],
        graph_version="v1",
    )


class TestRunSnapshot:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(
            monkeypatch,
            "knowledge.engine.scanner",
            scan_incremental=lambda prev, src: ([1, 2], "snap", [Path("skip.txt")], [3]),
        )
        result = _run_snapshot(Path("src"))
        assert result.stage == Stage.SNAPSHOT
        assert result.success is True
        assert result.duration_ms >= 0
        assert result.output == {
            "changed": 2,
            "deleted": 1,
            "snapshot": "snap",
            "skipped": ["skip.txt"],
        }

    def test_error_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _break_import(monkeypatch, "knowledge.engine.scanner")
        result = _run_snapshot(Path("src"))
        assert result.stage == Stage.SNAPSHOT
        assert result.success is False
        assert result.error != ""


class TestRunCompile:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch, "knowledge.engine.compiler", compile_source=_compile_ok)
        result = _run_compile(Path("src"), Path("db"), "cid")
        assert result.stage == Stage.COMPILE
        assert result.success is True
        assert result.output == {
            "documents_total": 5,
            "documents_changed": 2,
            "errors": 0,
            "warnings": 1,
            "graph_version": "v1",
        }

    def test_result_fallido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def compile_fail(**kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(
                success=False,
                documents_total=0,
                documents_changed=0,
                errors=["e1"],
                warnings=[],
                graph_version=None,
            )

        _install(monkeypatch, "knowledge.engine.compiler", compile_source=compile_fail)
        result = _run_compile(Path("src"), Path("db"))
        assert result.success is False
        assert result.output["errors"] == 1

    def test_error_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _break_import(monkeypatch, "knowledge.engine.compiler")
        result = _run_compile(Path("src"), Path("db"))
        assert result.success is False
        assert result.error != ""


class TestRunVerify:
    def test_sin_errores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(monkeypatch, "knowledge.engine.verifier", verify_graph=lambda db: [])
        result = _run_verify(Path("db"))
        assert result.stage == Stage.VERIFY
        assert result.success is True
        assert result.output == {"checks": 0, "errors": 0}

    def test_con_errores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(
            monkeypatch,
            "knowledge.engine.verifier",
            verify_graph=lambda db: [("ERROR", "x"), ("OK", "y")],
        )
        result = _run_verify(Path("db"))
        assert result.success is False
        assert result.output == {"checks": 2, "errors": 1}

    def test_error_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _break_import(monkeypatch, "knowledge.engine.verifier")
        result = _run_verify(Path("db"))
        assert result.success is False
        assert result.error != ""


class TestRunArchive:
    def test_success_con_commit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(
            monkeypatch,
            "knowledge.engine.archiver",
            archive_source=lambda **kw: SimpleNamespace(
                source_commit="a" * 20,
                file_count=3,
                content_sha256="b" * 32,
            ),
        )
        result = _run_archive(Path("src"), Path("db"))
        assert result.stage == Stage.ARCHIVE
        assert result.success is True
        assert result.output == {
            "commit": "a" * 12,
            "files": 3,
            "sha256": "b" * 16,
        }

    def test_success_sin_commit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(
            monkeypatch,
            "knowledge.engine.archiver",
            archive_source=lambda **kw: SimpleNamespace(
                source_commit=None,
                file_count=0,
                content_sha256="c" * 32,
            ),
        )
        result = _run_archive(Path("src"), Path("db"), archive_dir=Path("arch"))
        assert result.success is True
        assert result.output["commit"] == ""

    def test_error_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _break_import(monkeypatch, "knowledge.engine.archiver")
        result = _run_archive(Path("src"), Path("db"))
        assert result.success is False
        assert result.error != ""


class TestRunQdrant:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(
            monkeypatch,
            "knowledge.engine.qdrant_sync",
            sync_documents=lambda **kw: 7,
        )
        result = _run_qdrant(Path("db"))
        assert result.stage == Stage.QDRANT
        assert result.success is True
        assert result.output == {"synced": 7}

    def test_degradacion_gradual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(**kwargs: Any) -> Any:
            raise RuntimeError("qdrant down")

        _install(monkeypatch, "knowledge.engine.qdrant_sync", sync_documents=boom)
        result = _run_qdrant(Path("db"))
        assert result.success is True
        assert result.output == {"synced": 0}
        assert "Qdrant" in result.error


class TestRunCi:
    def test_script_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "exists", lambda self: False)
        result = _run_ci()
        assert result.stage == Stage.CI
        assert result.success is False
        assert "not found" in result.error

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: SimpleNamespace(returncode=0, stdout="x" * 500, stderr=""),
        )
        result = _run_ci()
        assert result.success is True
        assert result.output["returncode"] == 0
        assert result.output["stdout_preview"] == "x" * 300
        assert result.error == ""

    def test_fallo_returncode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
        )
        result = _run_ci()
        assert result.success is False
        assert result.error == "boom"

    def test_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def timeout(*args: Any, **kwargs: Any) -> Any:
            raise TimeoutExpired("bash", 300)

        monkeypatch.setattr("subprocess.run", timeout)
        result = _run_ci()
        assert result.success is False
        assert "bash" in result.error


class TestRunRuleEval:
    def _rows(self) -> list[dict[str, Any]]:
        return [
            {"id": "n1", "path": "p1", "frontmatter": '{"title": "T", "tags": ["a"]}', "body": "body"},
            {"id": "n2", "path": "p2", "frontmatter": None, "body": None},
            {"id": "n3", "path": "p3", "frontmatter": "", "body": ""},
        ]

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        evaluator = FakeRuleEvaluator()
        _install(
            monkeypatch,
            "knowledge.engine.connection",
            open_db=lambda p: FakeRuleConn(
                self._rows(),
                [{"src": "n1", "dst": "n2"}, {"src": "n2", "dst": "n3"}],
            ),
        )
        _install(monkeypatch, "knowledge.engine.rules", RuleEvaluator=lambda: evaluator)
        result = _run_rule_eval(Path("db"))
        assert result.stage == Stage.RULE_EVAL
        assert result.success is True
        assert result.output == {"documents": 3, "findings": 2, "errors": 1}

    def test_relaciones_y_frontmatter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        evaluator = FakeRuleEvaluator()
        _install(
            monkeypatch,
            "knowledge.engine.connection",
            open_db=lambda p: FakeRuleConn(
                self._rows(),
                [{"src": "n1", "dst": "n2"}, {"src": "n2", "dst": "n3"}],
            ),
        )
        _install(monkeypatch, "knowledge.engine.rules", RuleEvaluator=lambda: evaluator)
        _run_rule_eval(Path("db"))
        docs, node_ids, targets = evaluator.seen
        assert node_ids == {"n1", "n2", "n3"}
        assert targets == {"n2", "n3"}
        n1 = next(d for d in docs if d["id"] == "n1")
        assert n1["title"] == "T"
        assert n1["tags"] == ["a"]
        assert n1["relations"] == ["n2"]
        n2 = next(d for d in docs if d["id"] == "n2")
        assert n2["title"] == ""
        assert n2["body"] == ""

    def test_error_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _break_import(monkeypatch, "knowledge.engine.connection")
        result = _run_rule_eval(Path("db"))
        assert result.success is False
        assert result.error != ""


class TestPipelineInit:
    def test_defaults_source_dir_y_db_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen_source: list[Path] = []
        seen_db: list[Path] = []

        def scan(prev: Any, src: Path) -> tuple[list, str, list, list]:
            seen_source.append(src)
            return [], "snap", [], []

        _install(monkeypatch, "knowledge.engine.scanner", scan_incremental=scan)
        _install(
            monkeypatch,
            "knowledge.engine.verifier",
            verify_graph=lambda db: seen_db.append(db) or [],
        )
        pipe = Pipeline()
        pipe.run(stages=[Stage.SNAPSHOT, Stage.VERIFY])
        assert seen_source == [Path.cwd()]
        assert seen_db == [Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"]

    def test_valores_explicitos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen_archive: list[Path | None] = []

        def archive(**kwargs: Any) -> SimpleNamespace:
            seen_archive.append(kwargs.get("archive_dir"))
            return SimpleNamespace(source_commit=None, file_count=0, content_sha256="d" * 32)

        _install(monkeypatch, "knowledge.engine.archiver", archive_source=archive)
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"), archive_dir=Path("arch"))
        pipe.run(stages=[Stage.ARCHIVE])
        assert seen_archive == [Path("arch")]

    def test_archive_dir_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen_archive: list[Path | None] = []

        def archive(**kwargs: Any) -> SimpleNamespace:
            seen_archive.append(kwargs.get("archive_dir"))
            return SimpleNamespace(source_commit=None, file_count=0, content_sha256="e" * 32)

        _install(monkeypatch, "knowledge.engine.archiver", archive_source=archive)
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"))
        pipe.run(stages=[Stage.ARCHIVE])
        assert seen_archive == [None]


class TestPipelineRun:
    def _install_todo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install(
            monkeypatch,
            "knowledge.engine.scanner",
            scan_incremental=lambda prev, src: ([], "snap", [], []),
        )
        _install(monkeypatch, "knowledge.engine.compiler", compile_source=_compile_ok)
        _install(monkeypatch, "knowledge.engine.verifier", verify_graph=lambda db: [])
        _install(
            monkeypatch,
            "knowledge.engine.archiver",
            archive_source=lambda **kw: SimpleNamespace(
                source_commit="a" * 20,
                file_count=1,
                content_sha256="b" * 32,
            ),
        )
        _install(monkeypatch, "knowledge.engine.qdrant_sync", sync_documents=lambda **kw: 3)
        _install(monkeypatch, "knowledge.engine.connection", open_db=lambda p: FakeRuleConn([], []))
        _install(monkeypatch, "knowledge.engine.rules", RuleEvaluator=FakeRuleEvaluator)

    def test_todas_las_etapas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._install_todo(monkeypatch)
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        )
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"))
        result = pipe.run(correlation_id="cid-1")
        assert result.success is True
        assert result.total_duration_ms >= 0
        assert result.correlation_id == "cid-1"
        assert [s.stage for s in result.stages] == list(Stage)
        assert all(s.success for s in result.stages)

    def test_stages_explicitos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._install_todo(monkeypatch)
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"))
        result = pipe.run(stages=[Stage.COMPILE, Stage.VERIFY])
        assert len(result.stages) == 2
        assert [s.stage for s in result.stages] == [Stage.COMPILE, Stage.VERIFY]

    def test_correlation_id_autogenerado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._install_todo(monkeypatch)
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"))
        result = pipe.run(stages=[Stage.COMPILE])
        assert result.correlation_id != ""
        assert len(result.correlation_id) == 32

    def test_stage_desconocido(self) -> None:
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"))
        result = pipe.run(stages=["bogus"])  # type: ignore[list-item]
        assert len(result.stages) == 1
        assert result.success is False
        assert result.stages[0].error == "Unknown stage: bogus"

    def test_overall_fallido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._install_todo(monkeypatch)
        _break_import(monkeypatch, "knowledge.engine.connection")
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"))
        result = pipe.run(stages=[Stage.COMPILE, Stage.VERIFY, Stage.RULE_EVAL])
        assert result.success is False
        assert result.stages[0].success is True
        assert result.stages[2].success is False

    def test_stages_vacio_ejecuta_todas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._install_todo(monkeypatch)
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
        )
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"))
        result = pipe.run(stages=[])
        assert [s.stage for s in result.stages] == list(Stage)
        assert result.success is True


class TestRunCompileChain:
    def test_cadena(self, monkeypatch: pytest.MonkeyPatch) -> None:
        TestPipelineRun._install_todo(self, monkeypatch)
        pipe = Pipeline(source_dir=Path("s"), db_path=Path("db"))
        result = pipe.run_compile_chain()
        assert [s.stage for s in result.stages] == [
            Stage.COMPILE,
            Stage.VERIFY,
            Stage.RULE_EVAL,
        ]
        assert result.success is True
        assert isinstance(result, PipelineResult)
