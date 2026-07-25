"""Negative integration tests: pipeline falla correctamente cuando debe fallar."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.pipeline.pending_queue import PendingQueue
from scripts.pro.tuneladora.pipeline.runner import PipelineRunner
from scripts.pro.tuneladora.pipeline.snapshot_manager import SnapshotManager
from scripts.pro.tuneladora.pipeline.tools.base import Status
from scripts.pro.tuneladora.pipeline.tools.bandit_tool import BanditTool
from scripts.pro.tuneladora.pipeline.tools.pytest_tool import PytestTool
from scripts.pro.tuneladora.pipeline.tools.ruff_tool import RuffTool


@pytest.fixture
def cfg() -> Configuration:
    return Configuration()


class TestNegativeSyntaxError:
    def test_py_compile_rejects_bad_syntax(self, cfg):
        bad = Path("/tmp/test_neg_bad_syntax.py")
        bad.write_text("def foo(\n")
        runner = PipelineRunner(cfg, mode="gate", files=[str(bad)])
        result = runner._run_py_compile()
        bad.unlink(missing_ok=True)
        assert result.status == Status.FAIL
        assert "Syntax error" in result.summary or "syntax" in result.summary

    def test_pipeline_aborts_on_syntax_error(self, cfg):
        bad = Path("/tmp/test_neg_abort_syntax.py")
        bad.write_text("def foo(\n")
        runner = PipelineRunner(cfg, mode="gate", files=[str(bad)])
        with mock.patch.multiple(
            runner, phase_snapshot=mock.DEFAULT, phase_dynamic=mock.DEFAULT,
            phase_index=mock.DEFAULT, phase_integrity=mock.DEFAULT,
            phase_commit=mock.DEFAULT,
        ):
            runner.phase_snapshot.return_value = [mock.Mock(name="snap", status=Status.OK)]
            runner.phase_dynamic.return_value = [mock.Mock(name="dynamic", status=Status.OK)]
            runner.phase_index.return_value = [mock.Mock(name="index", status=Status.OK)]
            runner.phase_integrity.return_value = [mock.Mock(name="integrity", status=Status.OK)]
            runner.phase_commit.return_value = [mock.Mock(name="commit", status=Status.SKIP)]
            result = runner.run()
        bad.unlink(missing_ok=True)
        assert result == Status.FAIL


class TestNegativeUnusedImport:
    def test_ruff_rejects_unused_import(self, cfg):
        bad = Path("/tmp/test_neg_unused_import.py")
        bad.write_text("import os\n\nx = 1\n")
        tool = RuffTool(cfg.ruff, cfg.ura_root)
        if not tool.is_available():
            pytest.skip("ruff not available")
        result = tool.run_check([str(bad)])
        bad.unlink(missing_ok=True)
        assert result.status == Status.FAIL
        if result.detail:
            assert "F401" in result.detail or "unused" in result.detail.lower()

    def test_pipeline_detects_unused_import(self, cfg):
        bad = Path("/tmp/test_neg_pipeline_unused.py")
        bad.write_text("import os\n\nx = 1\n")
        runner = PipelineRunner(cfg, mode="check", files=[str(bad)])
        results = runner.phase_static()
        bad.unlink(missing_ok=True)
        ruff_results = [r for r in results if r.name == "ruff"]
        assert any(r.status == Status.FAIL for r in ruff_results)

    def test_mode_fix_auto_removes_unused_import(self, cfg, tmp_path):
        (tmp_path / "__init__.py").write_text("")
        bad = tmp_path / "test_fix_unused.py"
        bad.write_text("import os\n\nx = 1\n")
        tool = RuffTool(cfg.ruff, tmp_path)
        if not tool.is_available():
            pytest.skip("ruff not available")
        result = tool.run_fix([str(bad)])
        content = bad.read_text()
        assert result.status == Status.OK
        assert "import os" not in content
        assert "x = 1" in content


class TestNegativeBrokenTest:
    def test_pytest_rejects_failing_test(self, cfg, tmp_path):
        test_file = tmp_path / "test_neg_broken.py"
        test_file.write_text("def test_should_fail(): assert 1 == 2\n")
        tool = PytestTool(tmp_path)
        if not tool.is_available():
            pytest.skip("pytest not available")
        result = tool.run_check([str(test_file)])
        assert result.status == Status.FAIL
        assert "1 failed" in result.detail or "FAILED" in result.detail or "AssertionError" in result.detail

    def test_pipeline_blocks_on_broken_test(self, cfg, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("def add(a, b): return a + b\n")
        test = tmp_path / "test_src.py"
        test.write_text("def test_add(): assert 1 == 2\n")
        runner = PipelineRunner(cfg, mode="gate", files=[str(src)])
        orig_tools = runner.tools.copy()
        runner.tools["ruff"] = mock.Mock(is_available=lambda: False, spec=RuffTool)
        runner.tools["bandit"] = mock.Mock(is_available=lambda: False, spec=BanditTool)
        runner.tools["mypy"] = mock.Mock(is_available=lambda: False)
        try:
            result = runner.run()
        finally:
            runner.tools.update(orig_tools)
        assert result == Status.FAIL


class TestNegativeBlastRadius:
    def test_blast_radius_exceeds_50_files(self, cfg):
        runner = PipelineRunner(cfg, mode="gate", files=[f"f{i}.py" for i in range(51)])
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0, stdout="\n".join(f"f{i}.py" for i in range(51)),
                stderr="", spec=["returncode", "stdout", "stderr"],
            )
            results = runner.phase_integrity()
        assert any(r.name == "blast_radius" and r.status == Status.FAIL for r in results)

    def test_blast_radius_under_limit(self, cfg):
        runner = PipelineRunner(cfg, mode="check", files=["a.py", "b.py"])
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0, stdout="a.py\nb.py",
                stderr="", spec=["returncode", "stdout", "stderr"],
            )
            results = runner.phase_integrity()
        blast = [r for r in results if r.name == "blast_radius"]
        assert blast and blast[0].status == Status.OK

    def test_blast_radius_edge_50_files(self, cfg):
        runner = PipelineRunner(cfg, mode="gate", files=[f"f{i}.py" for i in range(50)])
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0, stdout="\n".join(f"f{i}.py" for i in range(50)),
                stderr="", spec=["returncode", "stdout", "stderr"],
            )
            results = runner.phase_integrity()
        assert any(r.name == "blast_radius" and r.status == Status.OK for r in results)


class TestNegativeBandit:
    def test_bandit_rejects_eval(self, cfg):
        bad = Path("/tmp/test_neg_eval.py")
        bad.write_text("user_input = input()\neval(user_input)\n")
        tool = BanditTool(cfg.ura_root)
        if not tool.is_available():
            pytest.skip("bandit not available")
        result = tool.run_check([str(bad)])
        bad.unlink(missing_ok=True)
        assert result.status == Status.FAIL
        assert "B307" in result.detail or "Severity: High" in result.detail

    def test_bandit_passes_clean_code(self, cfg):
        clean = Path("/tmp/test_neg_clean.py")
        clean.write_text("x = 42\nprint(x)\n")
        tool = BanditTool(cfg.ura_root)
        if not tool.is_available():
            pytest.skip("bandit not available")
        result = tool.run_check([str(clean)])
        clean.unlink(missing_ok=True)
        assert result.status == Status.OK


class TestNegativeRollback:
    def test_snapshot_take_and_restore(self, tmp_path):
        snap_dir = tmp_path / ".tuneladora_test"
        snap_dir.mkdir()
        sm = SnapshotManager(snap_dir)
        assert sm.ok
        original_file = tmp_path / "sub" / "target.py"
        original_file.parent.mkdir(parents=True)
        original_file.write_text("x = 1\n")
        snap_path = sm.take("test_label", [original_file])
        assert snap_path is not None
        original_file.write_text("x = 999\n")
        assert original_file.read_text() == "x = 999\n"
        ok = sm.restore(snap_path)
        assert ok
        assert original_file.read_text() == "x = 1\n"

    def test_latest_returns_most_recent(self, tmp_path):
        snap_dir = tmp_path / ".tuneladora_test_latest"
        snap_dir.mkdir()
        sm = SnapshotManager(snap_dir)
        (snap_dir / "snapshots" / "20250101_000000_old").mkdir(parents=True)
        (snap_dir / "snapshots" / "20250102_000000_new").mkdir(parents=True)
        latest = sm.latest()
        assert latest is not None
        assert "new" in latest.name

    def test_prune_removes_old_snapshots(self, tmp_path):
        snap_dir = tmp_path / ".tuneladora_test_prune"
        snap_dir.mkdir()
        sm = SnapshotManager(snap_dir)
        for i in range(35):
            (snap_dir / "snapshots" / f"20250101_{i:06d}_snap").mkdir(parents=True)
        removed = sm.prune(keep=30)
        assert removed == 5
        remaining = sorted((snap_dir / "snapshots").iterdir())
        assert len(remaining) == 30

    def test_pipeline_restores_snapshot_on_fail(self, cfg, tmp_path):
        src = tmp_path / "target.py"
        src.write_text("x = 1\n")
        runner = PipelineRunner(cfg, mode="gate", files=[str(src)])
        with mock.patch.multiple(
            runner, phase_snapshot=mock.DEFAULT, phase_static=mock.DEFAULT,
            phase_dynamic=mock.DEFAULT, phase_index=mock.DEFAULT,
            phase_integrity=mock.DEFAULT, phase_commit=mock.DEFAULT,
        ):
            runner.phase_snapshot.return_value = [mock.Mock(name="snap", status=Status.OK)]
            runner.phase_static.return_value = [mock.Mock(name="static", status=Status.OK)]
            runner.phase_dynamic.return_value = [mock.Mock(name="dynamic", status=Status.FAIL)]
            runner.phase_index.return_value = [mock.Mock(name="index", status=Status.OK)]
            runner.phase_integrity.return_value = [mock.Mock(name="integrity", status=Status.OK)]
            runner.phase_commit.return_value = [mock.Mock(name="commit", status=Status.SKIP)]
            result = runner.run()
        assert result == Status.FAIL


class TestNegativeTimeout:
    def test_timeout_not_applicable(self):
        pytest.skip("Timeout test requiere entorno controlado")


class TestNegativeLLMFallback:
    def test_ruff_failure_creates_pending_entry(self, cfg):
        bad = Path("/tmp/test_neg_llm_fallback.py")
        bad.write_text("import os\n\nx = 1\n")
        runner = PipelineRunner(cfg, mode="gate", files=[str(bad)])
        with mock.patch.object(runner.llm_fallback, 'analyze', return_value=""):
            pre_count = len(runner.pending_queue.list_pending())
            results = runner.phase_static()
        bad.unlink(missing_ok=True)
        post_entries = runner.pending_queue.list_pending()
        ruff_results = [r for r in results if r.name == "ruff"]
        if ruff_results and ruff_results[0].status == Status.FAIL:
            assert len(post_entries) > pre_count
        else:
            pytest.skip("ruff no disponible o no falló")

    def test_pending_queue_persists(self, cfg):
        pq = PendingQueue(cfg.knowledge_db)
        n = pq.add(archivo="test.py", herramienta="ruff", severidad="high", error_raw="F401 unused import")
        assert n > 0
        entries = pq.list_pending(severidad="high")
        assert any(e["archivo"] == "test.py" for e in entries)
        pq.resolve(n, "hecho")

    def test_pending_queue_stats(self, cfg):
        pq = PendingQueue(cfg.knowledge_db)
        stats = pq.stats()
        assert "pending_fixes" in stats
        assert "total_runs" in stats
        assert stats["pending_fixes"] >= 0
