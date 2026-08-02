"""Tests para MessageStore (SQLite temp, sin mocks internos).
Cada test documenta qué bug detectaría al cambiar message_store.py.
"""
from __future__ import annotations

import concurrent.futures
import contextlib
from pathlib import Path

import pytest

from motor.assistant.message_store import MessageStore
from motor.assistant.models import Message

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_conversations.db")


@pytest.fixture
def store(db_path: str) -> MessageStore:
    s = MessageStore(db_path=db_path)
    yield s
    with contextlib.suppress(Exception):
        s.close()


# ---------------------------------------------------------------------------
# Creación de la DB
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_sqlite_file(self, db_path: str) -> None:
        """Bug: si _init_db() no se llama en __init__, el archivo .db nunca se crea."""
        assert not Path(db_path).exists()
        MessageStore(db_path=db_path).close()
        assert Path(db_path).exists()

    def test_creates_messages_table(self, db_path: str) -> None:
        """Bug: si CREATE TABLE falta o tiene schema incorrecto, append falla."""
        store = MessageStore(db_path=db_path)
        store.append("x", Message(role="user", content="ok"))
        store.close()


# ---------------------------------------------------------------------------
# Append + GetConversation
# ---------------------------------------------------------------------------

class TestAppendAndGet:
    def test_roundtrip_single_message(self, store: MessageStore) -> None:
        """Bug: si append no escribe en SQLite o get_conversation no lee, el
        roundtrip devuelve 0 mensajes o contenido distinto."""
        store.append("r1", Message(role="user", content="hola"))
        msgs = store.get_conversation("r1")
        assert len(msgs) == 1
        assert msgs[0].role == "user"
        assert msgs[0].content == "hola"

    def test_multiple_conversations_isolated(self, store: MessageStore) -> None:
        """Bug: si la query WHERE conversation_id falta, mensajes de diferentes
        conversaciones se mezclan."""
        store.append("a", Message(role="user", content="msg-a"))
        store.append("b", Message(role="user", content="msg-b"))
        assert len(store.get_conversation("a")) == 1
        assert len(store.get_conversation("b")) == 1
        assert store.get_conversation("a")[0].content == "msg-a"

    def test_nonexistent_returns_empty_list(self, store: MessageStore) -> None:
        """Bug: si no se maneja conversation_id inexistente, puede retornar None
        o lanzar excepción en vez de lista vacía."""
        assert store.get_conversation("no-such") == []

    def test_limit_filters_messages(self, store: MessageStore) -> None:
        """Bug: si la cláusula LIMIT de SQL falta, get_conversation devuelve todos
        los mensajes ignorando el parámetro."""
        for i in range(10):
            store.append("lim", Message(role="user", content=f"msg-{i}"))
        msgs = store.get_conversation("lim", limit=3)
        assert len(msgs) == 3

    def test_limit_less_than_one_returns_empty(self, store: MessageStore) -> None:
        """Bug: si limit=0 o limit negativo, get_conversation debe retornar []
        (línea `if limit < 1: return []`)."""
        store.append("lim0", Message(role="user", content="x"))
        assert store.get_conversation("lim0", limit=0) == []
        assert store.get_conversation("lim0", limit=-1) == []

    def test_preserves_insertion_order(self, store: MessageStore) -> None:
        """Bug: si la query SQL pierde ORDER BY id ASC, los mensajes pueden
        devolverse en orden arbitrario (depende del plan de SQLite)."""
        msgs = [Message(role="user", content=f"pos-{i}") for i in range(10)]
        for m in msgs:
            store.append("order", m)
        retrieved = store.get_conversation("order")
        assert [m.content for m in retrieved] == [f"pos-{i}" for i in range(10)]

    def test_empty_content_string(self, store: MessageStore) -> None:
        """Bug: si content = '' causa un error en JSON serialization o SQL, el
        append lanza excepción. Debe permitir strings vacíos."""
        store.append("empty", Message(role="user", content=""))
        msgs = store.get_conversation("empty")
        assert msgs[0].content == ""

    def test_very_long_content(self, store: MessageStore) -> None:
        """Bug: si content > 1 MB causa buffer overflow o truncation silencioso
        en SQLite. SQLite soporta hasta ~2 GB, debe funcionar."""
        largo = "x" * 1_000_000
        store.append("long", Message(role="user", content=largo))
        msgs = store.get_conversation("long")
        assert len(msgs[0].content) == 1_000_000

    def test_tool_message_with_all_optional_fields(self, store: MessageStore) -> None:
        """Bug: si tool_call_id, tool_name o metadata no se serializan/deserializan
        correctamente como JSON, se pierden al recuperar."""
        msg = Message(
            role="assistant",
            content="resultado",
            tool_call_id="call-abc",
            tool_name="calculator",
            metadata={"expr": "2+2", "precision": 0.001},
        )
        store.append("tool1", msg)
        msgs = store.get_conversation("tool1")
        assert msgs[0].tool_call_id == "call-abc"
        assert msgs[0].tool_name == "calculator"
        assert msgs[0].metadata == {"expr": "2+2", "precision": 0.001}

    def test_role_tool_requires_tool_call_id(self) -> None:
        """Bug: si la validación de Message falla, tool sin tool_call_id se
        guarda silenciosamente."""
        with pytest.raises(ValueError, match="tool_call_id"):
            Message(role="tool", content="result")


# ---------------------------------------------------------------------------
# ListConversations
# ---------------------------------------------------------------------------

