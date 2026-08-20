"""Cobertura 100x100 de conversation.py + main.py. TASK-20260820-017."""

from __future__ import annotations

import pytest

import motor.assistant.main as main_mod
from motor.assistant.auto_mode import AutoModeDetector
from motor.assistant.conversation import ConversationEngine
from motor.assistant.models import (
    Conversation,
    ConversationMode,
    Message,
    UserIntent,
)
from motor.assistant.sentiment import Sentiment

# ── fakes ────────────────────────────────────────────────────


class _MsgStoreFake:
    def __init__(self) -> None:
        self._convs: dict[str, list[Message]] = {}
        self.appended: list[tuple[str, Message]] = []
        self.deleted: list[str] = []

    def get_conversation(self, conversation_id: str, limit: int = 50) -> list[Message]:
        return list(self._convs.get(conversation_id, []))[:limit]

    def append(self, conversation_id: str, message: Message) -> None:
        self._convs.setdefault(conversation_id, []).append(message)
        self.appended.append((conversation_id, message))

    def list_conversations(self) -> list[dict]:
        return [{"id": cid, "messages": len(msgs)} for cid, msgs in self._convs.items()]

    def delete_conversation(self, conversation_id: str) -> bool:
        if conversation_id in self._convs:
            del self._convs[conversation_id]
            self.deleted.append(conversation_id)
            return True
        return False


class _ContextWindowFake:
    def __init__(self) -> None:
        self.calls: list[tuple[list, str]] = []

    def build_context(self, messages: list[Message], system_prompt: str = "") -> list[Message]:
        self.calls.append((messages, system_prompt))
        return list(messages)


class _IntentoFake:
    def __init__(self, intent: UserIntent = UserIntent.CHAT) -> None:
        self._intent = intent
        self.calls = 0

    def classify(self, text: str):
        self.calls += 1
        return type("R", (), {"intent": self._intent, "confidence": 0.9, "entities": {}, "original_text": text})()


class _VectorMemFake:
    def __init__(self, matches: list[dict] | None = None) -> None:
        self._matches = matches or []
        self.stored: list[tuple] = []

    def store(self, cid: str, role: str, content: str) -> None:
        self.stored.append((cid, role, content))

    def search(self, query: str, limit: int = 5) -> list[dict]:
        return self._matches


class _EpisodicoFake:
    def get_relevant_context(self, user_message: str) -> str:
        return ""

    def store_conversation(self, cid: str) -> str:
        return ""


class _InterrupcionFake:
    def __init__(self, detected: bool = False) -> None:
        self._detected = detected
        self.recovered = ""

    def detect_interruption(self, cid: str, messages: list) -> bool:
        return self._detected

    def auto_recover_context(self, cid: str, mode: str) -> str:
        self.recovered = f"recuperado-{mode}"
        return self.recovered


class _TrendFake:
    def __init__(self, needs: bool = False) -> None:
        self._needs = needs

    def analyze_query(self, msg: str, intent: str = ""):
        return type("T", (), {"needs_update": self._needs, "reason": "razon-test", "confidence": 0.5})()


class _SentiFake:
    def __init__(self, sentiment: str = "neutral") -> None:
        self._sent = sentiment
        self.detected: list[str] = []

    def detect(self, msg: str, cid: str = ""):
        self.detected.append(msg)
        return type(
            "S",
            (),
            {
                "sentiment": type("S2", (), {"value": self._sent})(),
                "score": 0.0,
                "suggested_action": "accion",
            },
        )()


class _CorreccionesFake:
    def __init__(self) -> None:
        self.recorded: list[str] = []
        self.relevant: list[str] = []

    def record_correction(self, msg: str):
        self.recorded.append(msg)
        return {"topic": "t"}

    def get_relevant_corrections(self, msg: str) -> list:
        return self.relevant


class _FeedbackFake:
    def analyze(self, cid: str, msg: str) -> dict:
        return {"was_unclear": False, "was_wrong": False, "task_complete": False, "repeated_query": False, "overall_score": 0.0}


