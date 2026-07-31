"""Unit tests para change_log.py — unified change log SQLite."""

from __future__ import annotations

import json

import pytest

import scripts.pro.change_log as cl


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cl, "DB_PATH", tmp_path / "changes.db")
    monkeypatch.setattr(cl, "_ACTOR_FILE", tmp_path / "change_actor.txt")


class TestSchema:
    def test_table_created_on_first_use(self) -> None:
        conn = cl._connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        assert ("changes",) in tables

    def test_columns(self) -> None:
        conn = cl._connect()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(changes)")}
        conn.close()
        assert {
            "id",
            "commit_hash",
            "ts",
            "actor",
            "rationale",
            "tests_passed",
            "docs_modified",
            "adr_ref",
            "files",
        } <= cols


class TestRecord:
    def test_record_inserts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            cl,
            "_commit_info",
            lambda h: {"subject": "fix(cli): bug corregido", "body": "detalle", "files": ["motor/cli.py"]},
        )
        assert cl.record("abc1234") is True

    def test_record_deduplicates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            cl,
            "_commit_info",
            lambda h: {"subject": "fix: algo", "body": "", "files": []},
        )
        assert cl.record("abc1234") is True
        assert cl.record("abc1234") is False
        assert len(cl.query(limit=10)) == 1

    def test_record_empty_subject_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cl, "_commit_info", lambda h: {"subject": "", "body": "", "files": []})
        assert cl.record("abc1234") is False

    def test_record_detects_tests_and_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            cl,
            "_commit_info",
            lambda h: {
                "subject": "test(qdrant): día 1",
                "body": "",
                "files": ["tests/unit/test_qdrant.py", "docs/architecture/ADR-1.md"],
            },
        )
        cl.record("abc1234")
        entry = cl.query(limit=1)[0]
        assert entry["tests_passed"] == 1
        assert entry["docs_modified"] == 1

    def test_record_detects_adr_in_subject(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            cl,
            "_commit_info",
            lambda h: {"subject": "fix: algo (ADR-042)", "body": "", "files": []},
        )
        cl.record("abc1234")
        assert cl.query(limit=1)[0]["adr_ref"] == "42"

    def test_record_actor_default_human(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            cl,
            "_commit_info",
            lambda h: {"subject": "fix: algo", "body": "", "files": []},
        )
        cl.record("abc1234")
        assert cl.query(limit=1)[0]["actor"] == "human"

    def test_record_actor_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            cl,
            "_commit_info",
            lambda h: {"subject": "fix: algo", "body": "", "files": []},
        )
        cl.record("abc1234", actor="ia")
        assert cl.query(limit=1)[0]["actor"] == "ia"

    def test_files_serialized_as_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            cl,
            "_commit_info",
            lambda h: {"subject": "fix: algo", "body": "", "files": ["a.py", "b.py"]},
        )
        cl.record("abc1234")
        entry = cl.query(limit=1)[0]
        assert json.loads(entry["files"]) == ["a.py", "b.py"]


class TestActor:
    def test_default_human(self) -> None:
        assert cl.get_actor() == "human"

    def test_set_and_get(self) -> None:
        cl.set_actor("ia")
        assert cl.get_actor() == "ia"


class TestQuery:
    def test_query_orders_by_ts_desc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_info(h: str) -> dict:
            return {"subject": f"fix: cambio {h}", "body": "", "files": []}

        monkeypatch.setattr(cl, "_commit_info", fake_info)
        cl.record("commit1")
        cl.record("commit2")
        entries = cl.query(limit=10)
        assert entries[0]["commit_hash"] == "commit2"
        assert entries[1]["commit_hash"] == "commit1"

    def test_query_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            cl,
            "_commit_info",
            lambda h: {"subject": f"fix: cambio {h}", "body": "", "files": []},
        )
        for i in range(5):
            cl.record(f"c{i}")
        assert len(cl.query(limit=2)) == 2

    def test_query_empty(self) -> None:
        assert cl.query() == []
