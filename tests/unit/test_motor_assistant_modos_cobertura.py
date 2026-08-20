"""Cobertura 100x100 de motor/assistant (5 modulos). TASK-20260820-012."""

from __future__ import annotations

import asyncio

import pytest

from motor.assistant.auto_mode import AutoModeDetector
from motor.assistant.corrective_learning import CorrectiveMemory
from motor.assistant.episodic_memory import EpisodicConversationMemory, TopicExtractor
from motor.assistant.interruption import InterruptionContext, InterruptionSystem
from motor.assistant.models import ConversationMode, Message, UserIntent
from motor.assistant.streaming import StreamEvent, StreamManager

# ── streaming ────────────────────────────────────────────────


def test_stream_event_sin_datos() -> None:
    e = StreamEvent("ping")
    assert e.to_sse() == "data: \n\n"


def test_stream_event_con_datos() -> None:
    e = StreamEvent("token", "hola")
    assert e.to_sse() == 'data: {"type": "token", "data": "hola"}\n\n'


def test_stream_manager_start_stop() -> None:
    m = StreamManager()
    m.start_stream("s1")
    assert m.is_active("s1") is True
    m.stop_stream("s1")
    assert m.is_active("s1") is False
    m.stop_stream("no-existe")  # no lanza


def test_stream_response_simple() -> None:
    async def _gen():
        yield "hola"
        yield " mundo"

    async def _main() -> list[str]:
        m = StreamManager()
        events = []
        async for ev in m.stream_response("s1", _gen()):
            events.append(ev)
        return events

    events = asyncio.run(_main())
    assert any("token" in e for e in events)
    assert any('"done"' in e for e in events)
    assert any("hola" in e for e in events)


def test_stream_response_con_tool_calls() -> None:
    async def _gen():
        yield "respuesta"

    async def _main() -> list[str]:
        m = StreamManager()
        events = []
        async for ev in m.stream_response("s1", _gen(), tool_calls=[{"name": "calc"}]):
            events.append(ev)
        return events

    events = asyncio.run(_main())
    assert any("tool_calls" in e for e in events)


def test_stream_response_stop_activa() -> None:
    async def _gen():
        yield "chunk1"
        yield "chunk2"

    async def _main() -> list[str]:
        m = StreamManager()
        events = []
        async for ev in m.stream_response("s1", _gen()):
            if "chunk1" in ev:
                m.stop_stream("s1")
            events.append(ev)
        return events

    events = asyncio.run(_main())
    # el stop corta el loop → solo chunk1, sin done completo con chunk2
    assert any("chunk1" in e for e in events)
    assert not any("chunk2" in e for e in events)


def test_build_tool_call_event() -> None:
    m = StreamManager()
    e = m.build_tool_call_event("calc", {"a": 1}, "call-1")
    assert e.event_type == "tool_call"
    assert e.data == {"id": "call-1", "name": "calc", "arguments": {"a": 1}}


# ── interruption ─────────────────────────────────────────────


def test_interruption_context_defaults() -> None:
    c = InterruptionContext(conversation_id="c1", interrupted_message="hola")
    assert c.interrupted_at != ""
    assert c.resumed is False
    assert c.context_before_interruption == []


def test_interruption_context_con_timestamp() -> None:
    c = InterruptionContext(conversation_id="c1", interrupted_message="hola", interrupted_at="2026-08-20T10:00:00")
    assert c.interrupted_at == "2026-08-20T10:00:00"


def test_interruption_detect_con_2_mensajes() -> None:
    sys_ = InterruptionSystem()
    msgs = [Message(role="assistant", content="respuesta larga"), Message(role="user", content="para")]
    assert sys_.detect_interruption("c1", msgs) is True
    ctx = sys_.get_interruption("c1")
    assert ctx is not None
    assert ctx.interrupted_message == "respuesta larga"


def test_interruption_detect_menos_2() -> None:
    sys_ = InterruptionSystem()
    assert sys_.detect_interruption("c1", [Message(role="user", content="hola")]) is False


def test_interruption_detect_no_interrupcion() -> None:
    sys_ = InterruptionSystem()
    msgs = [Message(role="user", content="hola"), Message(role="assistant", content="respuesta")]
    assert sys_.detect_interruption("c1", msgs) is False


def test_interruption_get_resumed_none() -> None:
    sys_ = InterruptionSystem()
    sys_._interruptions["c1"] = InterruptionContext(conversation_id="c1", interrupted_message="x", resumed=True)
    assert sys_.get_interruption("c1") is None
    assert sys_.get_interruption("no-existe") is None


def test_interruption_mark_resumed() -> None:
    sys_ = InterruptionSystem()
    sys_._interruptions["c1"] = InterruptionContext(conversation_id="c1", interrupted_message="x")
    sys_.mark_resumed("c1")
    assert sys_._interruptions["c1"].resumed is True
    sys_.mark_resumed("no-existe")  # no lanza


