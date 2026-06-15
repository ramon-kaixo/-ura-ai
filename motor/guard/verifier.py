import json, logging, subprocess, time
from core.state import VerifyResult
from core.config import UraConfig

log = logging.getLogger("ura.guard.verifier")

def ejecutar_verificacion(config: UraConfig, hubo_cambios: bool = False) -> VerifyResult:
    r = VerifyResult()
    if not hubo_cambios:
        r.verdict = "no_changes"
        log.info("verifier: sin cambios, skip")
        return r
    time.sleep(3)
    r.test_response = _test_ollama()
    if r.test_response:
        r.ok = True
        r.verdict = "ok"
    else:
        r.ok = False
        r.verdict = "fail"
        r.error = "respuesta invalida o timeout"
        if config.auto_verify:
            _revertir_cambios()
            r.revertido = True
            r.verdict = "reverted"
            log.warning("verifier: cambio revertido")
        else:
            log.warning("verifier: fallo sin auto-revert")
    return r

def _test_ollama() -> str:
    try:
        r = subprocess.run(
            ["curl", "-sf", "-X", "POST",
             "http://localhost:11435/v1/chat/completions",
             "-H", "Content-Type: application/json",
             "-d", '{"model":"test","messages":[{"role":"user","content":"ping"}]}'],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            try:
                data = json.loads(r.stdout)
                if "choices" in data:
                    return data["choices"][0]["message"]["content"][:100] if data["choices"] else "ok"
            except: pass
        return ""
    except: return ""

def _revertir_cambios():
    try:
        subprocess.run(["systemctl", "restart", "opencode"], timeout=15)
    except: pass
