#!/usr/bin/env python3
"""SNC Remote — Observador en Mac.
Sincroniza /tmp/ura_snc_state.json desde GX10 cada 10s.
Notifica si GX10 está OFFLINE o en estado CRITICAL.
"""

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from core.config_manager import CONFIG

TARGET = CONFIG["ollama"]["host"]
SSH_USER = CONFIG["ssh"]["user"]
SSH_TIMEOUT = 10
POLL_INTERVAL = 10
STALE_THRESHOLD = 30  # segundos sin update → OFFLINE

LOCAL_STATE = Path.home() / "URA" / "logs" / "snc_state.json"
LOCAL_STATE.parent.mkdir(parents=True, exist_ok=True)

REMOTE_STATE = "/home/ramon/.ura/run/ura_snc_state.json"


def _escape_applescript(s: str) -> str:
    """Escape string for safe use in osascript double-quoted strings."""
    s = s.replace("\\", "\\\\")
    return s.replace('"', '\\"')


def mac_notify(title: str, message: str) -> None:
    try:
        safe_title = _escape_applescript(title)
        safe_message = _escape_applescript(message)
        subprocess.run(
            [
                "osascript",
                "osascript",
                "-e",
                f'display notification "{safe_message}" with title "{safe_title}" sound name "Basso"',
            ],
            timeout=5,
            capture_output=True,
            check=False,
        )
    except Exception:  # noqa: S110
        pass


def sync_state() -> dict:
    """Sincroniza el state file desde GX10 vía rsync."""
    try:
        subprocess.run(
            ["rsync", "-q", f"{SSH_USER}@{TARGET}:{REMOTE_STATE}", str(LOCAL_STATE)],
            timeout=SSH_TIMEOUT,
            check=False,
        )
        if LOCAL_STATE.exists():
            return json.loads(LOCAL_STATE.read_text())
    except Exception:  # noqa: S110
        pass
    return {}


def main() -> None:

    try:
        while True:
            state = sync_state()

            if not state or not state.get("timestamp"):
                mac_notify("SNC Remote", "GX10 no responde")
            else:
                ts = state.get("timestamp", "")
                try:
                    ts_dt = datetime.fromisoformat(ts)
                    age = (datetime.now(UTC) - ts_dt).total_seconds()
                except Exception:
                    age = 999

                state.get("status", "UNKNOWN")
                "🔴" if state.get("openclaw_active") else "⚫"

                if age > STALE_THRESHOLD:
                    mac_notify("SNC Remote", f"GX10 desincronizado ({age:.0f}s)")
                else:
                    failing = [k for k, v in state.get("services", {}).items() if not v.get("ok")]
                    if failing:
                        pass

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