def test_auto_recover_context() -> None:
    sys_ = InterruptionSystem()
    sys_._interruptions["c1"] = InterruptionContext(
        conversation_id="c1",
        interrupted_message="estaba explicando",
        context_before_interruption=[{"role": "user", "content": "dime"}],
    )
    recovered = sys_.auto_recover_context("c1")
    assert "estaba explicando" in recovered
    assert "Modo: conversacion" in recovered
    assert sys_._interruptions["c1"].resumed is True


def test_auto_recover_sin_interrupcion() -> None:
    sys_ = InterruptionSystem()
    assert sys_.auto_recover_context("no-existe") == ""


# ── episodic_memory ──────────────────────────────────────────


class _MsgStoreFake:
    def __init__(self, convs: dict[str, list[Message]] | None = None) -> None:
        self._convs = convs or {}

    def get_conversation(self, conversation_id: str, limit: int = 50) -> list[Message]:
        return list(self._convs.get(conversation_id, []))[:limit]

    def append(self, conversation_id: str, message: Message) -> None:
        self._convs.setdefault(conversation_id, []).append(message)


class _TopicFake:
    def extract(self, text: str) -> list[str]:
        return ["python", "testing"]

    def extract_key_topic(self, text: str) -> str:
        return "python"


def test_topic_extractor_filtra_stop_words() -> None:
    t = TopicExtractor()
    topics = t.extract("el sistema python es muy rápido y eficiente testing")
    assert "python" in topics
    assert "testing" in topics
    assert "el" not in topics
    assert "es" not in topics


def test_topic_extractor_key_topic() -> None:
    t = TopicExtractor()
    assert t.extract_key_topic("el sistema python está fallando") == "sistema"
    assert t.extract_key_topic("el la los") == ""


def test_store_conversacion_ok() -> None:
    store = _MsgStoreFake({"c1": [Message(role="user", content="hola"), Message(role="assistant", content="hola a ti")]})
    m = EpisodicConversationMemory(message_store=store, topic_extractor=_TopicFake())
    sid = m.store_conversation("c1")
    assert sid != ""
    assert m._topic_index["python"] == [sid]
    assert len(m._topic_index["testing"]) == 1


def test_store_conversacion_corta() -> None:
    store = _MsgStoreFake({"c1": [Message(role="user", content="solo")]})
    m = EpisodicConversationMemory(message_store=store, topic_extractor=_TopicFake())
    assert m.store_conversation("c1") == ""


def test_retrieve_by_topic() -> None:
    store = _MsgStoreFake()
    m = EpisodicConversationMemory(message_store=store, topic_extractor=_TopicFake())
    m._topic_index["python"] = ["s1"]
    store._convs["_summary_s1"] = [Message(role="system", content="resumen conversacion")]
    results = m.retrieve_by_topic("python")
    assert results == ["resumen conversacion"]
    assert m.retrieve_by_topic("no-topic") == []


def test_retrieve_by_topic_sin_mensajes() -> None:
    store = _MsgStoreFake()
    m = EpisodicConversationMemory(message_store=store, topic_extractor=_TopicFake())
    m._topic_index["python"] = ["s1"]  # sin mensajes en el store
    assert m.retrieve_by_topic("python") == []


def test_store_conversacion_topic_repetido() -> None:
    store = _MsgStoreFake({"c1": [Message(role="user", content="hola"), Message(role="assistant", content="hola a ti")]})
    m = EpisodicConversationMemory(message_store=store, topic_extractor=_TopicFake())
    m._topic_index["python"] = ["anterior"]
    sid = m.store_conversation("c1")
    assert sid != ""
    assert m._topic_index["python"] == ["anterior", sid]  # rama else: topic ya existe


def test_get_relevant_context() -> None:
    store = _MsgStoreFake()
    m = EpisodicConversationMemory(message_store=store, topic_extractor=_TopicFake())
    m._topic_index["python"] = ["s1", "s2"]
    store._convs["_summary_s1"] = [Message(role="system", content="resumen uno")]
    store._convs["_summary_s2"] = [Message(role="system", content="resumen dos")]
    ctx = m.get_relevant_context("me puedes explicar python")
    assert "resumen dos" in ctx  # el más reciente
    assert "python" in ctx


def test_get_relevant_context_sin_topic() -> None:
    store = _MsgStoreFake()

    class _SinTopic(_TopicFake):
        def extract_key_topic(self, text: str) -> str:
            return ""

    m = EpisodicConversationMemory(message_store=store, topic_extractor=_SinTopic())
    assert m.get_relevant_context("hola") == ""


def test_get_relevant_context_sin_summaries() -> None:
    store = _MsgStoreFake()
    m = EpisodicConversationMemory(message_store=store, topic_extractor=_TopicFake())
    assert m.get_relevant_context("python") == ""


