"""Streaming orchestration for assistant responses."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class StreamEvent:
    def __init__(self, event_type: str, data: Any = None):
        self.event_type = event_type
        self.data = data

    def to_sse(self) -> str:
        payload = json.dumps({"type": self.event_type, "data": self.data}) if self.data else ""
        return f"data: {payload}\n\n"


class StreamManager:
    def __init__(self):
        self._active_streams: dict[str, bool] = {}

    def start_stream(self, stream_id: str) -> None:
        self._active_streams[stream_id] = True

    def stop_stream(self, stream_id: str) -> None:
        self._active_streams.pop(stream_id, None)

    def is_active(self, stream_id: str) -> bool:
        return self._active_streams.get(stream_id, False)

    async def stream_response(
        self,
        stream_id: str,
        response_gen: AsyncGenerator[str, None],
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        self.start_stream(stream_id)
        try:
            if tool_calls:
                yield StreamEvent("tool_calls", tool_calls).to_sse()

            full_response = ""
            async for chunk in response_gen:
                if not self.is_active(stream_id):
                    break
                full_response += chunk
                yield StreamEvent("token", chunk).to_sse()

            yield StreamEvent("done", {"full_response": full_response}).to_sse()
        finally:
            self.stop_stream(stream_id)

    def build_tool_call_event(self, tool_name: str, args: dict[str, Any], call_id: str) -> StreamEvent:
        return StreamEvent("tool_call", {"id": call_id, "name": tool_name, "arguments": args})