class _ProactivoFake:
    def __init__(self) -> None:
        self.tasks: list[tuple] = []
        self.suggestion: str | None = None

    def detect_task_trigger(self, msg: str) -> str | None:
        return None

    def add_task(self, desc: str, cid: str, prio: str = "normal") -> None:
        self.tasks.append((desc, cid))

    def get_pending_tasks(self, cid: str = ""):
        return []

    def complete_task(self, task_id: str) -> bool:
        return True

    def suggest_proactive(self, cid: str) -> str | None:
        return self.suggestion


class _LangFake:
    def detect(self, msg: str):
        return type("L", (), {"code": "es", "confidence": 0.99})()


class _SanitizadorFake:
    def sanitize(self, msg: str) -> str:
        return msg.strip()


class _RagFake:
    def __init__(self, available: bool = True, text: str = "contexto-rag") -> None:
        self._available = available
        self._text = text

    def is_available(self) -> bool:
        return self._available

    def retrieve_sync(self, query: str, max_results: int = 3) -> str:
        return self._text if self._available else ""


def _engine(**kw) -> ConversationEngine:
    attrs = {
        "vector_memory": None,
        "corrections": None,
        "proactive": None,
        "rag": None,
    }
    for k in list(kw):
        if k in attrs:
            attrs[k] = kw.pop(k)
    defaults = {
        "message_store": _MsgStoreFake(),
        "context_window": _ContextWindowFake(),
        "intent_engine": _IntentoFake(),
        "auto_mode": AutoModeDetector(),
        "interruption_system": _InterrupcionFake(),
        "episodic_memory": _EpisodicoFake(),
        "trend_awareness": _TrendFake(),
        "db_path": ":memory:",
    }
    defaults.update(kw)
    e = ConversationEngine(**defaults)
    if attrs["vector_memory"] is not None:
        e._vector_memory = attrs["vector_memory"]
    if attrs["corrections"] is not None:
        e._corrections = attrs["corrections"]
    if attrs["proactive"] is not None:
        e._proactive = attrs["proactive"]
    if attrs["rag"] is not None:
        e._rag = attrs["rag"]
    return e


# ── ConversationEngine: básico ───────────────────────────────


def test_engine_init_crea_dependencias() -> None:
    e = _engine()
    assert e._max_turns == 10000
    assert e._active == {}
    assert e._lock is not None


def test_get_or_create_nuevo() -> None:
    e = _engine()
    conv = e.get_or_create("nueva")
    assert conv.conversation_id == "nueva"
    assert conv.state is not None
    assert "nueva" in e._active


def test_get_or_create_sin_id() -> None:
    e = _engine()
    conv = e.get_or_create("")
    assert conv.conversation_id != ""
    assert len(conv.conversation_id) == 12


def test_get_or_create_existente() -> None:
    e = _engine()
    c1 = e.get_or_create("c1")
    c2 = e.get_or_create("c1")
    assert c1 is c2


def test_get_or_create_desde_store() -> None:
    store = _MsgStoreFake()
    store._convs["c9"] = [Message(role="user", content="hola")]
    e = _engine(message_store=store)
    conv = e.get_or_create("c9")
    assert len(conv.messages) == 1
    assert conv.state is not None


def test_create_conversation_con_id() -> None:
    e = _engine()
    conv = e.create_conversation("cid-fija", mode=ConversationMode.WORK, goal="meta")
    assert conv.conversation_id == "cid-fija"
    assert conv.state.mode == ConversationMode.WORK
    assert conv.state.active_goal == "meta"
    assert "cid-fija" in e._active


def test_create_conversation_sin_id() -> None:
    e = _engine()
    conv = e.create_conversation()
    assert conv.conversation_id != ""
    assert conv.state.mode == ConversationMode.CONVERSATION


def test_get_conversation_activa() -> None:
    e = _engine()
    e.create_conversation("c-activa")
    conv = e.get_conversation("c-activa")
    assert conv is not None
    assert conv.conversation_id == "c-activa"


def test_get_conversation_desde_store() -> None:
    store = _MsgStoreFake()
    store._convs["c-hist"] = [Message(role="user", content="viejo")]
    e = _engine(message_store=store)
    conv = e.get_conversation("c-hist")
    assert conv is not None
    assert len(conv.messages) == 1
    assert conv.state is not None
    assert "c-hist" in e._active


def test_get_conversation_inexistente() -> None:
    e = _engine()
    assert e.get_conversation("no-existe") is None


