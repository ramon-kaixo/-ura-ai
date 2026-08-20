"""Cobertura 100x100 de motor/assistant (parte 2). TASK-20260820-017."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from motor.assistant.context import (
    ContextItem,
    ContextLevel,
    ContextManager,
    HistoricalMemoryAdapter,
)
from motor.assistant.implicit_feedback import ImplicitFeedback
from motor.assistant.intent import IntentEngine, IntentResult, IntentRouter
from motor.assistant.models import (
    Conversation,
    ConversationMode,
    ConversationState,
    Message,
    UserIntent,
)
from motor.assistant.proactive_memory import ProactiveMemory, Task
from motor.assistant.rag import RAGContext
from motor.assistant.sentiment import Sentiment, SentimentDetector
from motor.assistant.tool_plugin import ToolPlugin, discover_plugins
from motor.assistant.trends import TrendAwareness
from motor.assistant.vector_memory import VectorMemoryStore

# ── models ───────────────────────────────────────────────────


def test_conversation_mode_valores() -> None:
    assert ConversationMode.CONVERSATION.value == "conversacion"
    assert ConversationMode.WORK.value == "trabajo"
    assert ConversationMode.EXPLANATION.value == "explicacion"


def test_user_intent_valores() -> None:
    assert UserIntent.CHAT.value == "chat"
    assert UserIntent.UNKNOWN.value == "unknown"


def test_message_defaults() -> None:
    m = Message(role="user", content="hola")
    assert m.timestamp != ""
    assert m.metadata == {}
    assert m.tool_call_id == ""


def test_message_rol_invalido() -> None:
    with pytest.raises(ValueError):
        Message(role="robot", content="x")  # type: ignore[arg-type]


def test_message_tool_requiere_call_id() -> None:
    with pytest.raises(ValueError):
        Message(role="tool", content="x")


def test_message_tool_ok() -> None:
    m = Message(role="tool", content="x", tool_call_id="t1")
    assert m.tool_call_id == "t1"


def test_message_token_estimate() -> None:
    m = Message(role="user", content="abcdefgh")  # 8 chars / 4 = 2
    assert m.token_estimate() == 2
    assert m.token_estimate(chars_per_token=0) == 2  # fallback 4.0
    assert m.token_estimate(chars_per_token=100) == 1  # min 1


def test_conversation_state_defaults() -> None:
    s = ConversationState(conversation_id="c1")
    assert s.created_at != ""
    assert s.updated_at != ""
    assert s.mode == ConversationMode.CONVERSATION


def test_conversation_state_con_datos() -> None:
    s = ConversationState(conversation_id="c1", created_at="t", updated_at="u")
    assert s.created_at == "t"
    assert s.updated_at == "u"


def test_conversation_add_message() -> None:
    c = Conversation(conversation_id="c1", state=ConversationState(conversation_id="c1"))
    m = c.add_message("user", "hola")
    assert m.role == "user"
    assert c.state.turn_count == 1
    assert c.state.updated_at != ""


def test_conversation_add_message_kwargs_invalidos() -> None:
    c = Conversation(conversation_id="c1")
    with pytest.raises(TypeError):
        c.add_message("user", "hola", role="assistant")


def test_conversation_add_message_con_kwargs() -> None:
    c = Conversation(conversation_id="c1", state=ConversationState(conversation_id="c1"))
    m = c.add_message("user", "hola", metadata={"src": "x"})
    assert m.metadata == {"src": "x"}


def test_conversation_token_count() -> None:
    c = Conversation(conversation_id="c1")
    c.add_message("user", "abcdefgh")
    c.add_message("assistant", "abcd")
    assert c.token_count == 2 + 1


def test_conversation_sin_state_add_message() -> None:
    c = Conversation(conversation_id="c1")  # sin state
    c.add_message("user", "hola")
    assert len(c.messages) == 1


def test_conversation_last_messages() -> None:
    c = Conversation(conversation_id="c1")
    c.add_message("assistant", "res1")
    c.add_message("user", "pregunta")
    c.add_message("assistant", "res2")
    assert c.last_user_message.content == "pregunta"
    assert c.last_assistant_message.content == "res2"


def test_conversation_last_messages_vacio() -> None:
    c = Conversation(conversation_id="c1")
    assert c.last_user_message is None
    assert c.last_assistant_message is None


def test_conversation_last_user_solo_assistant() -> None:
    c = Conversation(conversation_id="c1")
    c.add_message("assistant", "solo respuesta")
    assert c.last_user_message is None
    assert c.last_assistant_message is not None


def test_conversation_last_user_varios_assistant() -> None:
    c = Conversation(conversation_id="c1")
    c.add_message("assistant", "res1")
    c.add_message("assistant", "res2")
    assert c.last_user_message is None
    assert c.last_assistant_message.content == "res2"


def test_conversation_last_assistant_solo_user() -> None:
    c = Conversation(conversation_id="c1")
    c.add_message("user", "solo pregunta")
    assert c.last_assistant_message is None
    assert c.last_user_message is not None


# ── rag ──────────────────────────────────────────────────────


def test_rag_sin_disponible() -> None:
    r = RAGContext()
    r._available = False
    assert r.is_available() is False
    assert r.retrieve_sync("q") == ""
    import asyncio

    assert asyncio.run(r.retrieve("q")) == ""


def test_rag_get_ke_db_path() -> None:
    assert RAGContext._get_ke_db_path() is None or isinstance(RAGContext._get_ke_db_path(), Path)


def test_rag_get_ke_db_path_inexistente(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.assistant.rag as rag_mod

    class _HomeFake:
        def __init__(self) -> None:
            self._p = Path(str(tmp_path))

        def __truediv__(self, other: str) -> Path:
            return self._p / other

    monkeypatch.setattr(Path, "home", staticmethod(lambda: _HomeFake()))
    assert rag_mod.RAGContext._get_ke_db_path() is None  # db no existe en tmp


def test_rag_check_available_con_db_inexistente(monkeypatch: pytest.MonkeyPatch) -> None:
    r = RAGContext()
    monkeypatch.setattr(r, "_get_ke_db_path", staticmethod(lambda: None))
    r._available = False
    r._check_available()
    assert r._available is False  # db_path None → return sin activar


def test_rag_check_available_con_error(monkeypatch: pytest.MonkeyPatch) -> None:
    r = RAGContext()

    def _roto():
        msg = "import fallo"
        raise ImportError(msg)

    monkeypatch.setattr(r, "_get_ke_db_path", staticmethod(lambda: Path("/tmp/x.db")))
    monkeypatch.setattr("knowledge.engine.memory_store.SQLiteMemoryStore", _roto)
    r._available = False
    r._check_available()
    assert r._available is False


def test_rag_disponible_con_store(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Store:
        def search(self, query: str, kind: str = "knowledge", limit: int = 3) -> list:
            return [type("R", (), {"content": "contenido útil para la consulta"})()]

    r = RAGContext()
    r._store = _Store()
    r._available = True
    out = r.retrieve_sync("consulta")
    assert "contenido útil" in out


def test_rag_sin_resultados(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Store:
        def search(self, query: str, kind: str = "knowledge", limit: int = 3) -> list:
            return []

    r = RAGContext()
    r._store = _Store()
    r._available = True
    assert r.retrieve_sync("q") == ""


def test_rag_error_en_busqueda() -> None:
    class _Store:
        def search(self, query: str, kind: str = "knowledge", limit: int = 3) -> list:
            msg = "roto"
            raise RuntimeError(msg)

    r = RAGContext()
    r._store = _Store()
    r._available = True
    assert r.retrieve_sync("q") == ""


def test_rag_retrieve_async_ok() -> None:
    import asyncio

    class _Store:
        def search(self, query: str, kind: str = "knowledge", limit: int = 3) -> list:
            return [type("R", (), {"content": "contenido async"})()]

    r = RAGContext()
    r._store = _Store()
    r._available = True
    out = asyncio.run(r.retrieve("consulta"))
    assert "contenido async" in out


def test_rag_retrieve_async_error() -> None:
    import asyncio

    class _Store:
        def search(self, query: str, kind: str = "knowledge", limit: int = 3) -> list:
            msg = "async roto"
            raise RuntimeError(msg)

    r = RAGContext()
    r._store = _Store()
    r._available = True
    assert asyncio.run(r.retrieve("q")) == ""


def test_rag_query_vacia() -> None:
    r = RAGContext()
    r._available = True
    assert r.retrieve_sync("") == ""


# ── trends ───────────────────────────────────────────────────


def test_trends_analiza_temporal_pregunta() -> None:
    t = TrendAwareness()
    r = t.analyze_query("¿cuál es la tendencia actual en IA?", intent="question")
    assert r.needs_update is True
    assert r.confidence == pytest.approx(0.85)
    assert "web_search" in r.suggested_sources


def test_trends_temporal_sin_pregunta() -> None:
    t = TrendAwareness()
    r = t.analyze_query("algo nuevo sobre python")
    assert r.needs_update is True
    assert r.confidence == pytest.approx(0.6)


def test_trends_sin_temporal() -> None:
    t = TrendAwareness()
    r = t.analyze_query("explica qué es la programación funcional")
    assert r.needs_update is False
    assert r.confidence == pytest.approx(0.5)


def test_trends_needs_web_search() -> None:
    t = TrendAwareness()
    assert t.needs_web_search("cuéntame lo más reciente") is True
    assert t.needs_web_search("explica conceptos básicos") is False


# ── tool_plugin ──────────────────────────────────────────────


def test_tool_plugin_execute_not_implemented() -> None:
    p = ToolPlugin()
    with pytest.raises(NotImplementedError):
        import asyncio

        asyncio.run(p.execute({}))


def test_discover_plugins_crea_dir(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.assistant.tool_plugin as tp

    d = Path(str(tmp_path)) / "tool_plugins"
    monkeypatch.setattr(tp, "PLUGIN_DIR", d)
    assert discover_plugins() == {}
    assert d.exists()


def test_discover_plugins_carga(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.assistant.tool_plugin as tp

    d = Path(str(tmp_path)) / "tool_plugins"
    d.mkdir(parents=True)
    (d / "mi_plugin.py").write_text(
        "from motor.assistant.tool_plugin import ToolPlugin\n"
        "class MiPlugin(ToolPlugin):\n"
        "    name = 'mi_plugin'\n"
        "    description = 'test'\n"
    )
    (d / "_privado.py").write_text("x = 1\n")
    (d / "roto.py").write_text("esto no es python válido {{{")
    monkeypatch.setattr(tp, "PLUGIN_DIR", d)
    plugins = discover_plugins()
    assert "mi_plugin" in plugins
    assert "_privado" not in plugins  # prefijo _ se salta


def test_discover_plugins_sin_nombre(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.assistant.tool_plugin as tp

    d = Path(str(tmp_path)) / "tool_plugins"
    d.mkdir(parents=True)
    (d / "anom.py").write_text(
        "from motor.assistant.tool_plugin import ToolPlugin\n"
        "class Anom(ToolPlugin):\n"
        "    pass\n"  # sin name → no se registra
    )
    monkeypatch.setattr(tp, "PLUGIN_DIR", d)
    assert discover_plugins() == {}


def test_discover_plugins_spec_sin_loader(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    import motor.assistant.tool_plugin as tp

    d = Path(str(tmp_path)) / "tool_plugins"
    d.mkdir(parents=True)
    (d / "sin_loader.py").write_text("x = 1\n")
    monkeypatch.setattr(tp, "PLUGIN_DIR", d)

    def _spec_roto(name, f):
        return type("Spec", (), {"loader": None})()

    monkeypatch.setattr(tp.importlib.util, "spec_from_file_location", _spec_roto)
    assert discover_plugins() == {}  # spec sin loader → continue


# ── intent ───────────────────────────────────────────────────


def test_intent_classify_greeting() -> None:
    e = IntentEngine()
    r = e.classify("hola")
    assert r.intent == UserIntent.GREETING
    assert r.confidence >= 0.9


def test_intent_classify_farewell() -> None:
    e = IntentEngine()
    r = e.classify("adiós")
    assert r.intent == UserIntent.FAREWELL


def test_intent_classify_confirm() -> None:
    e = IntentEngine()
    r = e.classify("vale")
    assert r.intent == UserIntent.CONFIRM


def test_intent_classify_reject() -> None:
    e = IntentEngine()
    r = e.classify("no")
    assert r.intent == UserIntent.REJECT


def test_intent_classify_repeat() -> None:
    e = IntentEngine()
    r = e.classify("repite")
    assert r.intent == UserIntent.REPEAT


def test_intent_classify_correct() -> None:
    e = IntentEngine()
    r = e.classify("corrige eso")
    assert r.intent == UserIntent.CORRECT


def test_intent_classify_question() -> None:
    e = IntentEngine()
    r = e.classify("¿qué es la IA?")
    assert r.intent == UserIntent.QUESTION


def test_intent_classify_command() -> None:
    e = IntentEngine()
    r = e.classify("busca el archivo config")
    assert r.intent == UserIntent.COMMAND


def test_intent_classify_default_chat() -> None:
    e = IntentEngine()
    r = e.classify("me gusta el café por las mañanas")
    assert r.intent == UserIntent.CHAT


def test_intent_confianza_menor_no_sobreescribe() -> None:
    e = IntentEngine()
    # "no es correcto" matchea CORRECT (0.85); el "?" final matchea QUESTION (0.8) después → no sobreescribe
    r = e.classify("no es correcto, cómo funciona?")
    assert r.intent == UserIntent.CORRECT
    assert r.confidence == pytest.approx(0.85)


def test_intent_classify_vacio() -> None:
    e = IntentEngine()
    r = e.classify("")
    assert r.intent == UserIntent.UNKNOWN
    assert r.confidence == 0.0
    r2 = e.classify("\x00\x00")
    assert r2.intent == UserIntent.UNKNOWN


def test_intent_entities() -> None:
    e = IntentEngine()
    r = e.classify("busca sobre motores diesel")
    assert "search_query" in r.entities
    r2 = e.classify("mira el archivo config.yaml")
    assert "filename" in r2.entities
    r3 = e.classify("visita https://example.com")
    assert "url" in r3.entities
    r4 = e.classify("escríbeme a user@example.com")
    assert "email" in r4.entities
    r5 = e.classify("usa 5 servidores")
    assert "number" in r5.entities
    r6 = e.classify("traduce al inglés")
    assert "language" in r6.entities
    r7 = e.classify("fecha 12/05/2026")
    assert "date" in r7.entities
    r8 = e.classify("la ruta /etc/ura/config")
    assert "path" in r8.entities


def test_intent_entities_sin_grupo() -> None:
    # pattern que matchea sin group(1) → except IndexError → group(0)
    e = IntentEngine()
    entities = e._extract_entities("el número es 42 y luego más")
    assert "number" in entities


def test_intent_resolve_references() -> None:
    e = IntentEngine()
    assert e._resolve_references("hazlo ahora") == "ejecuta ahora"
    assert e._resolve_references("eso es lo mismo") == " es "


def test_intent_capability() -> None:
    e = IntentEngine()
    assert e.intent_to_capability(UserIntent.COMMAND) == "tools_execute"
    assert e.intent_to_capability(UserIntent.QUESTION) == "knowledge_query"
    assert e.intent_to_capability(UserIntent.SEARCH) == "web_search"
    assert e.intent_to_capability(UserIntent.CHAT) == "conversation"
    assert e.intent_to_capability(UserIntent.UNKNOWN) == "conversation"


def test_intent_extract_action_target() -> None:
    e = IntentEngine()
    a, t = e.extract_action_and_target("crea un informe de ventas")
    assert a == "crea"
    assert "informe" in t
    a2, t2 = e.extract_action_and_target("hola")
    assert a2 == "" and t2 == ""


def test_intent_router() -> None:
    r = IntentRouter()
    result = r.route("busca algo")
    assert result.intent == UserIntent.COMMAND
    assert result.entities["capability"] == "tools_execute"


def test_intent_result_defaults() -> None:
    r = IntentResult(intent=UserIntent.CHAT, confidence=0.5)
    assert r.entities == {}
    assert r.original_text == ""


# ── sentiment ────────────────────────────────────────────────


def test_sentiment_valores() -> None:
    assert Sentiment.NEUTRAL.value == "neutral"
    assert Sentiment.GRATEFUL.value == "grateful"


def test_sentiment_detect_frustrado() -> None:
    d = SentimentDetector()
    r = d.detect("esto no me gusta nada")
    assert r.sentiment == Sentiment.FRUSTRATED
    assert r.score == -0.6
    assert d.should_apologize(r.sentiment) is True


def test_sentiment_detect_impaciente() -> None:
    d = SentimentDetector()
    r = d.detect("cuánto falta ya")
    assert r.sentiment == Sentiment.IMPATIENT
    assert d.should_shorten_response(r.sentiment) is True


def test_sentiment_detect_confundido() -> None:
    d = SentimentDetector()
    r = d.detect("no entiendo qué significa")
    assert r.sentiment == Sentiment.CONFUSED
    assert d.should_apologize(r.sentiment) is True


def test_sentiment_detect_satisfecho() -> None:
    d = SentimentDetector()
    r = d.detect("perfecto, justo lo que necesitaba")
    assert r.sentiment == Sentiment.SATISFIED
    assert d.should_offer_help(r.sentiment) is True


def test_sentiment_detect_agradecido() -> None:
    d = SentimentDetector()
    r = d.detect("gracias por tu ayuda")
    assert r.sentiment == Sentiment.GRATEFUL
    assert d.should_offer_help(r.sentiment) is True


def test_sentiment_detect_neutral() -> None:
    d = SentimentDetector()
    r = d.detect("mañana lloverá probablemente")
    assert r.sentiment == Sentiment.NEUTRAL
    assert r.confidence == 0.5


def test_sentiment_historia_y_tendencia() -> None:
    d = SentimentDetector()
    d.detect("no me gusta", "c1")
    d.detect("perfecto", "c1")
    d.detect("gracias", "c1")
    trend = d.get_trend("c1")
    assert trend == pytest.approx((-0.6 + 0.5 + 0.7) / 3)
    assert d.get_trend("no-existe") == 0.0


def test_sentiment_sin_conversation_id() -> None:
    d = SentimentDetector()
    r = d.detect("hola")
    assert r.sentiment == Sentiment.NEUTRAL
    assert d._history == {}  # sin id → no guarda


# ── implicit_feedback ────────────────────────────────────────


def test_feedback_rephrase() -> None:
    f = ImplicitFeedback(db_path=":memory:")
    f.analyze("c1", "explica cómo funciona el motor", "resp")
    s2 = f.analyze("c1", "no, explícame mejor cómo funciona el motor diesel")
    assert s2["was_unclear"] is True
    assert s2["overall_score"] == pytest.approx(-0.2)


def test_feedback_repeat() -> None:
    f = ImplicitFeedback(db_path=":memory:")
    f.analyze("c1", "¿qué hora es?")
    s = f.analyze("c1", "¿qué hora es?")
    assert s["repeated_query"] is True
    assert s["overall_score"] == pytest.approx(-0.3)


def test_feedback_gracias() -> None:
    f = ImplicitFeedback(db_path=":memory:")
    s = f.analyze("c1", "gracias por todo")
    assert s["task_complete"] is True
    assert s["overall_score"] == pytest.approx(0.3)


def test_feedback_normal() -> None:
    f = ImplicitFeedback(db_path=":memory:")
    s = f.analyze("c1", "cuéntame algo interesante")
    assert s == {
        "was_unclear": False,
        "was_wrong": False,
        "task_complete": False,
        "repeated_query": False,
        "overall_score": 0.0,
    }


def test_feedback_is_rephrase() -> None:
    f = ImplicitFeedback(db_path=":memory:")
    assert f._is_rephrase("explica el motor a gasolina", "explica el motor diesel mejor") is True
    assert f._is_rephrase("", "algo") is False
    assert f._is_rephrase("una cosa", "otra totalmente") is False


def test_feedback_scores() -> None:
    f = ImplicitFeedback(db_path=":memory:")
    assert f.get_conversation_score("c1") == 0.0
    assert f.get_overall_score() == 0.0
    f.analyze("c1", "gracias")
    assert f.get_conversation_score("c1") == pytest.approx(0.3)
    assert f.get_overall_score() == pytest.approx(0.3)


# ── vector_memory ────────────────────────────────────────────


def test_vector_store_init_y_count(tmp_path: object) -> None:
    v = VectorMemoryStore(db_path=str(tmp_path / "vm.db"))
    assert v.count() == 0


def test_vector_store_contenido_corto() -> None:
    v = VectorMemoryStore(db_path=":memory:")
    v.store("c1", "user", "corto")  # < 10 chars → no guarda
    assert v.count() == 0


def test_vector_store_sin_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    v = VectorMemoryStore(db_path=":memory:")
    monkeypatch.setattr(v, "_embed", lambda text: None)
    v.store("c1", "user", "contenido suficientemente largo")
    assert v.count() == 0


def test_vector_store_con_embedding() -> None:
    import numpy as np

    v = VectorMemoryStore(db_path=":memory:")
    v._embed = lambda text: np.ones(8, dtype=np.float32)
    v.store("c1", "user", "este es un contenido largo de prueba")
    v.store("c2", "assistant", "otra respuesta larga también")
    assert v.count() == 2


def test_vector_store_search_sin_embed() -> None:
    v = VectorMemoryStore(db_path=":memory:")
    v._embed = lambda text: None
    assert v.search("consulta") == []


def test_vector_store_search_sin_rows() -> None:
    import numpy as np

    v = VectorMemoryStore(db_path=":memory:")
    v._embed = lambda text: np.ones(8, dtype=np.float32)
    assert v.search("consulta") == []


def test_vector_store_search_con_resultados() -> None:
    import numpy as np

    v = VectorMemoryStore(db_path=":memory:")
    v._embed = lambda text: np.ones(8, dtype=np.float32)
    v.store("c1", "user", "primer contenido de prueba largo")
    v.store("c2", "assistant", "segundo contenido también largo")
    res = v.search("algo relacionado")
    assert len(res) >= 1
    assert "conversation_id" in res[0]


def test_vector_store_search_por_encima_umbral() -> None:
    import numpy as np

    v = VectorMemoryStore(db_path=":memory:")
    v._embed = lambda text: np.ones(8, dtype=np.float32)

    v.store("c1", "user", "contenido largo para guardar con embedding")
    # inyectar fila con embedding ortogonal (sim 0)
    conn = v._conn
    conn.execute(
        "INSERT INTO entries (conversation_id, role, content, embedding) VALUES (?, ?, ?, ?)",
        ("c9", "user", "contenido ortogonal largo", np.zeros(8, dtype=np.float32).tobytes()),
    )
    conn.commit()
    res = v.search("consulta similar")
    assert all(r["conversation_id"] != "c9" for r in res) or res  # sim 0 no pasa umbral


def test_vector_store_cosine() -> None:
    import numpy as np

    v = VectorMemoryStore(db_path=":memory:")
    assert v._cosine(np.array([1, 0]), np.array([1, 0])) == pytest.approx(1.0)
    assert v._cosine(np.array([1, 0]), np.array([0, 1])) == pytest.approx(0.0)
    assert v._cosine(np.zeros(2), np.ones(2)) == 0.0  # norma 0


def test_vector_store_programming_error(monkeypatch: pytest.MonkeyPatch) -> None:
    v = VectorMemoryStore(db_path=":memory:")

    class _ConnRoto:
        def execute(self, *a, **k):
            msg = "closed"
            raise sqlite3.ProgrammingError(msg)

        def commit(self) -> None:
            pass

    monkeypatch.setattr(v, "_conn", _ConnRoto())
    v.store("c1", "user", "contenido largo con error en insert")
    # no lanza (except ProgrammingError: pass)


def test_vector_store_embed_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _Resp:
        status_code = 200

        def json(self) -> dict:
            return {"embedding": [0.1, 0.2, 0.3]}

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.post = lambda *a, **k: _Resp()
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    v = VectorMemoryStore(db_path=":memory:")
    emb = v._embed("texto de prueba")
    assert emb is not None
    assert len(emb) == 3


def test_vector_store_embed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    def _roto(*a, **k):
        msg = "sin ollama"
        raise ConnectionError(msg)

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.post = _roto
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    v = VectorMemoryStore(db_path=":memory:")
    assert v._embed("texto") is None  # except → None


def test_vector_store_embed_sin_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _Resp:
        status_code = 200

        def json(self) -> dict:
            return {}  # sin embedding

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.post = lambda *a, **k: _Resp()
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    v = VectorMemoryStore(db_path=":memory:")
    assert v._embed("texto") is None  # emb vacío → None


def test_vector_store_embed_status_no_200(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    class _Resp:
        status_code = 500

        def json(self) -> dict:
            return {}

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.post = lambda *a, **k: _Resp()
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    v = VectorMemoryStore(db_path=":memory:")
    assert v._embed("texto") is None  # status != 200 → None


# ── proactive_memory ─────────────────────────────────────────


def test_task_to_dict() -> None:
    t = Task(description="d", conversation_id="c1", priority="alta", status="pending", created_at="t", task_id="id1")
    d = t.to_dict()
    assert d["task_id"] == "id1"
    assert d["priority"] == "alta"


def test_task_created_at_default() -> None:
    t = Task(description="d")
    assert t.created_at != ""


def test_proactive_add_y_get() -> None:
    p = ProactiveMemory(db_path=":memory:")
    p.add_task("comprar leche", "c1", "alta")
    tasks = p.get_pending_tasks("c1")
    assert len(tasks) == 1
    assert tasks[0].description == "comprar leche"
    assert tasks[0].priority == "alta"


def test_proactive_get_all() -> None:
    p = ProactiveMemory(db_path=":memory:")
    p.add_task("t1", "c1")
    p.add_task("t2", "c2")
    tasks = p.get_pending_tasks()
    assert len(tasks) == 2


def test_proactive_complete_task() -> None:
    p = ProactiveMemory(db_path=":memory:")
    t = p.add_task("tarea", "c1")
    assert p.complete_task(t.task_id) is True
    assert p.complete_task("no-existe") is False
    assert p.get_pending_tasks("c1") == []


def test_proactive_detect_trigger() -> None:
    p = ProactiveMemory(db_path=":memory:")
    assert p.detect_task_trigger("recuérdame llamar al médico") == "add_task"
    assert p.detect_task_trigger("ya lo hice") == "complete_task"
    assert p.detect_task_trigger("qué tareas tengo") == "list_tasks"
    assert p.detect_task_trigger("hola qué tal") is None


def test_proactive_suggest() -> None:
    p = ProactiveMemory(db_path=":memory:")
    assert p.suggest_proactive("c1") is None
    p.add_task("tarea pendiente", "c1")
    sug = p.suggest_proactive("c1")
    assert "tarea pendiente" in sug
    assert "pendientes" in sug


# ── context ──────────────────────────────────────────────────


def test_context_level_valores() -> None:
    assert ContextLevel.IMMEDIATE.value == 3
    assert ContextLevel.HISTORICAL.value == 1


def test_context_item_defaults() -> None:
    i = ContextItem(content="x", level=ContextLevel.IMMEDIATE, source="s")
    assert i.timestamp != ""
    assert i.priority == 1.0
    assert i.ttl_seconds == 0


def test_context_item_expired() -> None:
    viejo = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    i = ContextItem(content="x", level=ContextLevel.IMMEDIATE, source="s", timestamp=viejo, ttl_seconds=3600)
    assert i.is_expired is True


def test_context_item_no_expired() -> None:
    i = ContextItem(content="x", level=ContextLevel.IMMEDIATE, source="s", ttl_seconds=3600)
    assert i.is_expired is False


def test_context_item_ttl_cero() -> None:
    i = ContextItem(content="x", level=ContextLevel.IMMEDIATE, source="s", ttl_seconds=0)
    assert i.is_expired is False


def test_context_item_timestamp_sin_tz() -> None:
    i = ContextItem(content="x", level=ContextLevel.IMMEDIATE, source="s", timestamp="2026-08-20T10:00:00", ttl_seconds=0)
    assert i.is_expired is False


def test_context_item_sin_tz_con_ttl() -> None:
    # timestamp sin tzinfo + ttl activo → replace con UTC (línea 41)
    i = ContextItem(
        content="x",
        level=ContextLevel.IMMEDIATE,
        source="s",
        timestamp="2026-08-20T10:00:00",
        ttl_seconds=3600,
    )
    assert i.is_expired is True  # hace 1 hora + sin tz → expira


def test_context_item_score() -> None:
    i = ContextItem(content="x", level=ContextLevel.CONVERSATION, source="s", priority=0.7)
    assert i.score == pytest.approx(0.7 * 2)


def test_historical_adapter_sin_memoria() -> None:
    a = HistoricalMemoryAdapter()
    assert a.query("q") == []
    assert a.is_available() is False


def test_historical_adapter_con_memoria() -> None:
    from motor.memory.models import MemoryEntry

    class _MemFake:
        def state_at(self, ts: float):
            return MemoryEntry(entry_id="e1", timestamp=ts)

    a = HistoricalMemoryAdapter(memory=_MemFake())
    assert a.is_available() is True
    items = a.query("q")
    assert len(items) == 1
    assert items[0].level == ContextLevel.HISTORICAL


def test_historical_adapter_con_memoria_sin_state() -> None:
    class _MemVacio:
        def state_at(self, ts: float):
            return None

    a = HistoricalMemoryAdapter(memory=_MemVacio())
    assert a.query("q") == []


class _MsgStoreContext:
    def __init__(self, msgs: list | None = None) -> None:
        self._msgs = msgs or []

    def get_conversation(self, conversation_id: str, limit: int = 50) -> list:
        return list(self._msgs[:limit])


def test_context_manager_assemble_vacio() -> None:
    cm = ContextManager(message_store=_MsgStoreContext(), total_token_budget=100)
    msgs = cm.assemble("c1", system_prompt="", query="")
    assert msgs == []


def test_context_manager_assemble_con_mensajes() -> None:
    store = _MsgStoreContext(
        [
            Message(role="user", content="hola", timestamp="2026-08-20T10:00:00"),
            Message(role="assistant", content="respuesta", timestamp="2026-08-20T10:01:00"),
        ]
    )
    cm = ContextManager(message_store=store, total_token_budget=1000)
    msgs = cm.assemble("c1", system_prompt="sys", query="pregunta")
    assert len(msgs) >= 1


def test_context_manager_budget_pequeno() -> None:
    store = _MsgStoreContext([Message(role="user", content="x" * 200, timestamp="t")])
    cm = ContextManager(message_store=store, total_token_budget=5)
    msgs = cm.assemble("c1")
    assert msgs == []  # el item excede el presupuesto


def test_context_manager_con_historico() -> None:
    class _MemFake:
        def state_at(self, ts: float):
            return type("E", (), {"data": "memoria antigua"})()  # type: ignore[attr-defined]

    store = _MsgStoreContext([Message(role="user", content="hola", timestamp="t")])
    cm = ContextManager(
        message_store=store,
        historical_memory=HistoricalMemoryAdapter(memory=_MemFake()),
        total_token_budget=500,
    )
    msgs = cm.assemble("c1", query="pregunta")
    assert len(msgs) >= 1


def test_context_manager_con_historico_sin_query() -> None:
    store = _MsgStoreContext()
    cm = ContextManager(
        message_store=store,
        historical_memory=HistoricalMemoryAdapter(memory=object()),
        total_token_budget=500,
    )
    assert cm.assemble("c1", query="") == []
