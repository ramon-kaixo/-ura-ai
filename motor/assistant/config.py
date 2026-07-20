"""Configuración del asistente conversacional vía variables de entorno."""
from __future__ import annotations

import os
from pathlib import Path


class AssistantConfig:
    def __init__(self) -> None:
        self.data_dir = os.environ.get("URA_DATA_DIR", str(Path.home() / ".ura"))
        self.db_path = os.environ.get("URA_DB_PATH", str(Path(self.data_dir) / "ura.db"))
        self.api_key = os.environ.get("URA_API_KEY", "")
        self.llm_timeout = int(os.environ.get("URA_LLM_TIMEOUT", "30"))
        self.llm_model_fast = os.environ.get("URA_LLM_MODEL_FAST", "qwen2.5:7b")
        self.llm_model_deep = os.environ.get("URA_LLM_MODEL_DEEP", "qwen3:32b-q8_0")
        self.max_message_length = int(os.environ.get("URA_MAX_MESSAGE_LENGTH", "100000"))
        self.rate_limit = int(os.environ.get("URA_RATE_LIMIT", "60"))
        self.host = os.environ.get("URA_HOST", "0.0.0.0")  # noqa: S104
        self.port = int(os.environ.get("URA_PORT", "8000"))

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key)

    def ensure_data_dir(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

    def db_for(self, name: str) -> str:
        return str(Path(self.data_dir) / f"{name}.db")


config = AssistantConfig()