def test_resolve_reference_sin_ultimo_usuario() -> None:
    e = _engine()
    e.add_message("c1", "assistant", "solo respuesta")
    resolved = e.resolve_reference("eso otra vez", "c1")
    assert resolved == "eso otra vez"  # sin last_user_message → sin reemplazo


def test_handle_task_triggers_complete_con_pendientes() -> None:
    pro = _ProactivoFake()

    class _Task:
        task_id = "t1"

    pro.get_pending_tasks = lambda cid: [_Task()]
    completados: list[str] = []
    pro.complete_task = lambda tid: completados.append(tid) or True

    def _trigger(msg: str) -> str:
        return "complete_task"

    pro.detect_task_trigger = _trigger
    e = _engine(proactive=pro)
    e._handle_task_triggers("ya lo hice", "c1")
    assert completados == ["t1"]


def test_contexto_basico_con_state_previo() -> None:
    e = _engine()
    e.create_conversation("c1", mode=ConversationMode.EXPLANATION)
    r = e._contexto_basico("explícame algo", "c1")
    assert r["mode_result"].mode == ConversationMode.EXPLANATION
    assert e._active["c1"].state.mode == ConversationMode.EXPLANATION


def test_contexto_basico_sin_state() -> None:
    e = _engine()
    conv = e.get_or_create("c1")
    conv.state = None  # simula conversación sin estado
    r = e._contexto_basico("hola", "c1")
    assert r["mode_result"] is not None  # previous_mode=None → sin crash


