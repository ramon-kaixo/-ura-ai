#!/usr/bin/env python3
"""Integration Tests — URA v3.0
Flujos reales contra GX10. Condicionales: si GX10 no responde, se saltan.
"""

import json
import subprocess
import sys
import urllib.request

from core.config_manager import CONFIG

TARGET = CONFIG["ollama"]["host"]
OLLAMA_PORT = CONFIG["ollama"]["port"]
ROUTER_PORT = CONFIG["router"]["port"]
SSH_USER = CONFIG["ssh"]["user"]

PASS = 0
FAIL = 0
SKIP = 0

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"


def gx10_accessible() -> bool:
    """Verifica si GX10 es accesible vía SSH."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes",
             f"{SSH_USER}@{TARGET}", "echo ok"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def check(desc, fn) -> None:
    global PASS, FAIL
    try:
        if fn():
            PASS += 1
        else:
            FAIL += 1
    except Exception:
        FAIL += 1


def skip(desc) -> None:
    global SKIP
    SKIP += 1


def main() -> int:
    global PASS, FAIL, SKIP

    if not gx10_accessible():
        skip("SSH a GX10")
        skip("Ollama health check")
        skip("Router POST /api/chat")
        skip("SNC state file")
        skip("Health check remoto")
        return 0

    # Test 1: SSH
    check("SSH responde", gx10_accessible)

    # Test 2: Ollama
    def ollama_health():
        try:
            url = f"http://{TARGET}:{OLLAMA_PORT}/api/tags"
            req = urllib.request.Request(url)
            req.add_header("Connection", "close")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return "models" in data
        except Exception:
            return False
    check("Ollama /api/tags responde", ollama_health)

    # Test 3: Router POST
    def router_chat():
        try:
            url = f"http://{TARGET}:{ROUTER_PORT}/api/chat"
            data = json.dumps({"model": "auto", "messages": [{"role": "user", "content": "di hola"}], "stream": False}).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_data = json.loads(resp.read())
                return "message" in resp_data or "response" in resp_data
        except Exception:
            return False
    check("Router /api/chat responde con mensaje", router_chat)

    # Test 4: SNC state file
    def snc_state():
        try:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes",
                 f"{SSH_USER}@{TARGET}", "cat /tmp/ura_snc_state.json 2>/dev/null || echo '{}'"],
                capture_output=True, text=True, timeout=5,
            )
            state = json.loads(result.stdout.strip() or "{}")
            return "status" in state and "timestamp" in state
        except Exception:
            return False
    check("SNC state file existe y tiene status+timestamp", snc_state)

    # Test 5: Health check
    def health_check():
        try:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes",
                 f"{SSH_USER}@{TARGET}", "df -h / | tail -1 | awk '{print $5}'"],
                capture_output=True, text=True, timeout=5,
            )
            pct = result.stdout.strip().replace("%", "")
            return int(pct) > 0 and int(pct) < 100
        except Exception:
            return False
    check("Disco del GX10 reporta uso válido", health_check)

    if FAIL == 0:
        pass
    else:
        pass

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
