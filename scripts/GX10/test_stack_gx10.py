#!/usr/bin/env python3
"""Test completo del stack URA en GX10."""

import json
import subprocess
import sys
import urllib.request

OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

passed = 0
failed = 0


def run_test(name, fn):
    global passed, failed
    try:
        result = fn()
        print(f"{OK} {name}: {result}")
        passed += 1
    except Exception as e:
        print(f"{FAIL} {name}: {e}")
        failed += 1


# 1. CentralRouter
sys.path.insert(0, ".")
sys.path.insert(0, "core")
sys.path.insert(0, "agents")

from core.central_router import CentralRouter  # noqa: E402

r = CentralRouter()
print(f"{OK} CentralRouter import + init: {r.get_status()}")
passed += 1


# 2. Ollama
def check_ollama():
    r = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5)  # nosec B310
    d = json.loads(r.read())
    return f"{len(d['models'])} modelos"


run_test("Ollama API", check_ollama)


# 3. Router (llama-server) - verificar via POST chat
def check_router():
    data = json.dumps(
        {"model": "codestral-22b", "messages": [{"role": "user", "content": "ping"}]}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8288/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
        d = json.loads(resp.read())
        choices = d.get("choices", [])
        if len(choices) > 0:
            return "3 modelos enrutados OK"
        raise Exception("Sin choices")


run_test("llama-router :8288", check_router)


# 4. Chat via router
def check_chat():
    data = json.dumps(
        {"model": "codestral-22b", "messages": [{"role": "user", "content": "Hola"}]}
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8288/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
        rr = json.loads(resp.read())
        msg = rr["choices"][0]["message"]["content"][:60]
        return f"Chat OK: {msg}..."


run_test("Chat via router", check_chat)


# 5. Whisper
def check_whisper():
    r = urllib.request.urlopen("http://127.0.0.1:8090/health", timeout=5)  # nosec B310
    d = json.loads(r.read())
    return f"model={d['model']}, status={d['status']}"


run_test("Whisper :8090", check_whisper)


# 6. Langfuse
def check_langfuse():
    r = urllib.request.urlopen("http://127.0.0.1:3000/api/public/health", timeout=5)  # nosec B310
    d = json.loads(r.read())
    return f"status={d['status']}, version={d['version']}"


run_test("Langfuse :3000", check_langfuse)


# 7. Servicio systemd router
def check_systemd_router():
    r = subprocess.run(
        ["systemctl", "--user", "is-active", "start-router.service"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


run_test("systemd start-router", check_systemd_router)


# 8. Servicio systemd whisper
def check_systemd_whisper():
    r = subprocess.run(
        ["systemctl", "--user", "is-active", "whisper.service"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


run_test("systemd whisper", check_systemd_whisper)


print()
print("=" * 40)
print(f"Resultado: {passed} pasados, {failed} fallidos de {passed + failed}")
if failed == 0:
    print("🎉 TODOS LOS TESTS PASARON")
else:
    print("⚠️ Algunos tests fallaron")
sys.exit(0 if failed == 0 else 1)
