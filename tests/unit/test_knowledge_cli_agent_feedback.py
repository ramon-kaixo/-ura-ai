"""Tests para knowledge/engine/cli/ — agent y feedback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from knowledge.engine.cli.agent import cmd_agent_list, cmd_agent_run
from knowledge.engine.cli.feedback import cmd_feedback_rate, cmd_feedback_top


class TestCmdAgentList:
    def test_sin_agentes(self, monkeypatch) -> None:
        monkeypatch.setattr("knowledge.engine.agent.list_agents", mock.Mock(return_value=[]))
        assert cmd_agent_list(SimpleNamespace()) == 0

    def test_con_agentes(self, monkeypatch) -> None:
        monkeypatch.setattr("knowledge.engine.agent.list_agents", mock.Mock(return_value=[mock.Mock(), mock.Mock()]))
        assert cmd_agent_list(SimpleNamespace()) == 0


class TestCmdAgentRun:
    def test_agente_no_existe(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("knowledge.engine.agent.get_agent", mock.Mock(return_value=None))
        args = SimpleNamespace(agent_id="nope", db_path=str(tmp_path / "db.sqlite"))
        assert cmd_agent_run(args) == 1  # sin kind -> default audit

    def test_ok_con_findings(self, monkeypatch, tmp_path) -> None:
        agent = mock.Mock()
        finding = mock.Mock()
        finding.severity = "ERROR"
        agent.execute.return_value = [finding, finding]
        monkeypatch.setattr("knowledge.engine.agent.get_agent", mock.Mock(return_value=agent))
        args = SimpleNamespace(agent_id="a1", db_path=str(tmp_path / "db.sqlite"), kind="audit")
        assert cmd_agent_run(args) == 0
        agent.execute.assert_called_once()
        goal = agent.execute.call_args.args[0]
        assert goal.kind == "audit"

    def test_ok_sin_findings(self, monkeypatch, tmp_path) -> None:
        agent = mock.Mock()
        agent.execute.return_value = []
        monkeypatch.setattr("knowledge.engine.agent.get_agent", mock.Mock(return_value=agent))
        args = SimpleNamespace(agent_id="a1", db_path=str(tmp_path / "db.sqlite"), kind="audit")
        assert cmd_agent_run(args) == 0

    def test_sin_kind_default_audit(self, monkeypatch, tmp_path) -> None:
        agent = mock.Mock()
        agent.execute.return_value = []
        monkeypatch.setattr("knowledge.engine.agent.get_agent", mock.Mock(return_value=agent))
        args = SimpleNamespace(agent_id="a1", db_path=str(tmp_path / "db.sqlite"))
        cmd_agent_run(args)
        assert agent.execute.call_args.args[0].kind == "audit"


class TestCmdFeedbackRate:
    def test_rating_invalido(self, monkeypatch, tmp_path) -> None:
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), doc_id="d1", rating=6)
        assert cmd_feedback_rate(args) == 1
        args2 = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), doc_id="d1", rating=0)
        assert cmd_feedback_rate(args2) == 1

    def test_ok(self, monkeypatch, tmp_path) -> None:
        record = mock.Mock(return_value=True)
        monkeypatch.setattr("knowledge.engine.feedback.record_feedback", record)
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), doc_id="d1", rating=4)
        assert cmd_feedback_rate(args) == 0
        record.assert_called_once_with(tmp_path / "db.sqlite", "d1", 4)

    def test_falla(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("knowledge.engine.feedback.record_feedback", mock.Mock(return_value=False))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), doc_id="d1", rating=3)
        assert cmd_feedback_rate(args) == 1


class TestCmdFeedbackTop:
    def test_sin_resultados(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("knowledge.engine.feedback.top_rated", mock.Mock(return_value=[]))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), limit=5)
        assert cmd_feedback_top(args) == 0

    def test_con_resultados(self, monkeypatch, tmp_path) -> None:
        fb = mock.Mock()
        fb.rating = 4
        monkeypatch.setattr("knowledge.engine.feedback.top_rated", mock.Mock(return_value=[fb, fb]))
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"), limit=10)
        assert cmd_feedback_top(args) == 0

    def test_limit_default(self, monkeypatch, tmp_path) -> None:
        top = mock.Mock(return_value=[])
        monkeypatch.setattr("knowledge.engine.feedback.top_rated", top)
        args = SimpleNamespace(db_path=str(tmp_path / "db.sqlite"))
        cmd_feedback_top(args)
        assert top.call_args.kwargs["limit"] == 10
