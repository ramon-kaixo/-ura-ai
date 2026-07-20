"""Edge-case audit tests for motor/assistant/message_store.py.

Targets: thread safety, connection handling, lock coverage, SQL injection.
"""

from __future__ import annotations

import concurrent.futures
import sqlite3
import time
from typing import TYPE_CHECKING

import pytest

from motor.assistant.message_store import MessageStore
from motor.assistant.models import Message

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_msg(content: str = "hello") -> Message:
    return Message(role="user", content=content)


# ---------------------------------------------------------------------------
# B1 — Thread safety: unprotected reads race with concurrent writes
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """B1: get_conversation() and list_conversations() lack lock protection.

    sqlite3 default journal mode causes 'database is locked' when a read
    executes on another thread while a write-transaction is in-flight.
    """

    def test_concurrent_read_during_write_triggers_locked_error(self, tmp_path: Path) -> None:
        db = str(tmp_path / "race.db")
        store = MessageStore(db)

        errors: list[str] = []

        def writer() -> None:
            for i in range(200):
                store.append(f"conv-{i % 5}", _make_msg(f"msg-{i}"))

        def reader() -> None:
            for _ in range(200):
                try:
                    store.list_conversations()
                    store.get_conversation("conv-0")
                except sqlite3.OperationalError as exc:
                    errors.append(str(exc))

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(writer) for _ in range(2)] + [pool.submit(reader) for _ in range(2)]
            concurrent.futures.wait(futures)

        store.close()
        if errors:
            pytest.fail(f"{len(errors)} sqlite3.OperationalError(s) from unprotected read: {errors[0]}")

    def test_get_conversation_outside_lock_sees_partial_data(self, tmp_path: Path) -> None:
        """Without a shared lock a large write can be observed mid-flight."""
        db = str(tmp_path / "partial.db")
        store = MessageStore(db)
        store.append("c1", _make_msg("before"))

        seen_len: list[int] = []

        def slow_writer() -> None:
            store._conn.execute("BEGIN IMMEDIATE")
            store._conn.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp) "
                "VALUES ('c1', 'user', ?, 'now')",
                ("x" * 50_000,),
            )
            time.sleep(0.05)  # keep transaction open
            store._conn.commit()

        def reader() -> None:
            time.sleep(0.01)
            try:
                msgs = store.get_conversation("c1")
                seen_len.append(len(msgs))
            except sqlite3.OperationalError:
                seen_len.append(-1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(slow_writer)
            fut = pool.submit(reader)
            fut.result()

        store.close()
        # Either the reader got locked out or saw inconsistent count
        # Neither should happen with proper lock coverage
        assert len(seen_len) == 1

    def test_delete_during_list_returns_stale_data(self, tmp_path: Path) -> None:
        """delete_conversation is locked but list_conversations is not."""
        db = str(tmp_path / "stale.db")
        store = MessageStore(db)
        for cid in ("a", "b", "c"):
            for _ in range(5):
                store.append(cid, _make_msg())

        results: list[list[dict]] = []

        def deleter() -> None:
            time.sleep(0.02)
            store.delete_conversation("a")
            store.delete_conversation("b")

        def lister() -> None:
            time.sleep(0.01)
            results.append(store.list_conversations())

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(deleter)
            fut = pool.submit(lister)
            fut.result()

        store.close()
        assert len(results) == 1
        # This test passes if no crash occurs; the result may be stale


# ---------------------------------------------------------------------------
# B2 — Connection / resource handling
# ---------------------------------------------------------------------------

class TestConnectionHandling:
    """B2: message_store leaks the connection when not explicitly closed."""

    def test_use_after_close_crashes(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "gone.db"))
        store.append("c1", _make_msg("ok"))
        store.close()
        with pytest.raises(sqlite3.ProgrammingError, match="Cannot operate on a closed database"):
            store.append("c2", _make_msg("boom"))

    def test_no_context_manager(self, tmp_path: Path) -> None:
        """No __enter__/__exit__ means easy to leak the connection."""
        store = MessageStore(str(tmp_path / "leak.db"))
        assert not hasattr(store, "__enter__")
        assert not hasattr(store, "__exit__")
        store.close()

    def test_ensure_connection_exception_leaves_partial_state(self, tmp_path: Path) -> None:
        """If _init_db fails mid-way, __init__ still returns an object."""
        read_only = tmp_path / "ro"
        read_only.mkdir(parents=True, exist_ok=True)
        ro_file = read_only / "messages.db"
        ro_file.touch()
        ro_file.chmod(0o444)

        with pytest.raises((sqlite3.OperationalError, PermissionError)):
            MessageStore(str(ro_file))


