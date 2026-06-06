#!/usr/bin/env python3
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path
import zmq
REPO_DIR = Path(__file__).parent.parent
BASELINE_PATH = REPO_DIR / "config" / "baseline.json"
GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; BOLD = "\033[1m"; END = "\033[0m"

def _ok(v): return f"{GREEN}✅{END}" if v else f"{RED}❌{END}"
def _val(v): return f"{YELLOW}{v}{END}"
def _service(n):
    r = subprocess.run(["systemctl", "is-active", n], capture_output=True, text=True)
    return r.stdout.strip() == "active"

def main():
    quiet = "--quiet" in sys.argv; as_json = "--json" in sys.argv
    passed = 0; failed = 0; results = []

    def check(name, ok, actual, expected, detail=""):
        nonlocal passed, failed
        results.append({"name": name, "ok": ok, "actual": actual, "expected": expected, "detail": detail})
        if ok: passed += 1
        else: failed += 1

    bl = json.loads(open(BASELINE_PATH).read())
    metrics = bl["critical_metrics"]; required = bl["required_components"]; ver = bl["version"]

    tr = subprocess.run([sys.executable, "-m", "pytest", str(REPO_DIR / "tests"), "-q", "--no-header", "--ignore="+str(REPO_DIR / "tests/test_unit.py")], capture_output=True, text=True, timeout=120)
    if tr.returncode != 0:
        print(f"\n  {RED}UNIT TESTS FAILED{END}"); sys.exit(1)

    for mod_name, mod_path in [("modules_ingest","core/modules/ingest/coordinator.py"),("modules_ai","core/modules/ai/model_broker.py"),("modules_infra","core/modules/infra/action_handler.py")]:
        ok = (REPO_DIR / mod_path).exists(); check(mod_name, ok, "exists" if ok else "missing", "exists")
    pd = REPO_DIR / "data" / "processed"
    try: pd.mkdir(parents=True,exist_ok=True); tf=pd/".write_test"; tf.write_text("ok"); tf.unlink(); check("data_processed", True, "writable", "writable")
    except Exception as e: check("data_processed", False, str(e), "writable")

    for comp in required:
        ok = _service(comp); check(f"service:{comp}", ok, "active" if ok else "inactive", "active")

    try:
        ctx = zmq.Context(); sock = ctx.socket(zmq.REQ)
        sock.setsockopt(zmq.RCVTIMEO, 5000); sock.connect("ipc:///tmp/ura-supervisor.ipc")
        sock.send(b"tasks"); tasks = json.loads(sock.recv()); sock.close(); ctx.term()
        healthy = sum(1 for t in tasks if not t["done"] and t.get("last_error") is None); total = len(tasks)
    except Exception as e:
        total, healthy = 0, 0; check("coroutines", False, f"error: {e}", f">={metrics['min_coroutines']}"); return

    check("coroutines", healthy >= metrics["min_coroutines"], f"{healthy}/{total} healthy", f">={metrics['min_coroutines']} healthy",
          detail="\n".join(f"  {'✅' if not t['done'] and t.get('last_error') is None else '❌'} {t['name']}" for t in sorted(tasks, key=lambda x: x["name"])))

    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11435/dashboard.json"), timeout=5).read())
        lat = d.get("asus_latency_ms", -1)
        check("latency", 0 <= lat <= metrics["latency_max_ms"], f"{lat}ms" if lat >= 0 else "N/A", f"<={metrics['latency_max_ms']}ms", detail=f"models={len(d.get('models',[]))} backend={d.get('backend_label','?')}")
    except Exception as e:
        check("latency", False, f"error: {e}", f"<={metrics['latency_max_ms']}ms")

    try:
        r = subprocess.run([sys.executable, str(REPO_DIR / "core/chaos_monkey.py"), "--quick"], capture_output=True, timeout=60)
        check("chaos_tests", r.returncode == 0, "passed" if r.returncode == 0 else "failed", "passed")
    except Exception:
        check("chaos_tests", False, "error", "passed")

    ok_all = failed == 0
    if as_json:
        print(json.dumps({"version": ver, "all_ok": ok_all, "passed": passed, "failed": failed, "total": len(results), "checks": results}, indent=2))
    elif not quiet:
        print(f"\n{BOLD}{'='*58}{END}\n{BOLD}  VALIDACIÓN DE BASELINE v{ver}{END}\n{BOLD}{'='*58}{END}\n")
        for c in results:
            d = f"  — {c['detail']}" if c.get("detail") else ""
            print(f"  {_ok(c['ok'])} {c['name']:30s} actual={_val(c['actual'])} esperado={_val(c['expected'])}{d}")
        print(f"\n  {'✅ BASELINE OK' if ok_all else '❌ CRITICAL_MISMATCH'} — {passed}/{len(results)} checks\n")
    sys.exit(0 if ok_all else 1)

if __name__ == "__main__":
    main()