def test_compact_recorta() -> None:
    m = EpisodicConversationMemory(message_store=_MsgStoreFake(), topic_extractor=_TopicFake())
    msgs = [Message(role="user", content="mensaje largo " + "x" * 200), Message(role="assistant", content="respuesta")]
    compact = m._compact(msgs)
    assert "U: " in compact
    assert "A: " in compact
    assert len(compact.split("\n")) == 2


# ── corrective_learning ──────────────────────────────────────


def test_corrective_record_no_es() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    r = cm.record_correction("python no es lento, es rápido")
    assert r is not None
    assert r["corrected"] == "lento, es rápido"
    assert cm._cache["python"][0]["corrected"] == "lento, es rápido"


def test_corrective_record_en_realidad() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    r = cm.record_correction("en realidad el resultado es 42")
    assert r is not None
    assert r["original"] == "afirmación anterior"
    assert r["corrected"] == "el resultado es 42"


def test_corrective_record_corrige() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    r = cm.record_correction("corrige que el puerto es 8080")
    assert r is not None
    assert r["corrected"] == "que el puerto es 8080"


def test_corrective_record_sin_match() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    assert cm.record_correction("hola que tal") is None


def test_corrective_record_vacio() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    assert cm.record_correction("no es") is None
    assert cm.record_correction("corrige") is None
    # "en realidad" sin contenido devuelve dict con corrected vacío (comportamiento real)


def test_corrective_relevant() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    cm.record_correction("python no es lento, es rápido")
    res = cm.get_relevant_corrections("hablame de python")
    assert len(res) == 1
    assert res[0]["topic"] == "python"


def test_corrective_relevant_sin_match() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    cm.record_correction("python no es lento, es rápido")
    assert cm.get_relevant_corrections("hablame de gatos") == []


def test_corrective_relevant_limite_5() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    for i in range(7):
        cm.record_correction(f"python no es lento{i}, es rápido{i}")
    res = cm.get_relevant_corrections("python")
    assert len(res) == 5


def test_corrective_persistencia(tmp_path: object) -> None:
    db = str(tmp_path / "corrections.db")
    cm = CorrectiveMemory(db_path=db)
    cm.record_correction("python no es lento, es rápido")
    cm.record_correction("python no es malo, es bueno")  # mismo topic → rama else del load
    cm.record_correction("gatos no es verdad que sean feos")
    cm2 = CorrectiveMemory(db_path=db)
    res = cm2.get_relevant_corrections("python")
    assert len(res) == 2  # cache recargada desde sqlite
    assert len(cm2._cache) == 2  # topics distintos → rama True del load
    assert len(cm2._cache["python"]) == 2  # topic repetido → rama else del load


def test_corrective_extract_topic() -> None:
    cm = CorrectiveMemory(db_path=":memory:")
    assert cm._extract_topic("el sistema de python") == "sistema"
    assert cm._extract_topic("xy") == "xy"


# ── auto_mode ────────────────────────────────────────────────


def test_auto_mode_command() -> None:
    d = AutoModeDetector()
    r = d.detect_mode("haz algo", UserIntent.COMMAND)
    assert r.mode == ConversationMode.WORK
    assert r.confidence == pytest.approx(0.95)


def test_auto_mode_explain() -> None:
    d = AutoModeDetector()
    r = d.detect_mode("explícame qué es python", UserIntent.CHAT)
    assert r.mode == ConversationMode.EXPLANATION
    assert r.confidence == pytest.approx(0.9)


def test_auto_mode_concise() -> None:
    d = AutoModeDetector()
    r = d.detect_mode("resume en una frase", UserIntent.CHAT)
    assert r.mode == ConversationMode.CONVERSATION
    assert r.confidence == pytest.approx(0.85)


def test_auto_mode_work_trigger() -> None:
    d = AutoModeDetector()
    r = d.detect_mode("busca el archivo", UserIntent.CHAT)
    assert r.mode == ConversationMode.WORK
    assert r.confidence == pytest.approx(0.8)


def test_auto_mode_previous() -> None:
    d = AutoModeDetector()
    r = d.detect_mode("cualquier cosa", UserIntent.CHAT, previous_mode=ConversationMode.EXPLANATION)
    assert r.mode == ConversationMode.EXPLANATION
    assert r.confidence == pytest.approx(0.7)


def test_auto_mode_default() -> None:
    d = AutoModeDetector()
    r = d.detect_mode("cualquier cosa", UserIntent.CHAT)
    assert r.mode == ConversationMode.CONVERSATION
    assert r.confidence == pytest.approx(0.6)


def test_auto_mode_set_get() -> None:
    d = AutoModeDetector()
    d.set_mode("c1", ConversationMode.WORK)
    assert d.get_mode("c1") == ConversationMode.WORK
    assert d.get_mode("no-existe") is None