class TestListConversations:
    def test_empty_when_no_data(self, store: MessageStore) -> None:
        assert store.list_conversations() == []

    def test_returns_all_conversations(self, store: MessageStore) -> None:
        store.append("l1", Message(role="user", content="first"))
        store.append("l2", Message(role="user", content="second"))
        lst = store.list_conversations()
        ids = {c["id"] for c in lst}
        assert ids == {"l1", "l2"}

    def test_includes_message_count(self, store: MessageStore) -> None:
        store.append("cnt", Message(role="user", content="m1"))
        store.append("cnt", Message(role="user", content="m2"))
        entry = next(c for c in store.list_conversations() if c["id"] == "cnt")
        assert entry["message_count"] >= 2


# ---------------------------------------------------------------------------
# DeleteConversation
# ---------------------------------------------------------------------------

class TestDeleteConversation:
    def test_returns_true_and_removes(self, store: MessageStore) -> None:
        """Bug: si DELETE FROM messages no filtra por conversation_id, borra
        todas las conversaciones."""
        store.append("del1", Message(role="user", content="x"))
        assert store.delete_conversation("del1") is True
        assert store.get_conversation("del1") == []

    def test_returns_false_for_nonexistent(self, store: MessageStore) -> None:
        assert store.delete_conversation("no-such") is False

    def test_does_not_affect_other_conversations(self, store: MessageStore) -> None:
        """Bug: si el DELETE no tiene WHERE, borra todas las filas en lugar de
        solo la conversación solicitada."""
        store.append("keep", Message(role="user", content="keep me"))
        store.append("gone", Message(role="user", content="delete me"))
        store.delete_conversation("gone")
        assert len(store.get_conversation("keep")) == 1
        assert store.get_conversation("gone") == []


# ---------------------------------------------------------------------------
# CleanupOld
# ---------------------------------------------------------------------------

class TestCleanupOld:
    def test_removes_messages_before_threshold(self, store: MessageStore) -> None:
        """Bug: si la query datetime('now') no resta días correctamente, los
        mensajes antiguos no se limpian.
        Usamos timestamp explícito antiguo en el constructor de Message."""
        store.append("old", Message(role="user", content="viejos", timestamp="2020-01-01"))
        store.append("new", Message(role="user", content="recientes"))
        deleted = store.cleanup_old(days=0)
        assert deleted >= 1
        assert store.get_conversation("old") == []
        assert len(store.get_conversation("new")) > 0

    def test_removes_multiple_conversations(self, store: MessageStore) -> None:
        """Bug: cleanup cuenta solo 1 fila por conversación en vez de todas."""
        for i in range(5):
            store.append(f"batch-{i}", Message(role="user", content="x", timestamp="2020-06-01"))
        deleted = store.cleanup_old(days=0)
        assert deleted >= 5

    def test_no_removal_with_future_timestamp(self, store: MessageStore) -> None:
        """Bug: cleanup no debe borrar mensajes con timestamp futuro."""
        store.append("future", Message(role="user", content="futuro", timestamp="2099-12-31"))
        deleted = store.cleanup_old(days=0)
        assert deleted == 0
        assert len(store.get_conversation("future")) == 1

    def test_cleanup_future_days_does_not_remove_recent(self, store: MessageStore) -> None:
        """Bug: si days=30, mensajes de hoy no deben borrarse."""
        store.append("recent", Message(role="user", content="hoy"))
        deleted = store.cleanup_old(days=30)
        assert deleted == 0
        assert len(store.get_conversation("recent")) == 1


# ---------------------------------------------------------------------------
# Close / Context Manager
# ---------------------------------------------------------------------------

class TestClose:
    def test_raises_on_append_after_close(self, store: MessageStore) -> None:
        """Bug: si _closed no se verifica en append, se escribe en conexión
        cerrada y lanza sqlite3.ProgrammingError genérico."""
        store.close()
        with pytest.raises(RuntimeError, match="closed"):
            store.append("x", Message(role="user", content="fail"))

    def test_raises_on_get_after_close(self, store: MessageStore) -> None:
        store.close()
        with pytest.raises(RuntimeError, match="closed"):
            store.get_conversation("x")

    def test_raises_on_delete_after_close(self, store: MessageStore) -> None:
        store.close()
        with pytest.raises(RuntimeError, match="closed"):
            store.delete_conversation("x")

    def test_raises_on_list_after_close(self, store: MessageStore) -> None:
        store.close()
        with pytest.raises(RuntimeError, match="closed"):
            store.list_conversations()

    def test_context_manager_closes_automatically(self, tmp_path: Path) -> None:
        """Bug: si __exit__ no llama a close, la conexión SQLite queda abierta."""
        db = str(tmp_path / "ctx.db")
        with MessageStore(db_path=db) as s:
            s.append("ctx", Message(role="user", content="ok"))
        with pytest.raises(RuntimeError, match="closed"):
            s.append("ctx2", Message(role="user", content="fail"))


# ---------------------------------------------------------------------------
# Concurrencia (Race Condition)
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_appends(self, db_path: str) -> None:
        """Bug: si threading.Lock no protege append, dos hilos escribiendo
        simultáneamente pueden perder mensajes o corromper la DB.
        Probabilístico: puede pasar aunque falle el lock, pero si el lock
        funciona siempre pasa."""
        store = MessageStore(db_path=db_path)
        N = 50

        def writer(start: int) -> None:
            for i in range(start, start + N):
                store.append("conc", Message(role="user", content=f"msg-{i}"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(writer, 0)
            f2 = ex.submit(writer, N)
            concurrent.futures.wait([f1, f2])

        msgs = store.get_conversation("conc")
        {m.content for m in msgs}
        assert len(msgs) == 2 * N, (
            f"Esperados {2*N} mensajes, obtenidos {len(msgs)}. "
            "Posible race condition en append."
        )
        store.close()
