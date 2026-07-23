"""Business logic handlers for the chat API."""

from __future__ import annotations

import threading
from typing import Any

from fastapi import HTTPException

from motor.assistant.conversation import ConversationEngine
from motor.assistant.executor import ConversationalToolManager
from motor.assistant.health import get_assistant_health, init_assistant_health
from motor.assistant.llm_bridge import LLMBridge
from motor.assistant.models import ConversationMode, UserIntent
from motor.assistant.moderation import ContentModerator
from motor.assistant.style import StyleEngine

_log = __import__("logging").getLogger("ura.assistant.api")


class _EngineHolder:
    engine: ConversationEngine | None = None
    llm: LLMBridge | None = None
    lock = threading.Lock()


def get_engine() -> ConversationEngine:
    if _EngineHolder.engine is None:
        with _EngineHolder.lock:
            if _EngineHolder.engine is None:
                init_assistant_health()
                _EngineHolder.engine = ConversationEngine()
                get_assistant_health().set_healthy("memory", "loaded")
    return _EngineHolder.engine


def get_llm() -> LLMBridge:
    if _EngineHolder.llm is None:
        with _EngineHolder.lock:
            if _EngineHolder.llm is None:
                try:
                    from motor.core.llm.router import LLMRouter

                    router = LLMRouter()
                    _EngineHolder.llm = LLMBridge(get_engine(), router=router)
                except Exception:
                    _EngineHolder.llm = LLMBridge(get_engine())
                get_assistant_health().set_healthy("llm", "loaded")
    return _EngineHolder.llm


_SYSTEM_PROMPTS: dict[str, dict[str, str]] = {
    "conversacion": {
        "es": "Eres URA, un asistente conversacional inteligente. Responde de forma natural y directa, sin extenderte. Sé conciso pero completo. Habla en español.",
        "en": "You are URA, an intelligent conversational assistant. Respond naturally and directly, don't overexplain. Be concise but complete. Speak in English.",
    },
    "trabajo": {
        "es": "Eres URA, un asistente profesional. Responde de forma precisa y estructurada. Usa bullet points cuando sea apropiado. Ve al grano.",
        "en": "You are URA, a professional assistant. Respond precisely and structured. Use bullet points when appropriate. Get to the point.",
    },
    "explicacion": {
        "es": "Eres URA, un tutor experto. Explica paso a paso con ejemplos concretos. Profundiza en causas, mecanismos y consecuencias.",
        "en": "You are URA, an expert tutor. Explain step by step with concrete examples. Go deep into causes, mechanisms and consequences.",
    },
}

_style_engine = StyleEngine()
_moderator = ContentModerator()
_tool_manager = ConversationalToolManager()

_FALLBACK_REPLIES = {
    "es": "Lo siento, no puedo conectar con la IA ahora. ¿Pruebo de nuevo o preguntas otra cosa?",
    "en": "Sorry, I can't reach the AI model now. Try again or ask something else?",
}


def _hours_since_last_message(conv: Any) -> float:
    if not conv or not conv.messages:
        return 0
    try:
        from datetime import UTC, datetime

        last = conv.messages[-1].timestamp
        if last:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=UTC)
            return (datetime.now(UTC) - last_dt).total_seconds() / 3600
    except Exception:
        _log.debug("hours since last message failed", exc_info=True)
    return 0


def _get_conversation_summary(conv: Any) -> str:
    if not conv or not conv.messages:
        return ""
    msgs = conv.messages[-6:]
    topics = set()
    for m in msgs:
        words = m.content.lower().split()
        for w in words:
            if len(w) > 4 and w not in ("está", "este", "esta", "para", "como", "más", "pero"):
                topics.add(w)
    if topics:
        return "Se hablaba de: " + ", ".join(list(topics)[:5]) + "."
    return ""


def _add_context_sections(system_prompt: str, analysis: dict, lang_code: str) -> str:
    if analysis.get("sentiment_action"):
        if lang_code == "en":
            system_prompt += f" The user seems {analysis['sentiment']}. {analysis['sentiment_action']}."
        else:
            system_prompt += f" El usuario parece {analysis['sentiment']}. {analysis['sentiment_action']}."
    if analysis.get("interruption_context"):
        system_prompt += f" [Context: {analysis['interruption_context']}]"
    if analysis.get("episodic_context"):
        system_prompt += f" [Previous conversations: {analysis['episodic_context']}]"
    if analysis.get("rag_context"):
        system_prompt += f"\n[Contexto documental: {analysis['rag_context']}]"
    if analysis.get("semantic_context"):
        system_prompt += f"\n{analysis['semantic_context']}"
    system_prompt += " Al final, si es útil, sugiere 1 pregunta de seguimiento breve."
    return system_prompt


