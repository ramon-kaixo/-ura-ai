import json
import logging
import time

from motor.core.config import UraConfig
from motor.core.executor import SubprocessExecutor
from motor.core.state import VerifyResult

log = logging.getLogger("ura.guard.verifier")
_executor = SubprocessExecutor()

URL_OLLAMA = "http://localhost:11435/v1/chat/completions"
TIMEOUT_VERIFY = 3


def ejecutar_verificacion(config: UraConfig, hubo_cambios: bool = False) -> VerifyResult:
    """Ejecuta verificación post-cambio preguntando a Ollama."""
    r = VerifyResult()
    if not hubo_cambios:
        r.verdict = "no_changes"
        log.info("verifier: sin cambios, skip")
        return r
    time.sleep(TIMEOUT_VERIFY)
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
    """Prueba respuesta de Ollama local."""
    try:
        r = _executor.run(
            [
                "curl",
                "-sf",
                "-X",
                "POST",
                URL_OLLAMA,
                "-H",
                "Content-Type: application/json",
                "-d",
                '{"model":"test","messages":[{"role":"user","content":"ping"}]}',
            ],
            timeout=10,
        )
        if r.ok:
            try:
                data = json.loads(r.stdout)
                if "choices" in data:
                    return data["choices"][0]["message"]["content"][:100] if data["choices"] else "ok"
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                log.warning("test_ollama parse falló: %s", e)
        return ""
    except Exception as e:
        log.warning("test_ollama falló: %s", e)
        return ""


def _revertir_cambios():
    """Reinicia el servicio opencode para revertir cambios."""
    try:
        _executor.run(["systemctl", "restart", "opencode"], timeout=15)
    except Exception as e:
        log.error("revertir cambios falló: %s", e)
