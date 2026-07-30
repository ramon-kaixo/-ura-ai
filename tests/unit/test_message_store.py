"""Tests para MessageStore (SQLite en temp dir, sin mocks)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from motor.assistant.message_store import MessageStore
from motor.assistant.models import Message


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_conversations.db")


@pytest.fixture
def store(db_path: str) -> MessageStore:
    s = MessageStore(db_path=db_path)
    yield s
    try:
        s.close()
    except Exception:
        pass


def test_init_creates_db(db_path: str) -> None:
    assert not Path(db_path).exists()
    MessageStore(db_path=db_path).close()
    assert Path(db_path).exists()


def test_append_and_get_conversation(store: MessageStore) -> None:
    msg = Message(role="user", content="hola")
    store.append("conv-1", msg)
    msgs = store.get_conversation("conv-1")
    assert len(msgs) == 1
    assert msgs[0].role == "user"
    assert msgs[0].content == "hola"


def test_get_conversation_empty(store: MessageStore) -> None:
    assert store.get_conversation("nonexistent") == []


def test_get_conversation_limit(store: MessageStore) -> None:
    for i in range(10):
        store.append("conv-1", Message(role="user", content=f"msg-{i}"))
    msgs = store.get_conversation("conv-1", limit=3)
    assert len(msgs) == 3


def test_append_multiple_conversations(store: MessageStore) -> None:
    store.append("a", Message(role="user", content="msg-a"))
    store.append("b", Message(role="user", content="msg-b"))
    assert len(store.get_conversation("a")) == 1
    assert len(store.get_conversation("b")) == 1


def test_list_conversations(store: MessageStore) -> None:
    assert store.list_conversations() == []
    store.append("c1", Message(role="user", content="first"))
    time.sleep(0.01)
    store.append("c2", Message(role="user", content="second"))
    lst = store.list_conversations()
    assert len(lst) == 2
    ids = [c["id"] for c in lst]
    assert "c1" in ids
    assert "c2" in ids


def test_delete_conversation(store: MessageStore) -> None:
    store.append("d1", Message(role="user", content="x"))
    assert store.delete_conversation("d1") is True
    assert store.get_conversation("d1") == []


def test_delete_nonexistent(store: MessageStore) -> None:
    assert store.delete_conversation("no-such") is False


def test_cleanup_old(store: MessageStore) -> None:
    store.append("old", Message(role="user", content="old msg"))
    assert len(store.get_conversation("old")) == 1
    store._conn.execute("UPDATE messages SET timestamp = '2020-01-01' WHERE conversation_id = 'old'")
    store._conn.commit()
    deleted = store.cleanup_old(days=0)
    assert deleted >= 1
    assert store.get_conversation("old") == []


def test_close_raises_on_operation(store: MessageStore) -> None:
    store.close()
    with pytest.raises(RuntimeError, match="closed"):
        store.append("x", Message(role="user", content="fail"))


def test_context_manager(tmp_path: Path) -> None:
    db = str(tmp_path / "ctx.db")
    with MessageStore(db_path=db) as s:
        s.append("ctx", Message(role="user", content="ok"))
        assert len(s.get_conversation("ctx")) == 1


def test_message_with_tool_and_metadata(store: MessageStore) -> None:
    msg = Message(
        role="assistant",
        content="tool result",
        tool_call_id="call-1",
        tool_name="calculator",
        metadata={"expr": "2+2"},
    )
    store.append("t1", msg)
    msgs = store.get_conversation("t1")
    assert len(msgs) == 1
    assert msgs[0].tool_call_id == "call-1"
    assert msgs[0].tool_name == "calculator"
    assert msgs[0].metadata == {"expr": "2+2"}