def _build_system_prompt(mode_value: str, analysis: dict, lang_code: str) -> str:
    mode_prompts = _SYSTEM_PROMPTS.get(mode_value, _SYSTEM_PROMPTS["conversacion"])
    system_prompt = mode_prompts.get(lang_code, mode_prompts["es"])

    valid_modes = ("conversacion", "trabajo", "explicacion")
    mode = ConversationMode(mode_value) if mode_value in valid_modes else ConversationMode.CONVERSATION
    user_intent = analysis.get("intent", UserIntent.CHAT)
    if not isinstance(user_intent, UserIntent):
        user_intent = UserIntent.CHAT
    style_prompt = _style_engine.build_system_prompt(mode, user_intent)
    system_prompt += " " + style_prompt
    system_prompt = _add_context_sections(system_prompt, analysis, lang_code)

    lang = analysis.get("language", "es")
    if analysis.get("language_changed"):
        system_prompt += f" El usuario cambió de idioma. Responde ahora en {lang}. Este es el nuevo idioma."

    conv = analysis.get("_conv")
    if conv and conv.state and conv.state.turn_count > 0:
        hours_since = _hours_since_last_message(conv)
        if hours_since > 2:
            summary = _get_conversation_summary(conv)
            if summary:
                ctx = f"vuelve tras {int(hours_since)}h. Tema: {summary}"
                system_prompt += f"\n[El usuario {ctx}. Saluda brevemente y retoma.]"

    system_prompt += " Si no sabes la respuesta con certeza, dímelo honestamente en vez de inventar."

    if analysis.get("relevant_corrections", 0) > 0:
        system_prompt += " Has corregido información antes. Tenlo en cuenta al responder."
    user_id = analysis.get("user_id", "")
    if user_id:
        from motor.assistant.preferences import UserPreferenceLearning

        prefs = UserPreferenceLearning().get_preferences(user_id)
        if prefs.get("preferred_length") == "short":
            system_prompt += " Responde de forma breve."
        elif prefs.get("preferred_length") == "long":
            system_prompt += " Puedes extenderte si es necesario."

    if analysis.get("proactive_suggestion"):
        system_prompt += f"\n[INFO: {analysis['proactive_suggestion']}]"

    adj = analysis.get("response_adjustments", {})
    if adj.get("apologize"):
        system_prompt += " El usuario puede estar frustrado. Discúlpate y ofrece ayuda."
    if adj.get("shorten"):
        system_prompt += " Responde de forma muy breve y directa, sin extenderte."
    if adj.get("clarify"):
        system_prompt += " Pregunta al usuario si necesita una aclaración."

    return system_prompt


def _process(
    engine: ConversationEngine, llm: LLMBridge, cid: str, message: str, mode_str: str, user_id: str = ""
) -> tuple:
    conv = engine.get_or_create(cid)
    if mode_str:
        try:
            conv.state.mode = ConversationMode(mode_str)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode_str}") from None

    analysis = engine.process_user_message(cid, message)
    intent = analysis["intent"]
    mode = analysis["mode"]
    resolved = analysis["resolved_message"]
    lang_code = analysis.get("language", "es")

    engine.add_message(cid, "user", resolved)

    analysis["_conv"] = conv
    if user_id:
        analysis["user_id"] = user_id
    system_prompt = _build_system_prompt(mode.value, analysis, lang_code)

    return intent, mode, resolved, system_prompt, conv, lang_code, analysis


def _detect_tool_name(user_message: str) -> str | None:
    msg = user_message.lower().strip()
    tool_map = {
        "status": "git_status",
        "estado": "git_status",
        "log": "git_log",
        "diff": "git_diff",
        "docker": "docker_ps",
        "contenedor": "docker_ps",
        "busca": "web_search",
        "search": "web_search",
        "python": "python",
        "codigo": "python",
        "hora": "datetime",
        "fecha": "datetime",
        "ram": "system_info",
        "memoria": "system_info",
        "cuánto es": "calculator",
        "calcula": "calculator",
        "apunta": "note_save",
        "nota": "note_save",
        "branch": "git_branch",
        "rama": "git_branch",
        "commit": "git_commit",
        "clima": "weather",
        "tiempo": "weather",
        "weather": "weather",
        "temperatura": "weather",
        "noticias": "news",
        "news": "news",
    }
    for keyword, tool in tool_map.items():
        if keyword in msg:
            return tool
    for pname, plugin in _tool_manager._plugins.items():
        for kw in plugin.keywords:
            if kw in msg:
                return pname
    return None


async def _execute_command(user_message: str, analysis: dict) -> str:
    tool = _detect_tool_name(user_message)
    if not tool:
        return ""
    result = await _tool_manager.execute(tool)
    output = result.output if result.success else result.error
    if tool == "git_status" and output:
        return _format_git_status(output)
    return output


def _format_git_status(raw: str) -> str:
    if not raw:
        return ""
    lines = raw.strip().split("\n")
    parts = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("M "):
            parts.append(f"MODIFICADO (sin commit): {stripped[2:].strip()}")
        elif stripped.startswith(" M"):
            parts.append(f"MODIFICADO en working tree: {stripped[2:].strip()}")
        elif stripped.startswith("A "):
            parts.append(f"AÑADIDO (staged): {stripped[2:].strip()}")
        elif stripped.startswith("??"):
            parts.append(f"SIN RASTREAR (untracked): {stripped[2:].strip()}")
        elif stripped.startswith("D "):
            parts.append(f"ELIMINADO: {stripped[2:].strip()}")
        elif stripped.startswith("R "):
            parts.append(f"RENOMBRADO: {stripped[2:].strip()}")
        else:
            parts.append(stripped)
    return "\n".join(parts) if parts else raw


async def _enrich_prompt(system_prompt: str, analysis: dict, engine: ConversationEngine, resolved: str) -> str:
    prompt = system_prompt
    if analysis.get("needs_web_search"):
        try:
            web_results = await engine._web.search(resolved)
            if web_results:
                prompt += f"\n[Web: {web_results[:800]!s}]\nCuando uses información de la web, cita la fuente."
        except Exception:
            _log.debug("web search failed", exc_info=True)
    try:
        if engine._rag.is_available():
            get_assistant_health().set_healthy("rag", "available")
            rag_ctx = await engine._rag.retrieve(resolved)
            if rag_ctx:
                prompt += f"\n[Contexto: {rag_ctx[:800]}]"
        else:
            get_assistant_health().set_degraded("rag", "not available")
    except Exception:
        get_assistant_health().set_unhealthy("rag", "error")
    return prompt
