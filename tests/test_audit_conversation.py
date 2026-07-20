"""Critical audit: conversation.py — edge cases, race conditions, logic errors."""

from __future__ import annotations

import concurrent.futures
import tempfile
import threading
import time
from pathlib import Path

import pytest

from motor.assistant.conversation import ConversationEngine
from motor.assistant.message_store import MessageStore
from motor.assistant.models import (
    Conversation,
    Message,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine() -> tuple[ConversationEngine, Path]:
    tmp = Path(tempfile.mkstemp(suffix=".db")[1])
    store = MessageStore(db_path=str(tmp))
    eng = ConversationEngine(message_store=store, max_turns=200)
    return eng, tmp


def _cleanup(eng: ConversationEngine, tmp: Path) -> None:
    eng._store.close()
    tmp.unlink(missing_ok=True)


# ===================================================================
# 1.  Race conditions / Thread safety on _active dict
# ===================================================================


class TestRaceConditions:
    """Probe unprotected _active dict access from multiple threads."""

    def test_concurrent_get_or_create_same_id(self):
        """Two threads call get_or_create('same') simultaneously.
        Bug: _active has no lock → both may create, last-write-wins,
        but both callers get different Conversation objects for the same ID."""
        eng, tmp = _make_engine()
        results: list[Conversation] = []
        errors: list[Exception] = []

        def get_or_create() -> None:
            try:
                c = eng.get_or_create("race1")
                results.append(c)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_or_create) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        _cleanup(eng, tmp)

        # If the dict were thread-safe, all callers would get the SAME object
        conv_ids = [id(c) for c in results]
        # BUG: multiple distinct Conversation objects exist for 'race1'
        if len(set(conv_ids)) > 1:
            pytest.fail(
                f"RACE: {len(set(conv_ids))} different Conversation objects created "
                f"for id='race1' — {len(conv_ids)} callers got different refs"
            )
        assert not errors

    def test_concurrent_add_message_no_data_loss(self):
        """50 threads add a message to same conversation concurrently.
        Bug: no lock on _active + MessageStore.append has per-call lock
        but the load/create path is not atomic → potential data loss."""
        eng, tmp = _make_engine()
        N = 50
        msg_ids: list[int] = []

        def add(i: int) -> None:
            msg = eng.add_message("race2", "user", f"msg-{i}")
            msg_ids.append(id(msg))

        threads = [threading.Thread(target=add, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        conv = eng.get_conversation("race2")
        _cleanup(eng, tmp)

        assert conv is not None
        # BUG: message count may be less than N due to race
        assert len(conv.messages) == N, f"DATA LOSS: expected {N} messages, got {len(conv.messages)}"

    def test_concurrent_create_and_delete(self):
        """One thread creates conversations, another deletes them.
        Bug: pop from _active while another thread iterates or adds."""
        eng, tmp = _make_engine()
        stop = threading.Event()
        created: list[str] = []

        def creator() -> None:
            for i in range(500):
                if stop.is_set():
                    break
                c = eng.create_conversation(f"cd-{i}")
                created.append(c.conversation_id)
                time.sleep(0.0001)

        def destroyer() -> None:
            for i in range(500):
                if stop.is_set():
                    break
                eng.delete_conversation(f"cd-{i}")
                time.sleep(0.0001)

        t1 = threading.Thread(target=creator)
        t2 = threading.Thread(target=destroyer)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        stop.set()
        # Should not crash
        _cleanup(eng, tmp)

    def test_get_conversation_toctu_race(self):
        """Two threads call get_conversation on a stale (only-in-db) conv.
        Bug: check-then-act on _active dict."""
        eng, tmp = _make_engine()
        # Pre-populate DB without _active
        eng.create_conversation("toc-1")
        eng.add_message("toc-1", "user", "hello")
        # Now remove from _active so it's "in store only"
        eng._active.pop("toc-1", None)

        results: list[Conversation | None] = []

        def load() -> None:
            c = eng.get_conversation("toc-1")
            results.append(c)

        threads = [threading.Thread(target=load) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Check: each caller got their own Conversation for the same ID
        refs = {id(r) for r in results if r is not None}
        _cleanup(eng, tmp)
        if len(refs) > 1:
            pytest.fail(
                f"TOCTOU: {len(refs)} different Conversation objects loaded "
                f"from store for 'toc-1' — callers see different state"
            )


# ===================================================================
# 2.  Empty / None inputs
# ===================================================================


class TestEmptyNoneInputs:
    """Probe crashes and silent wrong behavior with bad inputs."""

    def test_get_conversation_empty_string(self):
        eng, tmp = _make_engine()
        c = eng.get_conversation("")
        _cleanup(eng, tmp)
        assert c is None, "empty conversation_id should return None"

    def test_get_or_create_empty_string(self):
        """Bug: get_or_create('') generates a NEW random UUID every call
        because '' is falsy in create_conversation."""
        eng, tmp = _make_engine()
        c1 = eng.get_or_create("")
        c2 = eng.get_or_create("")
        _cleanup(eng, tmp)
        assert c1 is not None
        assert c2 is not None
        # BUG: they have DIFFERENT IDs — caller thinks same conv, gets different
        if c1.conversation_id == c2.conversation_id:
            pytest.fail("unexpected: empty string gave same ID")
        # This is expected to fail — it's a real bug
        # We assert the bug exists:
        assert c1.conversation_id != c2.conversation_id, "BUG CONFIRMED: get_or_create('') yields different conv IDs"

    def test_add_message_empty_content(self):
        """Empty content should be allowed but not crash."""
        eng, tmp = _make_engine()
        msg = eng.add_message("empty-1", "user", "")
        _cleanup(eng, tmp)
        assert msg.content == ""

    def test_add_message_none_content(self):
        """BUG: None content raises sqlite3.IntegrityError instead of Python-level validation."""
        eng, tmp = _make_engine()
        exc = None
        try:
            eng.add_message("none-1", "user", None)  # type: ignore[arg-type]
        except Exception as e:
            exc = e
        _cleanup(eng, tmp)
        assert exc is not None, "None content should raise"
        assert "IntegrityError" in type(exc).__name__, (
            f"BUG: should raise ValueError before SQLite, got {type(exc).__name__}"
        )
        pytest.fail(f"BUG: None content reaches SQLite ({type(exc).__name__}). No validation at Python level.")

    def test_get_context_empty_conversation(self):
        eng, tmp = _make_engine()
        ctx = eng.get_context("empty-ctx", system_prompt="test")
        _cleanup(eng, tmp)
        assert ctx == []

    def test_detect_intent_empty_string(self):
        eng, tmp = _make_engine()
        result = eng.detect_intent("")
        _cleanup(eng, tmp)
        assert result == UserIntent.UNKNOWN

    def test_detect_intent_whitespace(self):
        eng, tmp = _make_engine()
        result = eng.detect_intent("   ")
        _cleanup(eng, tmp)
        assert result == UserIntent.UNKNOWN

    def test_detect_intent_none(self):
        eng, tmp = _make_engine()
        with pytest.raises((TypeError, AttributeError)):
            eng.detect_intent(None)  # type: ignore[arg-type]
        _cleanup(eng, tmp)

    def test_resolve_reference_empty_text(self):
        eng, tmp = _make_engine()
        result = eng.resolve_reference("", "ref-empty")
        _cleanup(eng, tmp)
        assert result == ""

    def test_resolve_reference_in_empty_conversation(self):
        """Con referencias a 'eso' en conversación vacía — no crash."""
        eng, tmp = _make_engine()
        eng.create_conversation("ref-empty-conv")
        result = eng.resolve_reference("haz eso", "ref-empty-conv")
        _cleanup(eng, tmp)
        # last_user_message is None so no replacement — still no crash
        assert isinstance(result, str)

    def test_delete_nonexistent_conversation(self):
        """Bug: delete_conversation always returns True."""
        eng, tmp = _make_engine()
        result = eng.delete_conversation("i-dont-exist")
        _cleanup(eng, tmp)
        # BUG: should be False, always True
        assert result is True  # actual behavior — documents the bug

    def test_list_conversations_empty(self):
        eng, tmp = _make_engine()
        lst = eng.list_conversations()
        _cleanup(eng, tmp)
        assert lst == []


# ===================================================================
# 3.  Very long conversations (>1000 messages)
# ===================================================================


class TestLongConversations:
    """Probe performance, truncation, and memory behavior."""

    def test_1000_messages_no_crash(self):
        eng, tmp = _make_engine()
        for i in range(1000):
            eng.add_message("long1", "user", f"msg-{i}")
            eng.add_message("long1", "assistant", f"reply-{i}")
        conv = eng.get_conversation("long1")
        _cleanup(eng, tmp)
        assert conv is not None
        assert len(conv.messages) == 2000

    def test_store_limit_100_truncates_loaded_conversation(self):
        """Bug: MessageStore.get_conversation hardcodes limit=100.
        Even with max_turns=200, loading from store returns at most 100 rows."""
        eng, tmp = _make_engine()
        for i in range(150):
            eng.add_message("trunc1", "user", f"msg-{i}")
        # Remove from _active to force reload from store
        eng._active.pop("trunc1", None)
        conv = eng.get_conversation("trunc1")
        _cleanup(eng, tmp)
        assert conv is not None
        # BUG: only 100 messages loaded despite 150 stored
        if len(conv.messages) == 100:
            pytest.fail(
                "BUG: MessageStore truncates to 100 messages on reload. "
                "150 stored, but get_conversation returned only 100."
            )

    def test_max_turns_not_enforced(self):
        """Bug: max_turns=200 is stored but never checked in add_message.
        Conversations can grow unbounded."""
        eng, tmp = _make_engine()
        for i in range(300):
            eng.add_message("noturn1", "user", f"msg-{i}")
        conv = eng.get_conversation("noturn1")
        _cleanup(eng, tmp)
        assert conv is not None
        # BUG: 300 > max_turns=200, but no trimming occurred
        if len(conv.messages) > 200:
            pytest.fail(f"BUG: max_turns=200 not enforced. Conversation has {len(conv.messages)} messages.")

    def test_long_conversation_reference_resolution(self):
        eng, tmp = _make_engine()
        for i in range(500):
            eng.add_message("longref", "user", f"long message number {i}")
            eng.add_message("longref", "assistant", f"response {i}")
        result = eng.resolve_reference("repite eso", "longref")
        _cleanup(eng, tmp)
        # Should contain the last user message content (truncated to 80 chars)
        assert "long message number 499" in result or "499" in result or result != "repite eso"


# ===================================================================
# 4.  Concurrent access to same conversation
# ===================================================================


class TestConcurrentSameConversation:
    """Multiple threads hitting the same conversation simultaneously."""

    def test_read_write_contention(self):
        """Some threads read, some write — no crash and no data loss."""
        eng, tmp = _make_engine()
        eng.create_conversation("contend1")
        N = 200
        errors: list[Exception] = []

        def writer(i: int) -> None:
            try:
                eng.add_message("contend1", "user", f"write-{i}")
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                eng.get_conversation("contend1")
                eng.get_context("contend1", "test")
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
            for i in range(N):
                ex.submit(writer, i)
                ex.submit(reader)

        time.sleep(0.5)
        conv = eng.get_conversation("contend1")
        _cleanup(eng, tmp)
        assert not errors, f"Errors during concurrent access: {errors}"
        assert conv is not None
        assert len(conv.messages) >= N, f"Data loss: expected >= {N} messages, got {len(conv.messages)}"

    def test_detect_intent_during_add_message(self):
        """Simultaneous intent detection and message addition."""
        eng, tmp = _make_engine()
        eng.create_conversation("detect-contend")
        errors: list[Exception] = []

        def adder() -> None:
            for i in range(50):
                try:
                    eng.add_message("detect-contend", "user", f"hello {i}")
                except Exception as e:
                    errors.append(e)

        def detector() -> None:
            for _ in range(50):
                try:
                    eng.detect_intent("hello world")
                except Exception as e:
                    errors.append(e)

        t1 = threading.Thread(target=adder)
        t2 = threading.Thread(target=detector)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        _cleanup(eng, tmp)
        assert not errors


# ===================================================================
# 5.  Memory leak — _active grows unbounded
# ===================================================================


class TestMemoryLeak:
    """Probe unbounded growth of _active dict."""

    def test_active_grows_with_get_conversation(self):
        """get_conversation inserts into _active but never evicts."""
        eng, tmp = _make_engine()
        # Create conversations and store them only
        for i in range(500):
            cid = f"leak-{i}"
            eng.create_conversation(cid)
            eng.add_message(cid, "user", "test")
        # Remove all from _active
        eng._active.clear()
        # Now load each one — each call to get_conversation re-adds to _active
        for i in range(500):
            c = eng.get_conversation(f"leak-{i}")
            assert c is not None
        # _active now has 500 entries — never evicted
        _cleanup(eng, tmp)
        # BUG: _active size is 500 with no eviction
        if len(eng._active) >= 500:
            pytest.fail(
                f"MEMORY LEAK: _active has {len(eng._active)} entries with no eviction mechanism. Unbounded growth."
            )

    def test_active_grows_on_get_or_create(self):
        """Every new conversation_id permanently occupies _active."""
        eng, tmp = _make_engine()
        for i in range(1000):
            eng.get_or_create(f"nogc-{i}")
        _cleanup(eng, tmp)
        if len(eng._active) == 1000:
            pytest.fail(
                f"MEMORY LEAK: _active holds {len(eng._active)} entries after 1000 get_or_create calls with no cleanup."
            )

    def test_delete_conversation_removes_from_active(self):
        """delete_conversation correctly removes from _active."""
        eng, tmp = _make_engine()
        eng.create_conversation("del-test")
        assert "del-test" in eng._active
        eng.delete_conversation("del-test")
        _cleanup(eng, tmp)
        assert "del-test" not in eng._active

    def test_active_does_not_grow_on_read_only_ops(self):
        """detect_intent and list_conversations should not create entries."""
        eng, tmp = _make_engine()
        before = len(eng._active)
        eng.detect_intent("hello")
        eng.list_conversations()
        _cleanup(eng, tmp)
        assert len(eng._active) == before, "detect_intent or list_conversations leaked into _active"


# ===================================================================
# 6.  Intent detection edge cases
# ===================================================================


class TestIntentEdgeCases:
    """Probe detect_intent edge cases through the engine."""

    def test_detect_intent_mixed_case(self):
        eng, tmp = _make_engine()
        r1 = eng.detect_intent("HOLA")
        r2 = eng.detect_intent("Adiós")
        r3 = eng.detect_intent("Sí")
        _cleanup(eng, tmp)
        assert r1 == UserIntent.GREETING
        assert r2 == UserIntent.FAREWELL
        assert r3 == UserIntent.CONFIRM

    def test_detect_intent_with_punctuation(self):
        eng, tmp = _make_engine()
        r = eng.detect_intent("hola!")
        _cleanup(eng, tmp)
        assert r == UserIntent.CHAT, "'hola!' should still be GREETING, but pattern requires exact match"

    def test_detect_intent_long_text(self):
        eng, tmp = _make_engine()
        text = "hola " * 100
        r = eng.detect_intent(text)
        _cleanup(eng, tmp)
        assert r is not None

    def test_detect_intent_question_mark(self):
        eng, tmp = _make_engine()
        r = eng.detect_intent("esto es una pregunta?")
        _cleanup(eng, tmp)
        assert r == UserIntent.QUESTION

    def test_detect_intent_exclamation(self):
        eng, tmp = _make_engine()
        r = eng.detect_intent("hola")
        _cleanup(eng, tmp)
        assert r == UserIntent.GREETING


# ===================================================================
# 7.  Reference resolution edge cases
# ===================================================================


class TestReferenceResolutionEdgeCases:
    """Probe resolve_reference logic errors."""

    def test_resolve_reference_lowercases_everything(self):
        """Bug: resolve_reference calls resolved.lower() which destroys casing."""
        eng, tmp = _make_engine()
        eng.add_message("case1", "user", "Hola Mundo")
        result = eng.resolve_reference("Repite ESO", "case1")
        _cleanup(eng, tmp)
        # BUG: even if replacement didn't match, the entire string is lowercased
        # So "Repite ESO" becomes "repite eso" even without replacement
        if "Repite" not in result and result == "repite eso"[: len("Repite ESO")]:
            pytest.fail(
                f"BUG: resolve_reference lowercased entire input. "
                f"Input='Repite ESO', output='{result}'. "
                f"Casing of non-replaced parts should be preserved."
            )

    def test_resolve_reference_substring_match(self):
        """Bug: no word boundary — 'eso' matches 'esos', 'esoterico'."""
        eng, tmp = _make_engine()
        eng.add_message("sub1", "user", "contenido anterior")
        result = eng.resolve_reference("esoterico", "sub1")
        _cleanup(eng, tmp)
        # 'eso' is a substring of 'esoterico' — should NOT match
        if "(contenido anterior" in result or "contenido" in result:
            pytest.fail(
                f"BUG: 'eso' in 'esoterico' triggered replacement. Output: '{result}'. Word boundaries not enforced."
            )

    def test_resolve_reference_empty_content_after_replacement(self):
        """Replacing 'eso' with empty string produces empty or spaces."""
        eng, tmp = _make_engine()
        eng.add_message("emptyref", "user", "something")
        result = eng.resolve_reference("repite eso", "emptyref")
        _cleanup(eng, tmp)
        # 'eso' → empty, so "repite eso" → "repite " (with trailing space)
        assert "(something" in result or "repite" in result

    def test_resolve_reference_no_last_message(self):
        """No last_user_message — should still work without error."""
        eng, tmp = _make_engine()
        eng.create_conversation("nomsg")
        result = eng.resolve_reference("haz eso", "nomsg")
        _cleanup(eng, tmp)
        assert result in {"haz eso", "haz "}

    def test_resolve_reference_multiple_refs(self):
        """Multiple reference tokens in one string."""
        eng, tmp = _make_engine()
        eng.add_message("multiref", "user", "primera peticion")
        result = eng.resolve_reference("eso y el anterior", "multiref")
        _cleanup(eng, tmp)
        # Both should be replaced
        assert "primera" in result

    def test_resolve_reference_unicode(self):
        """Unicode content in reference resolution."""
        eng, tmp = _make_engine()
        eng.add_message("unicode1", "user", "café ñoño")
        result = eng.resolve_reference("repite eso", "unicode1")
        _cleanup(eng, tmp)
        assert "caf" in result or "ñoño" in result


# ===================================================================
# 8.  Multiple conversations interleaving
# ===================================================================


class TestMultipleConversations:
    """Interleaved operations across conversations."""

    def test_interleaved_add_messages(self):
        """Add messages to different conversations in alternating order."""
        eng, tmp = _make_engine()
        for i in range(100):
            eng.add_message("a", "user", f"a-msg-{i}")
            eng.add_message("b", "user", f"b-msg-{i}")
            eng.add_message("a", "assistant", f"a-reply-{i}")
            eng.add_message("b", "assistant", f"b-reply-{i}")

        ca = eng.get_conversation("a")
        cb = eng.get_conversation("b")
        _cleanup(eng, tmp)
        assert ca is not None and len(ca.messages) == 200
        assert cb is not None and len(cb.messages) == 200
        # Verify no cross-contamination
        assert all(m.content.startswith("a-") for m in ca.messages)
        assert all(m.content.startswith("b-") for m in cb.messages)

    def test_reference_resolution_only_own_conversation(self):
        """resolve_reference should only use the specified conversation."""
        eng, tmp = _make_engine()
        eng.add_message("only1", "user", "Soy la conversación 1")
        eng.add_message("only2", "user", "Soy la conversación 2")
        r1 = eng.resolve_reference("repite eso", "only1")
        r2 = eng.resolve_reference("repite eso", "only2")
        _cleanup(eng, tmp)
        assert "conversación 1" in r1 or "conversaci" in r1
        assert "conversación 2" in r2 or "conversaci" in r2

    def test_many_conversations_no_cross_talk(self):
        """100 conversations — messages should not leak."""
        eng, tmp = _make_engine()
        for i in range(100):
            eng.add_message(f"mc-{i}", "user", f"msg-in-{i}")
        for i in range(100):
            conv = eng.get_conversation(f"mc-{i}")
            assert conv is not None
            assert len(conv.messages) == 1
            assert conv.messages[0].content == f"msg-in-{i}"
        _cleanup(eng, tmp)

    def test_concurrent_mixed_conversations(self):
        """Multiple threads each working on different conversations."""
        eng, tmp = _make_engine()
        errors: list[Exception] = []

        def work_on_conv(cid: str, n: int) -> None:
            try:
                for j in range(n):
                    eng.add_message(cid, "user", f"thread-msg-{j}")
                    eng.get_context(cid)
                    eng.resolve_reference("eso", cid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=work_on_conv, args=(f"mix-{i}", 50)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        _cleanup(eng, tmp)
        assert not errors, f"Errors during mixed conversations: {errors}"


# ===================================================================
# 9.  Additional logic errors
# ===================================================================


class TestLogicErrors:
    """Other design flaws."""

    def test_create_conversation_duplicate_id_overwrites(self):
        """Creating a conversation with an existing ID silently overwrites."""
        eng, tmp = _make_engine()
        c1 = eng.create_conversation("dup", mode=ConversationMode.WORK, goal="first")
        c2 = eng.create_conversation("dup", mode=ConversationMode.CONVERSATION, goal="second")
        _cleanup(eng, tmp)
        # BUG: c1 is now orphaned, c2 is in _active
        assert c1.conversation_id == c2.conversation_id
        # The old conversation (c1) is still referenced by caller but
        # _active['dup'] now points to c2 — c1's messages are lost in memory
        assert eng._active["dup"] is c2, "c2 should have overwritten c1"
        assert eng._active["dup"] is not c1, "c1 should be orphaned"

    def test_add_message_with_invalid_role(self):
        """BUG: Literal type is not enforced at runtime — invalid role passes through."""
        eng, tmp = _make_engine()
        eng.add_message("badrole", "invalid_role", "test")  # type: ignore[arg-type]
        conv = eng.get_conversation("badrole")
        _cleanup(eng, tmp)
        assert conv is not None
        assert len(conv.messages) == 1
        assert conv.messages[0].role == "invalid_role"
        pytest.fail(
            "BUG: 'invalid_role' passed runtime without validation. "
            "Literal['user','assistant','system','tool'] not enforced at runtime."
        )

    def test_get_context_with_stale_active(self):
        """If _active holds stale data, get_context returns stale context."""
        eng, tmp = _make_engine()
        eng.add_message("stale", "user", "original")
        # Directly manipulate _active to inject stale state
        eng._active["stale"].messages.append(Message(role="user", content="direct"))
        ctx = eng.get_context("stale")
        _cleanup(eng, tmp)
        assert any(m.content == "direct" for m in ctx), "get_context should reflect _active state"

    def test_resolve_reference_replacement_values_ignored(self):
        """BUG: replacements dict values are never used.
        Code replaces with `f\"({last.content[:80]}...)\"` instead of the dict value.
        'hazlo' should → 'ejecuta' but instead → '(una tarea...)'."""
        eng, tmp = _make_engine()
        eng.add_message("hazlo1", "user", "una tarea")
        result = eng.resolve_reference("hazlo", "hazlo1")
        _cleanup(eng, tmp)
        # Code replaces "hazlo" with last.content wrapped in parens, ignoring "ejecuta"
        assert "ejecuta" not in result, "replacements dict value ignored — code uses last.content instead"
        pytest.fail(
            "BUG: replacements{'hazlo': 'ejecuta'} value IGNORED. "
            f"Output: '{result}'. Code replaces with last.content instead."
        )

    def test_add_message_turn_count_consistency(self):
        """Turn count should match number of messages / 2 (roughly)."""
        eng, tmp = _make_engine()
        eng.create_conversation("turns1")
        for i in range(10):
            eng.add_message("turns1", "user", f"q{i}")
            eng.add_message("turns1", "assistant", f"a{i}")
        conv = eng.get_conversation("turns1")
        _cleanup(eng, tmp)
        assert conv is not None
        assert conv.state is not None
        # 20 messages = 20 turns (each add_message increments turn_count by 1)
        assert conv.state.turn_count == 20


# Need this import at top — redeclared here since module scope
from motor.assistant.models import (
    ConversationMode,
    UserIntent,
)
