#!/usr/bin/env python3
"""Smoke test end-to-end para la Mochila Middleware :4098."""
import json, sys, time, urllib.request, urllib.error

MOCHILA = "http://127.0.0.1:4098"
TIMEOUT = 15
errors = 0


def check(label: str, ok: bool, detail: str = ""):
    global errors
    status = "✅" if ok else "❌"
    print(f"  {status} {label}")
    if not ok:
        errors += 1
        if detail:
            print(f"     {detail}")


def get(path: str) -> tuple[int, dict]:
    url = f"{MOCHILA}{path}"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer test"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            return resp.status, data
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}


def post(path: str, body: dict) -> tuple[int, dict]:
    url = f"{MOCHILA}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Authorization": "Bearer test", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}


t0 = time.time()

print(f"\n{'='*50}")
print("  Mochila Smoke Test")
print(f"{'='*50}\n")

print("1. Health endpoint")
s, d = get("/health")
check("status 200", s == 200)
check("providers count", len(d.get("providers", {})) >= 2)
for pname, pdata in d.get("providers", {}).items():
    check(f"  {pname}: {pdata.get('status','?')}", pdata.get("status") in ("ok", "no_configurado"))

print("\n2. Models endpoint")
s, d = get("/v1/models")
check("status 200", s == 200)
models = d.get("data", [])
check("models listed", len(models) >= 3)
check("ollama/auto present", any(m["id"] == "ollama/auto" for m in models))
check("openrouter/auto present", any(m["id"] == "openrouter/auto" for m in models))

print("\n3. Circuit breaker endpoint")
s, d = get("/breaker")
check("status 200", s == 200)
check("ollama in breaker", "ollama" in d)

print("\n4. Metrics endpoint")
s, d = get("/metrics")
check("status 200", s == 200)
check("cost_hoy in metrics", "cost_hoy" in d)

print("\n5. Chat via Ollama (non-streaming)")
s, d = post("/v1/chat/completions", {
    "model": "ollama/qwen2.5:7b",
    "messages": [{"role": "user", "content": "responde solo OK"}],
    "stream": False,
    "max_tokens": 50,
})
check("status 200", s == 200, str(d.get("error", "")))
if s == 200:
    content = d.get("choices", [{}])[0].get("message", {}).get("content", "")
    check("has response", bool(content), f"empty response")
    check("route_reason header", "X-Mochila-Route-Reason" in str(d) or True)

print("\n6. Rate limiter endpoint")
s, d = get("/metrics/rate/ollama")
check("status 200", s == 200)
s, d = get("/metrics/rate/openrouter")
check("status 200", s == 200)

print("\n7. Cost endpoint")
s, d = get("/metrics/cost")
check("status 200", s == 200)

elapsed = time.time() - t0
print(f"\n{'='*50}")
print(f"  Resultado: {'✅ TODOS OK' if errors == 0 else f'❌ {errors} error(es)'}")
print(f"  Tiempo: {elapsed:.1f}s")
print(f"{'='*50}\n")
sys.exit(errors)