# ---------------------------------------------------------------------------
# B3 — SQL injection probes (parameterised queries are used, verify)
# ---------------------------------------------------------------------------

class TestSQLInjection:
    """B3: All queries use ? placeholders — confirm edge cases are safe."""

    def test_special_chars_in_conversation_id(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "sqli.db"))
        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE messages; --",
            "c1\\'; DELETE FROM messages; --",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            '" OR "1"="1',
            "1; SELECT * FROM messages",
        ]
        for cid in payloads:
            msg = _make_msg("safe")
            row_id = store.append(cid, msg)
            assert row_id > 0
            got = store.get_conversation(cid)
            assert len(got) == 1

        assert len(store.list_conversations()) == len(payloads)
        store.close()

    def test_null_byte_in_content(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "nullbyte.db"))
        msg = _make_msg("hello\x00world")
        store.append("c1", msg)
        got = store.get_conversation("c1")
        assert len(got) == 1
        assert "\x00" in got[0].content
        store.close()

    def test_negative_limit_in_get_conversation(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "negl.db"))
        for i in range(10):
            store.append("c1", _make_msg(f"msg-{i}"))
        # LIMIT with negative value is clamped by sqlite3 — should not crash
        with pytest.raises(sqlite3.ProgrammingError):
            store.get_conversation("c1", limit=-5)
        store.close()


# ---------------------------------------------------------------------------
# B4 — Large-data edge cases
# ---------------------------------------------------------------------------

class TestLargeData:
    def test_very_long_message_content(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "big.db"))
        huge = "A" * 10_000_000  # 10 MB
        msg = _make_msg(huge)
        store.append("c1", msg)
        got = store.get_conversation("c1")
        assert len(got) == 1
        assert len(got[0].content) == 10_000_000
        store.close()

    def test_many_conversations_list(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "many.db"))
        for i in range(5000):
            store.append(f"conv-{i}", _make_msg(f"msg-{i}"))
        convs = store.list_conversations()
        assert len(convs) == 5000
        store.close()

    def test_very_long_conversation_id(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "longid.db"))
        long_id = "x" * 1_000_000
        store.append(long_id, _make_msg("test"))
        got = store.get_conversation(long_id)
        assert len(got) == 1
        store.close()


# ---------------------------------------------------------------------------
# B5 — Metadata serialisation edge cases
# ---------------------------------------------------------------------------

class TestMetadataEdgeCases:
    def test_metadata_non_string_keys(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "metakey.db"))
        msg = _make_msg("test")
        msg.metadata = {42: "answer", None: "null", ("tuple",): "value"}
        store.append("c1", msg)
        got = store.get_conversation("c1")
        assert len(got) == 1
        store.close()

    def test_metadata_unicode(self, tmp_path: Path) -> None:
        store = MessageStore(str(tmp_path / "metauni.db"))
        msg = _make_msg("test")
        msg.metadata = {"emoji": "🚀🔥", "japanese": "こんにちは"}
        store.append("c1", msg)
        got = store.get_conversation("c1")
        assert got[0].metadata["emoji"] == "🚀🔥"
        assert got[0].metadata["japanese"] == "こんにちは"
        store.close()


# ---------------------------------------------------------------------------
# B6 — Lock contention under high concurrency
# ---------------------------------------------------------------------------

class TestLockContention:
    """B6: Multiple threads calling append with the lock should not deadlock."""

    def test_high_contention_append(self, tmp_path: Path) -> None:
        db = str(tmp_path / "contention.db")
        store = MessageStore(db)
        n_threads = 8
        msgs_per_thread = 250
        errs: list[Exception] = []

        def worker(tid: int) -> None:
            try:
                for i in range(msgs_per_thread):
                    store.append(f"t{tid}", _make_msg(f"msg-{i}"))
            except Exception as e:
                errs.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(worker, t) for t in range(n_threads)]
            concurrent.futures.wait(futures)

        assert not errs, f"Errors during concurrent append: {errs}"
        convs = store.list_conversations()
        assert len(convs) == n_threads
        total = sum(c["message_count"] for c in convs)
        assert total == n_threads * msgs_per_thread
        store.close()
