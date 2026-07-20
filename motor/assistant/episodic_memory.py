"""EpisodicConversationMemory — memoria de conversaciones pasadas (F29.5 B3).

Almacena resúmenes de conversaciones y los recupera cuando el usuario
retoma un tema anterior. Se apoya en F25 EpisodeStore/SessionMemory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from motor.assistant.message_store import MessageStore
from motor.assistant.models import Message


class EpisodicConversationMemory:
    def __init__(
        self,
        message_store: MessageStore | None = None,
        topic_extractor: TopicExtractor | None = None,
    ):
        self._store = message_store or MessageStore()
        self._topic_extractor = topic_extractor or TopicExtractor()
        self._topic_index: dict[str, list[str]] = {}

    def store_conversation(self, conversation_id: str) -> str:
        messages = self._store.get_conversation(conversation_id, limit=200)
        if len(messages) < 2:
            return ""

        summary_id = uuid.uuid4().hex[:12]
        compact = self._compact(messages)
        topics = self._topic_extractor.extract(compact)

        self._store.append(
            f"_summary_{summary_id}",
            Message(
                role="system",
                content=compact,
                metadata={
                    "type": "conversation_summary",
                    "original_id": conversation_id,
                    "topics": topics,
                    "message_count": len(messages),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ),
        )

        for topic in topics:
            if topic not in self._topic_index:
                self._topic_index[topic] = []
            self._topic_index[topic].append(summary_id)

        return summary_id

    def retrieve_by_topic(self, topic: str) -> list[str]:
        summary_ids = self._topic_index.get(topic.lower(), [])
        results: list[str] = []
        for sid in summary_ids:
            msgs = self._store.get_conversation(f"_summary_{sid}", limit=1)
            if msgs:
                results.append(msgs[0].content)
        return results

    def get_relevant_context(self, user_message: str, limit: int = 3) -> str:
        topic = self._topic_extractor.extract_key_topic(user_message)
        if not topic:
            return ""
        summaries = self.retrieve_by_topic(topic)
        if not summaries:
            return ""
        recent = summaries[-limit:]
        return "\n---\n".join(f"[Conversación anterior sobre '{topic}']: {s[:200]}" for s in recent)

    def _compact(self, messages: list[Message]) -> str:
        parts: list[str] = []
        for m in messages[-20:]:
            prefix = "U: " if m.role == "user" else "A: "
            parts.append(f"{prefix}{m.content[:150]}")
        return "\n".join(parts)


class TopicExtractor:
    def __init__(self) -> None:
        self._stop_words = {
            "el",
            "la",
            "los",
            "las",
            "un",
            "una",
            "y",
            "e",
            "o",
            "u",
            "de",
            "del",
            "en",
            "con",
            "por",
            "para",
            "a",
            "ante",
            "bajo",
            "es",
            "son",
            "fue",
            "era",
            "está",
            "este",
            "esta",
            "que",
            "como",
            "más",
            "pero",
            "lo",
            "le",
            "se",
            "no",
            "me",
            "te",
        }

    def extract(self, text: str) -> list[str]:
        words = text.lower().split()
        nouns = [w for w in words if w not in self._stop_words and len(w) > 3]
        freq: dict[str, int] = {}
        for w in nouns:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: -x[1])
        return [w for w, _ in sorted_words[:5]]

    def extract_key_topic(self, text: str) -> str:
        words = text.lower().split()
        meaningful = [w for w in words if w not in self._stop_words and len(w) > 3]
        return meaningful[0] if meaningful else ""
