"""Configuration — fuente única de configuración para el pipeline."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None  # Python <3.11

log = logging.getLogger("tuneladora.config")

_TOOL_SECTION = "tuneladora"
_TOML_KEY_MAP: dict[str, str] = {
    "review-model": "review_model",
    "llm-fallback-model": "llm_fallback_model",
    "unsafe-fixes": "unsafe_fixes",
    "strict-warnings": "strict_warnings",
    "auto-commit": "auto_commit",
    "max-snapshots": "max_snapshots",
    "timeout-ruff": "timeout_ruff",
    "timeout-llm": "timeout_llm",
    "timeout-worker": "timeout_worker",
    "timeout-script": "timeout_script",
    "sandbox-cpu-sec": "sandbox_cpu_sec",
    "sandbox-max-mem-mb": "sandbox_max_mem_mb",
    "test-target": "test_target",
    "pytest-socket-disable": "pytest_socket_disable",
    "ollama-host": "ollama_host",
    "ollama-port": "ollama_port",
    "llm-retries": "llm_retries",
    "auto-trigger-mode": "auto_trigger_mode",
    "auto-trigger-strict": "auto_trigger_strict",
}


class Configuration:
    def __init__(self) -> None:
        self.ura_root: Path = Path(os.environ.get("URA_ROOT", Path.home() / "URA" / "ura_ia_1972"))
        self.log_dir: Path = Path(os.environ.get("TUNEL_LOG_DIR", str(self.ura_root / "logs")))
        self.nervioso: Path = self.ura_root / ".nervioso"
        self.venv_python: str = str(self.ura_root / ".venv" / "bin" / "python3")
        self.ruff: str = shutil.which("ruff") or os.environ.get("TUNEL_RUFF_PATH", str(self.ura_root / ".venv" / "bin" / "ruff"))
        self.tuneladora_dir: Path = self.ura_root / ".tuneladora"

        # Ollama
        self.ollama_host: str = os.environ.get("URA_OLLAMA_HOST", "localhost")
        self.ollama_port: str = os.environ.get("URA_OLLAMA_PORT", "11434")
        self.ollama_url: str = f"http://{self.ollama_host}:{self.ollama_port}"

        # Qdrant
        self.qdrant_host: str = os.environ.get("URA_QDRANT_HOST", "localhost")
        self.qdrant_port: str = os.environ.get("URA_QDRANT_PORT", "6333")

        # Timeouts
        self.timeout_ruff: int = int(os.environ.get("TUNEL_TIMEOUT_RUFF", "300"))
        self.timeout_worker: int = int(os.environ.get("TUNEL_TIMEOUT_WORKER", "3600"))
        self.timeout_script: int = int(os.environ.get("TUNEL_TIMEOUT_SCRIPT", "120"))
        self.timeout_snapshot: int = int(os.environ.get("TUNEL_TIMEOUT_SNAPSHOT", "60"))
        self.timeout_llm: int = int(os.environ.get("TUNEL_TIMEOUT_LLM", "120"))

        # Pipeline tuning
        self.unsafe_fixes: bool = os.environ.get("TUNEL_UNSAFE_FIXES", "false").lower() == "true"
        self.strict_warnings: bool = os.environ.get("TUNEL_STRICT_WARNINGS", "false").lower() == "true"
        self.auto_commit: bool = os.environ.get("TUNEL_AUTO_COMMIT", "true").lower() == "true"
        self.max_snapshots: int = int(os.environ.get("TUNEL_MAX_SNAPSHOTS", "30"))

        # Modelos
        self.review_model: str = os.environ.get("TUNEL_REVIEW_MODEL", "qwen3:32b-q8_0")
        self.llm_fallback_model: str = os.environ.get("TUNEL_LLM_FALLBACK_MODEL", "qwen2.5-coder:14b")
        self.llm_retries: int = int(os.environ.get("TUNEL_LLM_RETRIES", "2"))

        # Sandbox
        self.pytest_socket_disable: bool = os.environ.get("TUNEL_PYTEST_SOCKET_DISABLE", "false").lower() == "true"
        self.sandbox_cpu_sec: int = int(os.environ.get("TUNEL_SANDBOX_CPU_SEC", "300"))
        self.sandbox_max_mem_mb: int = int(os.environ.get("TUNEL_SANDBOX_MAX_MEM_MB", "2048"))

        # Test target
        self.test_target: str = os.environ.get("TUNEL_TEST_TARGET", "tests/")

        # Auto-trigger
        self.auto_trigger_mode: str = os.environ.get("TUNEL_AUTO_TRIGGER_MODE", "gate")
        self.auto_trigger_strict: bool = os.environ.get("TUNEL_AUTO_TRIGGER_STRICT", "true").lower() == "true"

        # DB
        self.knowledge_db: Path = Path(
            os.environ.get("TUNEL_KNOWLEDGE_DB", str(self.ura_root / "knowledge" / "knowledge.db"))
        )
        self.episodic_db: Path = Path(
            os.environ.get("TUNEL_EPISODIC_DB", str(self.ura_root / "knowledge" / "episodic.db"))
        )
        self.ltm_db: Path = Path(
            os.environ.get("TUNEL_LTM_DB", str(self.ura_root / "knowledge" / "ltm.db"))
        )

        self._load_from_pyproject()

    def _load_from_pyproject(self) -> None:
        pyproject = self.ura_root / "pyproject.toml"
        if not pyproject.exists():
            return
        if tomllib is None:
            log.warning("tomllib not available — skipping [tool.tuneladora] from pyproject.toml")
            return
        try:
            data = tomllib.loads(pyproject.read_text())
            tool_cfg = data.get("tool", {}).get(_TOOL_SECTION, {})
            if not tool_cfg:
                return
            for toml_key, attr_name in _TOML_KEY_MAP.items():
                if toml_key not in tool_cfg:
                    continue
                val = tool_cfg[toml_key]
                current = getattr(self, attr_name, None)
                if isinstance(current, bool):
                    setattr(self, attr_name, bool(val))
                elif isinstance(current, int):
                    setattr(self, attr_name, int(val))
                elif isinstance(current, str):
                    setattr(self, attr_name, str(val))
                elif isinstance(current, Path):
                    setattr(self, attr_name, Path(val))
        except (tomllib.TOMLDecodeError, OSError, ValueError) as exc:
            log.warning("Failed to load [tool.tuneladora] from pyproject.toml: %s", exc)
        except Exception:
            log.warning("Unexpected error loading [tool.tuneladora] from pyproject.toml")

    @property
    def log_file(self) -> Path:
        return self.log_dir / "tuneladora.log"

    @property
    def sistema_map(self) -> Path:
        return self.nervioso / "sistema_map.json"

    @property
    def delta_snapshot_file(self) -> Path:
        return self.nervioso / "delta_snapshots" / "ultimo_ciclo.json"



# test desde mac sábado, 25 de julio de 2026, 20:38:48 CEST
# test 2 sábado, 25 de julio de 2026, 20:44:42 CEST
# test 3 sábado, 25 de julio de 2026, 20:46:44 CEST
# test desde mac sáb 25 jul 2026 21:05:58 CEST
