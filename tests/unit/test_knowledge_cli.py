"""Tests para knowledge/engine/cli/ — jobs, pipeline, docs, notify."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from knowledge.engine.cli.docs import cmd_docs_generate
from knowledge.engine.cli.jobs import cmd_job_process
from knowledge.engine.cli.notify import cmd_notify_test
from knowledge.engine.cli.pipeline import cmd_pipeline_run


class FakeResult:
    def __init__(self, success=True, stages=None):
        self.success = success
        self.stages = stages or []

    class Stage:
        def __init__(self, error=None):
            self.error = error


class TestCmdJobProcess:
    def test_ok(self, monkeypatch, tmp_path) -> None:
        worker = mock.Mock()
        monkeypatch.setattr("knowledge.engine.cli.jobs.compile_worker", worker)
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), source_dir=str(tmp_path / "src"))
        assert cmd_job_process(args) == 0
        worker.assert_called_once()
        assert worker.call_args.kwargs["source_dir"] == tmp_path / "src"

    def test_sin_source_dir(self, monkeypatch, tmp_path) -> None:
        worker = mock.Mock()
        monkeypatch.setattr("knowledge.engine.cli.jobs.compile_worker", worker)
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), source_dir=None)
        cmd_job_process(args)
        assert worker.call_args.kwargs["source_dir"] is None


class TestCmdPipelineRun:
    def test_ok(self, monkeypatch, tmp_path) -> None:
        pipeline = mock.Mock()
        pipeline.run.return_value = FakeResult(success=True, stages=[FakeResult.Stage(), FakeResult.Stage(error="err")])
        monkeypatch.setattr("knowledge.engine.cli.pipeline.Pipeline", mock.Mock(return_value=pipeline))
        args = SimpleNamespace(source_dir=str(tmp_path / "src"), archive_dir=str(tmp_path / "arc"), db_path="")
        assert cmd_pipeline_run(args) == 0

    def test_fail(self, monkeypatch, tmp_path) -> None:
        pipeline = mock.Mock()
        pipeline.run.return_value = FakeResult(success=False)
        monkeypatch.setattr("knowledge.engine.cli.pipeline.Pipeline", mock.Mock(return_value=pipeline))
        args = SimpleNamespace(source_dir=None, archive_dir=None, db_path="")
        assert cmd_pipeline_run(args) == 1

    def test_db_path_directo(self, monkeypatch, tmp_path) -> None:
        pipeline = mock.Mock()
        pipeline.run.return_value = FakeResult(success=True)
        constructor = mock.Mock(return_value=pipeline)
        monkeypatch.setattr("knowledge.engine.cli.pipeline.Pipeline", constructor)
        args = SimpleNamespace(source_dir=None, archive_dir=None, db_path=str(tmp_path / "db.sqlite"))
        assert cmd_pipeline_run(args) == 0
        assert constructor.call_args.kwargs["db_path"] == tmp_path / "db.sqlite"


class TestCmdDocsGenerate:
    def test_ok(self, monkeypatch, tmp_path) -> None:
        gen = mock.Mock(return_value=10)
        monkeypatch.setattr("knowledge.engine.knowledge_base.generate_knowledge_base", gen)
        args = SimpleNamespace(output=str(tmp_path / "out"))
        assert cmd_docs_generate(args) == 0
        assert gen.call_args.kwargs["output_dir"] == tmp_path / "out"

    def test_sin_output(self, monkeypatch) -> None:
        gen = mock.Mock(return_value=5)
        monkeypatch.setattr("knowledge.engine.knowledge_base.generate_knowledge_base", gen)
        args = SimpleNamespace(output=None)
        assert cmd_docs_generate(args) == 0
        assert gen.call_args.kwargs["output_dir"] is None

    def test_cero_docs_error(self, monkeypatch) -> None:
        gen = mock.Mock(return_value=0)
        monkeypatch.setattr("knowledge.engine.knowledge_base.generate_knowledge_base", gen)
        args = SimpleNamespace(output=None)
        assert cmd_docs_generate(args) == 1


class TestCmdNotifyTest:
    def test_sin_urls_sin_notifiers(self, monkeypatch) -> None:
        service = mock.Mock()
        service.notifier_count = 0
        monkeypatch.setattr("knowledge.engine.cli.notify.get_notifier", mock.Mock(return_value=service))
        args = SimpleNamespace(webhook="", slack="")
        assert cmd_notify_test(args) == 0

    def test_con_webhook_envia(self, monkeypatch) -> None:
        service = mock.Mock()
        service.notifier_count = 1
        service.send.return_value = 1
        monkeypatch.setattr("knowledge.engine.cli.notify.get_notifier", mock.Mock(return_value=service))
        format_event = mock.Mock(return_value={"tipo": "test"})
        monkeypatch.setattr("knowledge.engine.cli.notify.format_compile_event", format_event)
        args = SimpleNamespace(webhook="https://hooks.example.com", slack="")
        assert cmd_notify_test(args) == 0
        service.send.assert_called_once()

    def test_send_falla(self, monkeypatch) -> None:
        service = mock.Mock()
        service.notifier_count = 1
        service.send.return_value = 0
        monkeypatch.setattr("knowledge.engine.cli.notify.get_notifier", mock.Mock(return_value=service))
        args = SimpleNamespace(webhook="https://x", slack="")
        assert cmd_notify_test(args) == 1