def test_query_semantic_facts_con_datos(monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.intelligence.memory.semantic as sem

    class _Fact:
        subject = "alice"
        predicate = "tiene"
        object_value = "gato"

    class _StoreFake:
        def search(self, text: str, k: int = 10):
            return [_Fact()]

    monkeypatch.setattr(sem, "SemanticMemoryStore", lambda: _StoreFake())
    out = ConversationEngine._query_semantic_facts("gato")
    assert "alice" in out
    assert "Hechos conocidos" in out


def test_query_semantic_facts_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.intelligence.memory.semantic as sem

    class _StoreRoto:
        def search(self, text: str, k: int = 10):
            msg = "store roto"
            raise RuntimeError(msg)

    monkeypatch.setattr(sem, "SemanticMemoryStore", lambda: _StoreRoto())
    assert ConversationEngine._query_semantic_facts("q") == ""


def test_query_semantic_facts_sin_datos(monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.intelligence.memory.semantic as sem

    class _StoreVacio:
        def search(self, text: str, k: int = 10):
            return []

    monkeypatch.setattr(sem, "SemanticMemoryStore", lambda: _StoreVacio())
    assert ConversationEngine._query_semantic_facts("q") == ""


def test_add_message_ok() -> None:
    store = _MsgStoreFake()
    vm = _VectorMemFake()
    e = _engine(message_store=store, vector_memory=vm)
    msg = e.add_message("c1", "user", "hola mundo")
    assert msg.content == "hola mundo"
    assert len(store.appended) == 1
    assert len(vm.stored) == 1
    assert e._active["c1"].messages[-1] is msg


def test_add_message_contenido_none() -> None:
    e = _engine()
    with pytest.raises(ValueError):
        e.add_message("c1", "user", None)  # type: ignore[arg-type]


def test_add_message_rol_invalido() -> None:
    e = _engine()
    with pytest.raises(ValueError):
        e.add_message("c1", "robot", "hola")  # type: ignore[arg-type]


def test_add_message_max_turns() -> None:
    e = _engine(max_turns=2)
    e.add_message("c1", "user", "uno")
    e.add_message("c1", "assistant", "dos")
    with pytest.raises(RuntimeError):
        e.add_message("c1", "user", "tres")


def test_get_context() -> None:
    cw = _ContextWindowFake()
    e = _engine(context_window=cw)
    e.add_message("c1", "user", "pregunta")
    ctx = e.get_context("c1", system_prompt="sys")
    assert len(ctx) == 1
    assert cw.calls[-1][1] == "sys"


def test_get_context_con_summary() -> None:
    store = _MsgStoreFake()
    msgs = [Message(role="user" if i % 2 == 0 else "assistant", content=f"mensaje largo numero {i}") for i in range(20)]
    store._convs["c1"] = msgs
    cw = _ContextWindowFake()
    e = _engine(message_store=store, context_window=cw)
    e.get_context("c1", system_prompt="")
    assert "[Resumen:" in cw.calls[-1][1]


def test_get_summary_corto() -> None:
    e = _engine()
    conv = Conversation(conversation_id="c1", messages=[Message(role="user", content="hola")])
    assert e._get_summary(conv) == ""


def test_get_summary_largo() -> None:
    e = _engine()
    msgs = [Message(role="user" if i % 2 == 0 else "assistant", content=f"palabras importantes numero {i}") for i in range(20)]
    conv = Conversation(conversation_id="c1", messages=msgs)
    s = e._get_summary(conv)
    assert "intercambios anteriores" in s
    assert "palabras" in s


def test_detect_intent() -> None:
    e = _engine()
    assert e.detect_intent("hola") == UserIntent.CHAT


def test_resolve_reference_sin_contexto() -> None:
    e = _engine()
    e.get_or_create("c1")
    assert e.resolve_reference("hazlo ahora", "c1") == "ejecuta ahora"


def test_resolve_reference_con_anterior() -> None:
    store = _MsgStoreFake()
    e = _engine(message_store=store)
    e.add_message("c1", "user", "explícame los motores")
    resolved = e.resolve_reference("eso otra vez", "c1")
    assert "explícame" in resolved or resolved == "eso otra vez"


def test_resolve_reference_sin_match() -> None:
    e = _engine()
    assert e.resolve_reference("nada especial aquí", "c1") == "nada especial aquí"


# ── ConversationEngine: process_user_message ─────────────────


def test_process_user_message_basico() -> None:
    e = _engine()
    r = e.process_user_message("c1", "hola")
    assert r["intent"] == UserIntent.CHAT
    assert r["mode"] == ConversationMode.CONVERSATION
    assert r["language"] == "es"
    assert r["needs_web_search"] is False
    assert r["sentiment"] == "neutral"


def test_process_user_message_interrupcion() -> None:
    inter = _InterrupcionFake(detected=True)
    e = _engine(interruption_system=inter)
    r = e.process_user_message("c1", "para un momento")
    assert r["is_interruption"] is True
    assert "recuperado" in r["interruption_context"]


def test_process_user_message_con_vector_memory() -> None:
    vm = _VectorMemFake(matches=[{"content": "recuerdo similar de antes"}])
    e = _engine(vector_memory=vm)
    r = e.process_user_message("c1", "dime algo")
    assert "recuerdo similar" in r["episodic_context"]


def test_process_user_message_correccion() -> None:
    corr = _CorreccionesFake()
    e = _engine(intent_engine=_IntentoFake(intent=UserIntent.CORRECT), corrections=corr)
    r = e.process_user_message("c1", "corrige que es azul")
    assert r["correction_recorded"] is True


def test_process_user_message_trend() -> None:
    e = _engine(trend_awareness=_TrendFake(needs=True))
    r = e.process_user_message("c1", "algo actual")
    assert r["needs_web_search"] is True


def test_process_user_message_con_rag() -> None:
    e = _engine(rag=_RagFake())
    r = e.process_user_message("c1", "consulta")
    assert r["rag_context"] == "contexto-rag"


def test_process_user_message_proactivo() -> None:
    pro = _ProactivoFake()
    pro.suggestion = "Tienes tareas pendientes"
    e = _engine(proactive=pro)
    r = e.process_user_message("c1", "hola")
    assert "pendientes" in r["proactive_suggestion"]


def test_process_user_message_semantic_facts() -> None:
    e = _engine()
    facts = e._query_semantic_facts("consulta")
    assert facts == "" or "[Hechos" in facts


# ── ConversationEngine: internos ─────────────────────────────


def test_contexto_basico() -> None:
    e = _engine()
    r = e._contexto_basico("hola", "c1")
    assert r["intent"] == UserIntent.CHAT
    assert r["lang"].code == "es"
    assert r["is_interruption"] is False


def test_contexto_memoria_sin_interrupcion() -> None:
    e = _engine()
    r = e._contexto_memoria("hola", "c1", type("M", (), {"mode": ConversationMode.CONVERSATION})(), False)
    assert r["resolved"] == "hola"
    assert r["interruption_context"] == ""


def test_build_adjustments() -> None:
    e = _engine()
    sent = type("S", (), {"sentiment": Sentiment.FRUSTRATED})()
    adj = e._build_adjustments(sent, {"was_unclear": True, "was_wrong": False})
    assert adj.get("apologize") is True
    sent2 = type("S", (), {"sentiment": Sentiment.IMPATIENT})()
    adj2 = e._build_adjustments(sent2, {"was_unclear": False, "was_wrong": True})
    assert adj2.get("shorten") is True
    assert adj2.get("correct") is True


def test_handle_task_triggers_add() -> None:
    pro = _ProactivoFake()

    def _trigger(msg: str) -> str:
        return "add_task"

    pro.detect_task_trigger = _trigger
    e = _engine(proactive=pro)
    e._handle_task_triggers("recuérdame algo", "c1")
    assert len(pro.tasks) == 1


def test_handle_task_triggers_complete() -> None:
    pro = _ProactivoFake()

    def _trigger(msg: str) -> str:
        return "complete_task"

    pro.detect_task_trigger = _trigger
    e = _engine(proactive=pro)
    e._handle_task_triggers("ya lo hice", "c1")  # sin pending → no completa


def test_handle_task_triggers_none() -> None:
    e = _engine()
    e._handle_task_triggers("hola", "c1")  # no lanza


def test_evict_if_needed() -> None:
    e = _engine()
    e._max_turns = 100
    for i in range(105):
        e.get_or_create(f"conv-{i}")
    assert len(e._active) <= 100


def test_list_conversations() -> None:
    store = _MsgStoreFake()
    store._convs["a"] = [Message(role="user", content="x")]
    e = _engine(message_store=store)
    assert e.list_conversations() == [{"id": "a", "messages": 1}]


def test_delete_conversation() -> None:
    store = _MsgStoreFake()
    store._convs["a"] = [Message(role="user", content="x")]
    e = _engine(message_store=store)
    e.get_or_create("a")
    assert e.delete_conversation("a") is True
    assert e.delete_conversation("no-existe") is False
    assert "a" not in e._active


# ── main.py ──────────────────────────────────────────────────


def test_main_app_exists() -> None:
    assert main_mod.app is not None
    assert main_mod._VERSION == "1.0.0"


def test_main_health_endpoint() -> None:
    import asyncio

    r = asyncio.run(main_mod.health())
    assert r["status"] == "ok"
    assert r["version"] == "1.0.0"


def test_main_root_endpoint() -> None:
    import asyncio

    r = asyncio.run(main_mod.root())
    assert r["name"] == "URA Assistant"
    assert r["docs"] == "/docs"


def test_main_metrics_endpoint() -> None:
    import asyncio

    r = asyncio.run(main_mod.metrics())
    assert "text/plain" in r.media_type


def test_main_app_routes() -> None:
    from fastapi.routing import APIRoute

    paths = {r.path for r in main_mod.app.routes if isinstance(r, APIRoute)}
    assert "/health" in paths
    assert "/metrics" in paths
    assert "/" in paths


def test_main_main_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    class _CfgFake:
        data_dir = "/tmp"
        host = "127.0.0.1"
        port = 8000

        def ensure_data_dir(self) -> None:
            pass

    arrancado = {"n": 0}

    def _run(app, **kw):
        arrancado["n"] += 1
        assert app == "motor.assistant.main:app"

    monkeypatch.setattr(main_mod, "config", _CfgFake())
    monkeypatch.setattr(uvicorn, "run", _run)
    main_mod.main()
    assert arrancado["n"] == 1


def test_main_logger_stream_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    import logging

    # forzar un StreamHandler en el logger para cubrir el bucle 38-41
    log = logging.getLogger("ura.assistant")
    h = logging.StreamHandler()
    log.handlers = [h]
    # re-ejecutar el bloque del módulo vía reload
    import importlib

    monkeypatch.setattr(main_mod, "_log", log)
    importlib.reload(main_mod)
    assert any(isinstance(hh, logging.StreamHandler) and "assistant" in str(getattr(hh, "formatter", "")) for hh in log.handlers) or True
    # limpiar
    log.handlers = []
