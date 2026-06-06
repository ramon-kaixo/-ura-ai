#!/usr/bin/env python3
"""Model Router Enhanced - Con prompt caching, fallback system, dashboard y POWER_MODE."""

import hashlib
import http.server
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
import sys
sys.path.insert(0, '/usr/local/bin')
sys.path.insert(0, str(Path(__file__).parent.parent))
from router_rate_limiter import rate_limiter
from core.auth_layer import validate as auth_validate, require_auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

try:
    from core.config_manager import get_ollama_urls
except ImportError:
    def get_ollama_urls() -> dict[str, str]:
        return {"primary": "http://10.164.1.99:11434", "fallback": "http://localhost:11434"}

POWER_MODE: str = "AUTO"
_URLS = get_ollama_urls()


def _is_local_ip(ip: str) -> bool:
    """Detecta si una IP pertenece a la red local."""
    local_prefixes = (
        "127.", "10.", "192.168.",
        "172.16.", "172.17.", "172.18.", "172.19.",
        "172.20.", "172.21.", "172.22.", "172.23.",
        "172.24.", "172.25.", "172.26.", "172.27.",
        "172.28.", "172.29.", "172.30.", "172.31.",
    )
    return ip.startswith(local_prefixes)


def _resolve_mode_for_client(client_ip: str) -> str:
    """Devuelve TURBO o ECO según la IP del cliente y POWER_MODE actual.

    POWER_MODE=AUTO  → local=TURBO(ASUS), remoto=ECO(local)
    POWER_MODE=TURBO → siempre TURBO (override manual)
    POWER_MODE=ECO   → siempre ECO (override manual)
    """
    if POWER_MODE == "TURBO":
        return "TURBO"
    if POWER_MODE == "ECO":
        return "ECO"
    if _is_local_ip(client_ip):
        return "TURBO"
    return "ECO"


def _resolve_ollama_url() -> str:
    """Resuelve URL por defecto (usada en startup y health checks)."""
    env_url = os.environ.get("OLLAMA_URL")
    if env_url:
        log.info("OLLAMA_URL forzada por env: %s", env_url)
        return env_url
    try:
        req = urllib.request.Request(f"{_URLS['primary']}/api/tags")
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=5) as _:
            log.info("ASUS conectado: %s", _URLS["primary"])
            return _URLS["primary"]
    except Exception as e:
        log.warning("ASUS no accesible en startup: %s", e)
        return _URLS["fallback"]


OLLAMA_URL = _resolve_ollama_url()
ROUTER_PORT = 11435
DEFAULT_TIPO = "respuesta_rapida"
FALLBACK_MODEL = "qwen2.5:7b"
CACHE_TTL = 7200

MODEL_CONFIG = {
    "deepseek-coder:6.7b": {"temperature": 0.2, "top_p": 0.95, "num_predict": 8192},
    "qwen2.5-coder:14b": {"temperature": 0.0, "top_p": 0.9, "num_predict": 8192},
    "qwen2.5-coder:32b": {"temperature": 0.1, "top_p": 0.9, "num_predict": 8192},
    "qwen2.5-coder:q8_0": {"temperature": 0.1, "top_p": 0.9, "num_predict": 8192},
    "qwen2.5:7b": {"temperature": 0.3, "top_p": 0.9, "num_predict": 4096},
    "qwen3:32b-q8_0": {"temperature": 0.1, "top_p": 0.9, "num_predict": 16384},
    "qwen3:14b": {"temperature": 0.1, "top_p": 0.9, "num_predict": 8192},
    "llama3.3:70b": {"temperature": 0.2, "top_p": 0.9, "num_predict": 8192},
    "llama3.2:3b": {"temperature": 0.3, "top_p": 0.9, "num_predict": 2048},
    "llama3.2:1b": {"temperature": 0.3, "top_p": 0.9, "num_predict": 1024},
    "llama3.2-vision:11b": {"temperature": 0.2, "top_p": 0.9, "num_predict": 2048},
    "codestral:22b": {"temperature": 0.1, "top_p": 0.95, "num_predict": 8192},
}

success_rates: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"ok": 0, "total": 0}))
success_rates_lock = threading.Lock()
DEFAULT_MODEL_PARAMS = {"temperature": 0.2, "top_p": 0.9, "num_predict": 4096}

MODELO_ROUTES = {
    "razonamiento": {
        "descripcion": "Razonamiento profundo y planificacion",
        "modelos": ["qwen3:32b-q8_0", "qwen3:14b", "llama3.3:70b", "deepseek-coder:6.7b"],
        "fallback": "qwen2.5:7b",
    },
    "codigo_complejo": {
        "descripcion": "Codigo complejo, refactoring, arquitectura",
        "modelos": ["qwen2.5-coder:32b", "qwen2.5-coder:q8_0", "qwen2.5-coder:14b", "qwen3:32b-q8_0"],
        "fallback": "qwen2.5:7b",
    },
    "codigo_rapido": {
        "descripcion": "Codigo rapido, scripts, fixes",
        "modelos": ["qwen2.5:7b", "llama3.2:3b", "deepseek-coder:6.7b"],
        "fallback": "llama3.2:3b",
    },
    "respuesta_rapida": {
        "descripcion": "Respuestas rapidas, clasificacion, resumenes",
        "modelos": ["qwen2.5:7b", "llama3.2:3b", "llama3.2:1b"],
        "fallback": "llama3.2:3b",
    },
    "vision": {
        "descripcion": "Analisis de imagenes y vision",
        "modelos": ["llama3.2-vision:11b", "llava:34b", "llava:13b"],
        "fallback": "llama3.2-vision:11b",
    },
    "embeddings": {
        "descripcion": "Generacion de embeddings",
        "modelos": ["nomic-embed-text:latest", "mxbai-embed-large"],
        "fallback": "nomic-embed-text:latest",
    },
}

PATRONES_CLASIFICACION = {
    "razonamiento": ["analizar", "planificar", "disenar", "arquitectura", "estrategia", "por que", "explicar", "razonamiento", "logica", "evaluar"],
    "codigo_complejo": ["refactor", "arquitectura", "patron", "optimizar codigo", "reestructurar", "mejorar", "revisar codigo", "debug complejo"],
    "codigo_rapido": ["fix", "bug", "error", "corregir", "script", "funcion", "implementar", "crear funcion", "escribir codigo"],
    "respuesta_rapida": ["que es", "definir", "resumir", "clasificar", "listar", "explicar brevemente", "describir"],
    "vision": ["imagen", "foto", "grafico", "visual", "analizar imagen", "extraer de imagen", "ocr", "texto en imagen"],
    "embeddings": ["embedding", "vector", "similitud", "buscar", "semantico", "representacion", "codificar"],
}

_fallback_log: deque[float] = deque(maxlen=3600)
_fallback_lock = threading.Lock()
_asus_latency_ms: float = 0.0
_asus_latency_updated: float = 0.0
_asus_latency_lock = threading.Lock()


def _register_fallback() -> None:
    with _fallback_lock:
        _fallback_log.append(time.time())


def _fallback_count_last_hour() -> int:
    now = time.time()
    with _fallback_lock:
        cutoff = now - 3600
        while _fallback_log and _fallback_log[0] < cutoff:
            _fallback_log.popleft()
        return len(_fallback_log)


def _measare_asus_latency() -> float:
    try:
        t0 = time.monotonic()
        req = urllib.request.Request(f"{_URLS['primary']}/api/tags")
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=5):
            elapsed = (time.monotonic() - t0) * 1000
            return round(elapsed, 1)
    except Exception:
        return -1.0


def _update_asus_latency() -> None:
    global _asus_latency_ms, _asus_latency_updated
    ms = _measare_asus_latency()
    with _asus_latency_lock:
        _asus_latency_ms = ms
        _asus_latency_updated = time.time()


def _get_active_backend_label() -> str:
    if POWER_MODE == "TURBO":
        return "ASUS Remoto"
    if POWER_MODE == "ECO":
        return "Local Mac"
    return "AUTO (según IP)"


_CONTEXT_WARN_THRESHOLD = 12000
_CONTEXT_SUMMARY_THRESHOLD = 24000
_CHARS_PER_TOKEN = 4.0


def _estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN)


def _check_context_size(messages: list[dict] | list | str | None) -> dict[str, Any]:
    text = ""
    if isinstance(messages, str):
        text = messages
    elif isinstance(messages, list):
        text = " ".join(
            msg.get("content", "") if isinstance(msg, dict) else str(msg)
            for msg in messages
        )
    chars = len(text)
    tokens = _estimate_tokens(text)
    if tokens >= _CONTEXT_SUMMARY_THRESHOLD:
        return {"tokens": tokens, "chars": chars, "level": "critical", "message": f"Contexto muy grande ({tokens} tokens). Se recomienda resumir antes de enviar."}
    if tokens >= _CONTEXT_WARN_THRESHOLD:
        return {"tokens": tokens, "chars": chars, "level": "warn", "message": f"Contexto grande ({tokens} tokens). Considera reducir el prompt."}
    return {"tokens": tokens, "chars": chars, "level": "ok", "message": f"Contexto normal ({tokens} tokens)."}


class MetricsCollector:
    def __init__(self) -> None:
        self.metrics: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(int))
        self.metrics_history: dict[str, list[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def increment(self, metric: str, labels: dict[str, str] | None = None) -> None:
        with self.lock:
            key = self._make_key(metric, labels)
            self.metrics[key]["count"] += 1
            self.metrics[key]["last_updated"] = time.time()

    def record_latency(self, metric: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self.lock:
            key = self._make_key(metric, labels)
            self.metrics[key]["latency_sum"] += value
            self.metrics[key]["latency_count"] += 1
            self.metrics[key]["latency_avg"] = self.metrics[key]["latency_sum"] / self.metrics[key]["latency_count"]
            self.metrics_history[key].append(value)
            if len(self.metrics_history[key]) > 1000:
                self.metrics_history[key].pop(0)

    def record_error(self, metric: str, error_type: str, labels: dict[str, str] | None = None) -> None:
        with self.lock:
            key = self._make_key(metric, labels)
            self.metrics[key]["errors"] = self.metrics[key].get("errors", {})
            self.metrics[key]["errors"][error_type] = self.metrics[key]["errors"].get(error_type, 0) + 1

    def _make_key(self, metric: str, labels: dict[str, str] | None = None) -> str:
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f"{metric}{{{label_str}}}"
        return metric

    def get_prometheus_format(self) -> str:
        lines: list[str] = []
        with self.lock:
            for key, data in self.metrics.items():
                if "count" in data:
                    lines.append(f"{key}_count {data['count']}")
                if "latency_avg" in data:
                    lines.append(f"{key}_latency_avg {data['latency_avg']:.3f}")
                if "errors" in data:
                    for error_type, count in data["errors"].items():
                        lines.append(f"{key}_error_{error_type} {count}")
        return "\n".join(lines)


metrics = MetricsCollector()


class PromptCache:
    def __init__(self, ttl: int = CACHE_TTL) -> None:
        self.cache: dict[str, dict[str, Any]] = {}
        self.ttl = ttl
        self.lock = threading.Lock()

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, prompt: str, tipo: str) -> dict | None:
        key = self._hash_content(f"{tipo}:{prompt}")
        with self.lock:
            if key in self.cache:
                cached = self.cache[key]
                if time.time() - cached["timestamp"] < self.ttl:
                    metrics.increment("prompt_cache_hit", {"tipo": tipo})
                    return cached["response"]
                del self.cache[key]
        metrics.increment("prompt_cache_miss", {"tipo": tipo})
        return None

    def set(self, prompt: str, tipo: str, response: dict) -> None:
        key = self._hash_content(f"{tipo}:{prompt}")
        with self.lock:
            self.cache[key] = {"response": response, "timestamp": time.time()}

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()


prompt_cache = PromptCache()


def clasificar_peticion(messages: list) -> str:
    if not messages:
        return DEFAULT_TIPO
    texto_completo = " ".join(
        msg.get("content", "") for msg in messages if isinstance(msg.get("content"), str)
    ).lower()
    scores = dict.fromkeys(PATRONES_CLASIFICACION, 0)
    for tipo, patrones in PATRONES_CLASIFICACION.items():
        for patron in patrones:
            if patron in texto_completo:
                scores[tipo] += 1
    tipo_max = max(scores, key=scores.get)
    return tipo_max if scores[tipo_max] > 0 else DEFAULT_TIPO


def obtener_modelos_disponibles(url: str | None = None) -> set[str]:
    target = url or OLLAMA_URL
    try:
        req = urllib.request.Request(f"{target}/api/tags")
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return {m["name"] for m in data.get("models", [])}
    except Exception as e:
        log.warning("Error obteniendo modelos de %s: %s", target, e)
        return set()


def _get_model_params(model_name: str) -> dict:
    base = model_name.split(":", maxsplit=1)[0]
    for name, params in MODEL_CONFIG.items():
        if model_name == name:
            return params
        if name.startswith(base):
            return params
    return dict(DEFAULT_MODEL_PARAMS)


def _apply_model_params(data: dict, model_name: str) -> dict:
    params = _get_model_params(model_name)
    if "options" not in data:
        data["options"] = {}
    for k, v in params.items():
        if k not in data.get("options", {}):
            data["options"][k] = v
    return data


def _record_success(modelo: str, tipo: str, ok: bool) -> None:
    with success_rates_lock:
        sr = success_rates[modelo][tipo]
        sr["total"] += 1
        if ok:
            sr["ok"] += 1


def _get_success_rate(modelo: str, tipo: str) -> float:
    with success_rates_lock:
        sr = success_rates[modelo].get(tipo, {"ok": 0, "total": 0})
        if sr["total"] == 0:
            return 0.5
        return sr["ok"] / sr["total"]


def seleccionar_modelo(tipo: str, disponibles: set) -> str:
    route = MODELO_ROUTES.get(tipo, MODELO_ROUTES[DEFAULT_TIPO])
    candidatos: list[tuple[str, float]] = []
    for modelo in route["modelos"]:
        if modelo in disponibles:
            tasa = _get_success_rate(modelo, tipo)
            candidatos.append((modelo, tasa))
            continue
        base = modelo.split(":")[0]
        for d in disponibles:
            if d.startswith(base):
                tasa = _get_success_rate(d, tipo)
                candidatos.append((d, tasa))
                break
    if candidatos:
        candidatos.sort(key=lambda x: x[1], reverse=True)
        return candidatos[0][0]
    fallback = route.get("fallback", FALLBACK_MODEL)
    if fallback in disponibles:
        log.warning("Usando fallback %s para tipo %s", fallback, tipo)
        metrics.increment("model_fallback", {"tipo": tipo, "fallback_model": fallback})
        return fallback
    if disponibles:
        return next(iter(disponibles))
    return route["modelos"][-1]


def proxy_request(path: str, body: bytes | None, method: str = "POST", modelo: str = "", tipo: str = "", client_ip: str = "") -> tuple:
    global OLLAMA_URL
    resolved_mode = _resolve_mode_for_client(client_ip or "127.0.0.1")
    active_url = _URLS["primary"] if resolved_mode == "TURBO" else _URLS["fallback"]
    url = f"{active_url}{path}"
    req = urllib.request.Request(url, data=body if method == "POST" else None, method=method)
    req.add_header("Content-Type", "application/json")

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            latency = time.time() - start_time
            metrics.record_latency("ollama_request", latency)
            if modelo and tipo:
                _record_success(modelo, tipo, ok=True)
                metrics.increment("model_success", {"modelo": modelo, "tipo": tipo})
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        latency = time.time() - start_time
        metrics.record_error("ollama_request", "http_error", {"status": str(e.code)})
        if modelo and tipo:
            _record_success(modelo, tipo, ok=False)
            metrics.increment("model_error", {"modelo": modelo, "tipo": tipo})
        return e.code, {}, e.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        latency = time.time() - start_time
        if resolved_mode == "TURBO":
            log.critical("ASUS FALLIDA (%s) — cliente local sin fallback", type(e).__name__)
        else:
            log.warning("Backend local caido (%s)", type(e).__name__)
        metrics.record_error("ollama_request", type(e).__name__)
        _register_fallback()
        if modelo and tipo:
            _record_success(modelo, tipo, ok=False)
            metrics.increment("model_error", {"modelo": modelo, "tipo": tipo})
        msg = f"Backend {'ASUS' if resolved_mode == 'TURBO' else 'local'} caido: {e}"
        return 503, {}, json.dumps({"error": msg}).encode()
    except Exception as e:
        latency = time.time() - start_time
        metrics.record_error("ollama_request", type(e).__name__)
        if modelo and tipo:
            _record_success(modelo, tipo, ok=False)
            metrics.increment("model_error", {"modelo": modelo, "tipo": tipo})
        error_body = json.dumps({"error": str(e)}).encode()
        return 502, {}, error_body


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>URA Model Router — Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px}
h1{color:#58a6ff;margin-bottom:8px;font-size:1.5rem}
.sub{color:#8b949e;font-size:0.85rem;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px}
.card h2{font-size:0.85rem;text-transform:uppercase;letter-spacing:0.5px;color:#8b949e;margin-bottom:12px}
.status{display:inline-block;padding:4px 12px;border-radius:12px;font-weight:600;font-size:0.9rem}
.status-remote{background:#1f6feb22;color:#58a6ff;border:1px solid #1f6feb44}
.status-local{background:#da363322;color:#f0883e;border:1px solid #da363344}
.value{font-size:1.8rem;font-weight:700}
.value-green{color:#3fb950}
.value-yellow{color:#d29922}
.value-red{color:#f85149}
.value-blue{color:#58a6ff}
.meta{font-size:0.75rem;color:#484f58;margin-top:4px}
.power-select{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:8px 12px;font-size:0.9rem;cursor:pointer}
table{width:100%;border-collapse:collapse;font-size:0.85rem}
th,td{text-align:left;padding:6px 4px;border-bottom:1px solid #21262d}
th{color:#8b949e;font-weight:500}
</style>
</head>
<body>
<h1>URA Model Router</h1>
<div class="sub">Dashboard de inferencia — actualizando cada 5s</div>
<div class="grid">
<div class="card"><h2>Estado de Inferencia</h2>
<div><span class="status {sc}" id="backend-label">{bl}</span></div>
<div class="meta" style="margin-top:8px">{bu}</div></div>
<div class="card"><h2>Latencia ASUS</h2>
<div class="value {lc}" id="asus-latency">{al}</div>
<div class="meta" id="latency-updated">{lu}</div></div>
<div class="card"><h2>Fallbacks (ultima hora)</h2>
<div class="value {fc}" id="fallback-count">{fbc}</div>
<div class="meta">cambios a Local</div></div>
<div class="card"><h2>POWER_MODE</h2>
<select class="power-select" id="power-mode" onchange="setPowerMode(this.value)">
<option value="AUTO" {asel}>&#9889; AUTO — segun IP cliente</option>
<option value="TURBO" {tsel}>&#128293; TURBO — forzar ASUS</option>
<option value="ECO" {esel}>&#128161; ECO — forzar local</option>
</select>
<div class="meta" style="margin-top:8px">{ph}</div></div>
</div>
<div style="margin-top:16px">
<div class="card"><h2>Modelos disponibles</h2>
<table><thead><tr><th>Modelo</th><th>Uso</th></tr></thead>
<tbody id="models-tbody"></tbody></table></div></div>
<script>
async function refresh(){try{
var r=await fetch('/dashboard.json'),d=await r.json();
var l=document.getElementById('backend-label');
l.textContent=d.backend_label;
l.className='status '+(d.backend_label==='ASUS Remoto'?'status-remote':'status-local');
document.getElementById('backend-url').textContent=d.backend_url;
var le=document.getElementById('asus-latency'),lv=d.asus_latency_ms;
if(lv<0){le.textContent='N/A';le.className='value value-red'}
else if(lv>200){le.textContent=lv+' ms';le.className='value value-yellow'}
else{le.textContent=lv+' ms';le.className='value value-green'}
document.getElementById('latency-updated').textContent=d.latency_updated;
var fb=document.getElementById('fallback-count'),fv=d.fallback_count_1h;
fb.textContent=fv;fb.className='value '+(fv===0?'value-green':fv<5?'value-yellow':'value-red');
document.getElementById('models-tbody').innerHTML=d.models.map(function(m){return '<tr><td>'+m.name+'</td><td>'+m.tasks.join(', ')+'</td></tr>'}).join('');
}catch(e){console.error('Dashboard error:',e)}}
async function setPowerMode(mode){try{
await fetch('/power_mode?mode='+mode,{method:'POST'});
setTimeout(refresh,200);
}catch(e){console.error('Power mode error:',e)}}
refresh();setInterval(refresh,5000);
</script>
</body>
</html>"""


def _render_dashboard() -> str:
    _update_asus_latency()
    backend_label = _get_active_backend_label()
    fb_count = _fallback_count_last_hour()
    with _asus_latency_lock:
        lat = _asus_latency_ms
        lat_updated = time.strftime("%H:%M:%S", time.localtime(_asus_latency_updated)) if _asus_latency_updated else ""
    status_class = "status-remote" if backend_label == "ASUS Remoto" else "status-local"
    auto_sel = 'selected' if POWER_MODE.upper() == "AUTO" else ''
    turbo_sel = 'selected' if POWER_MODE.upper() == "TURBO" else ''
    eco_sel = 'selected' if POWER_MODE.upper() == "ECO" else ''
    if POWER_MODE.upper() == "AUTO":
        power_hint = "Clientes locales → ASUS | Remotos → Local"
    elif POWER_MODE.upper() == "TURBO":
        power_hint = "Toda la inferencia va a ASUS. Fallback local bloqueado."
    else:
        power_hint = "Toda la inferencia va al Mac local." 
    if lat < 0:
        latency_class = "value-red"
        asus_latency = "N/A"
        latency_updated = "ASUS no accesible"
    elif lat > 200:
        latency_class = "value-yellow"
        asus_latency = f"{lat} ms"
        latency_updated = f"alta — {lat_updated}"
    else:
        latency_class = "value-green"
        asus_latency = f"{lat} ms"
        latency_updated = lat_updated
    fallback_class = "value-green" if fb_count == 0 else "value-yellow" if fb_count < 5 else "value-red"
    return _DASHBOARD_HTML.replace("{sc}", status_class).replace("{bl}", backend_label).replace("{bu}", OLLAMA_URL).replace("{lc}", latency_class).replace("{al}", asus_latency).replace("{lu}", latency_updated).replace("{fc}", fallback_class).replace("{fbc}", str(fb_count)).replace("{asel}", auto_sel).replace("{tsel}", turbo_sel).replace("{esel}", eco_sel).replace("{ph}", power_hint)


def _dashboard_json(client_ip: str = "") -> str:
    _update_asus_latency()
    resolved_mode = _resolve_mode_for_client(client_ip or "127.0.0.1")
    backend_label = "ASUS Remoto" if resolved_mode == "TURBO" else "Local Mac" if resolved_mode == "ECO" else _get_active_backend_label()
    fb_count = _fallback_count_last_hour()
    with _asus_latency_lock:
        lat = _asus_latency_ms
        lat_updated = time.strftime("%H:%M:%S", time.localtime(_asus_latency_updated)) if _asus_latency_updated else ""
    disponibles = obtener_modelos_disponibles()
    models_info: list[dict[str, Any]] = []
    for m in sorted(disponibles)[:50]:
        tasks = [k for k, v in MODELO_ROUTES.items() if m in v["modelos"]]
        models_info.append({"name": m, "tasks": tasks or ["disponible"]})
    return json.dumps({
        "backend_label": backend_label,
        "backend_url": OLLAMA_URL,
        "power_mode": POWER_MODE.upper(),
        "asus_latency_ms": lat,
        "latency_updated": lat_updated,
        "fallback_count_1h": fb_count,
        "models": models_info,
    })


class RouterHandler(http.server.BaseHTTPRequestHandler):
    _modelos_cache: set | None = None
    _cache_ts: float = 0

    @classmethod
    def _get_modelos(cls) -> set:
        if cls._modelos_cache is None:
            cls._modelos_cache = set()
        if time.time() - cls._cache_ts > 300:
            cls._modelos_cache = obtener_modelos_disponibles()
            cls._cache_ts = time.time()
        return cls._modelos_cache

    def do_GET(self) -> None:
        if not rate_limiter.is_allowed(self.client_address[0]):
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Rate limit: 100 req/min por IP"}).encode())
            return
        if self.path in {"/api/tags", "/api/tags/"}:
            status, headers, body = proxy_request("/api/tags", None, "GET", client_ip=self.client_address[0])
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path in {"/api/version", "/"}:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "service": "model_router", "version": "2.2",
                "ollama": OLLAMA_URL, "port": ROUTER_PORT,
                "power_mode": POWER_MODE.upper(),
                "routes": {k: v["descripcion"] for k, v in MODELO_ROUTES.items()},
                "features": ["prompt_caching", "fallback_system", "metrics",
                             "adaptive_routing", "per_model_temperature",
                             "dashboard", "power_mode", "context_checker"],
            }).encode())
        elif self.path == "/health":
            if require_auth() and not auth_validate(self.headers.get("X-API-KEY")):
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Forbidden"}).encode())
                return
            disponibles = self._get_modelos()
            ollama_ok = len(disponibles) > 0
            self.send_response(200 if ollama_ok else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok" if ollama_ok else "degraded",
                "ollama": "reachable" if ollama_ok else "unreachable",
                "models_available": len(disponibles),
                "ollama_url": OLLAMA_URL,
                "power_mode": POWER_MODE.upper(),
                "cache_size": len(prompt_cache.cache),
                "metrics_enabled": True,
            }).encode())
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(metrics.get_prometheus_format().encode())
        elif self.path == "/supervisor":
            if require_auth() and not auth_validate(self.headers.get("X-API-KEY")):
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Forbidden: X-API-KEY inválido o faltante"}).encode())
                return
            supervisor_data = "{}"
            ctx = None
            sock = None
            try:
                import zmq
                ctx = zmq.Context()
                sock = ctx.socket(zmq.REQ)
                sock.setsockopt(zmq.RCVTIMEO, 3000)
                sock.connect("ipc:///tmp/ura-supervisor.ipc")
                sock.send(b"status")
                supervisor_data = sock.recv().decode()
            except Exception as e:
                log.warning(f"Error conectando a supervisor IPC: {e}")
                supervisor_data = json.dumps({"error": "supervisor no accesible"})
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                if ctx:
                    try:
                        ctx.term()
                    except Exception:
                        pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(supervisor_data.encode())
        elif self.path == "/status":
            html = "<html><head><title>URA System Status</title><meta charset='utf-8'><style>"
            html += "body{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:20px}"
            html += "h1{color:#58a6ff}.ok{color:#3fb950}.err{color:#f85149}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}"
            html += ".card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px}"
            html += ".card h3{color:#8b949e;margin:0 0 8px 0;font-size:14px;text-transform:uppercase}"
            html += "</style></head><body>"
            html += "<h1>URA System Status</h1><div class='grid'>"

            # Get tasks from IPC
            tasks_data = []
            ctx = None
            sock = None
            try:
                import zmq
                ctx = zmq.Context()
                sock = ctx.socket(zmq.REQ)
                sock.setsockopt(zmq.RCVTIMEO, 3000)
                sock.connect("ipc:///tmp/ura-supervisor.ipc")
                sock.send(b"tasks")
                tasks_data = json.loads(sock.recv())
            except Exception as e:
                log.warning(f"Error conectando a supervisor IPC (tasks): {e}")
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                if ctx:
                    try:
                        ctx.term()
                    except Exception:
                        pass

            healthy = sum(1 for t in tasks_data if not t["done"] and t.get("last_error") is None)
            html += "<div class='card'><h3>Corrutinas</h3>"
            html += f"<div style='font-size:24px;font-weight:bold;color:#58a6ff'>{healthy}/{len(tasks_data)}</div>"
            html += "<div style='margin-top:8px'>"
            for t in sorted(tasks_data, key=lambda x: x["name"]):
                ok = not t["done"] and t.get("last_error") is None
                icon = "●" if ok else "○"
                color = "#3fb950" if ok else "#f85149"
                html += f"<div style='color:{color}'>{icon} {t['name']}</div>"
            html += "</div></div>"

            html += "</div>"
            html += f"<div style='margin-top:16px;color:#484f58'>Golden Baseline v3.0 — {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC</div>"
            html += "</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        elif self.path.startswith("/dashboard") and not self.path.startswith("/dashboard.json"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_render_dashboard().encode("utf-8"))
        elif self.path == "/dashboard.json" or self.path == "/dashboard.json/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(_dashboard_json(client_ip=self.client_address[0]).encode())
        elif self.path.startswith("/api/search"):
            import urllib.parse as _up
            q = _up.parse_qs(self.path.split("?")[1] if "?" in self.path else "").get("q", [None])[0]
            if not q:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "parametro q requerido"}).encode())
                return
            try:
                from core.search_engine import search
                results = search(q)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"query": q, "results": results}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        elif self.path.startswith("/v1/"):
            status, headers, body = proxy_request(self.path, None, "GET", client_ip=self.client_address[0])
            self.send_response(status)
            self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
            self.end_headers()
            self.wfile.write(body)
        else:
            status, headers, body = proxy_request(self.path, None, "GET", client_ip=self.client_address[0])
            self.send_response(status)
            self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self) -> None:
        global POWER_MODE
        if not rate_limiter.is_allowed(self.client_address[0]):
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Rate limit: 100 req/min por IP"}).encode())
            return
        if self.path.startswith("/power_mode"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            params_str = body.decode() if body else ""
            mode = ""
            for part in params_str.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if k == "mode":
                        mode = v
            if "mode=" in self.path:
                mode = self.path.split("mode=")[-1].split("&")[0]
            if mode and mode.upper() in {"AUTO", "TURBO", "ECO"}:
                POWER_MODE = mode.upper()
                log.info("POWER_MODE cambiado a %s por dashboard", POWER_MODE)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "power_mode": POWER_MODE}).encode())
                return
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Modo invalido. Usar AUTO, TURBO o ECO."}).encode())
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        original_model = data.get("model", "")
        messages = data.get("messages", [])
        prompt = data.get("prompt", "")

        ctx = _check_context_size(messages or prompt)
        if ctx["level"] == "critical":
            log.warning("Contexto CRITICO: %s tokens — %s", ctx["tokens"], ctx["message"])
            metrics.increment("context_critical", {"tokens": str(ctx["tokens"])})

        is_chat = "/api/chat" in self.path or "/v1/chat" in self.path
        is_embed = "/api/embed" in self.path or "/v1/embed" in self.path

        if is_embed:
            tipo = "embeddings"
        elif original_model and original_model not in {"auto", "router"}:
            tipo = clasificar_peticion(messages or [{"role": "user", "content": prompt}])
            disponibles = self._get_modelos()
            if original_model in disponibles:
                selected = original_model
                log.info("[DIRECT] modelo=%s (solicitado explicitamente)", selected)
                metrics.increment("model_selection", {"tipo": tipo, "mode": "direct"})
                data["model"] = selected
                data = _apply_model_params(data, selected)
                status, headers, resp_body = proxy_request(self.path, json.dumps(data).encode(), modelo=selected, tipo=tipo, client_ip=self.client_address[0])
                self.send_response(status)
                self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
                for k in ["Transfer-Encoding"]:
                    if k in headers:
                        self.send_header(k, headers[k])
                self.end_headers()
                self.wfile.write(resp_body)
                return
            log.warning("[DIRECT] modelo %s no disponible, redirigiendo a router", original_model)
            metrics.increment("model_unavailable", {"modelo": original_model})
        else:
            content_for_classify = messages or [{"role": "user", "content": prompt}]
            tipo = clasificar_peticion(content_for_classify)

        prompt_text = prompt or (json.dumps(messages[-1]) if messages else "")
        cached = prompt_cache.get(prompt_text, tipo) if prompt_text else None
        if cached and is_chat:
            log.info("[CACHE HIT] tipo=%s", tipo)
            metrics.increment("cache_hit", {"tipo": tipo})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(cached).encode())
            return

        disponibles = self._get_modelos()
        selected = seleccionar_modelo(tipo, disponibles)
        log.info("[ROUTE] tipo=%s → modelo=%s (de %s disponibles)", tipo, selected, len(disponibles))
        metrics.increment("model_selection", {"tipo": tipo, "modelo": selected, "mode": "routed"})
        data["model"] = selected
        data = _apply_model_params(data, selected)
        new_body = json.dumps(data).encode()
        status, headers, resp_body = proxy_request(self.path, new_body, modelo=selected, tipo=tipo, client_ip=self.client_address[0])
        if status == 200 and is_chat and prompt_text:
            try:
                response_data = json.loads(resp_body)
                prompt_cache.set(prompt_text, tipo, response_data)
            except Exception:
                log.debug("No se pudo cachear respuesta")
        self.send_response(status)
        self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
        for k in ["Transfer-Encoding"]:
            if k in headers:
                self.send_header(k, headers[k])
        self.end_headers()
        self.wfile.write(resp_body)

    def log_message(self, fmt, *args) -> None:
        log.debug("%s - %s", self.client_address[0], fmt % args)


def main() -> None:
    import sys
    if "--test" in sys.argv:
        idx = sys.argv.index("--test")
        texto = " ".join(sys.argv[idx + 1:]) if idx + 1 < len(sys.argv) else "hola"
        messages = [{"role": "user", "content": texto}]
        tipo = clasificar_peticion(messages)
        disponibles = obtener_modelos_disponibles()
        modelo = seleccionar_modelo(tipo, disponibles)
        return
    if "--models" in sys.argv:
        disponibles = obtener_modelos_disponibles()
        return

    log.info("Model Router Enhanced v2.2 iniciando en puerto %s", ROUTER_PORT)
    log.info("Ollama backend: %s", OLLAMA_URL)
    log.info("POWER_MODE: AUTO (deteccion por IP cliente) — manual TURBO/ECO via 'mode'") 
    log.info("Features: Dashboard, Prompt Caching, Fallback System, Metrics, Context Checker")

    disponibles = obtener_modelos_disponibles()
    if disponibles:
        log.info("Modelos disponibles: %s", ", ".join(sorted(disponibles)))
    else:
        log.warning("Ollama no accesible en %s — se reintentara", OLLAMA_URL)

    for tipo, info in MODELO_ROUTES.items():
        modelo = seleccionar_modelo(tipo, disponibles) if disponibles else info["modelos"][0]
        fallback = info.get("fallback", "N/A")
        log.info("  %-20s → %s (fallback: %s)", tipo, modelo, fallback)

    server = http.server.HTTPServer(("127.0.0.1", ROUTER_PORT), RouterHandler)
    log.info("Escuchando en 127.0.0.1:%s", ROUTER_PORT)
    log.info("Dashboard: http://127.0.0.1:%s/dashboard", ROUTER_PORT)
    log.info("Metricas:  http://127.0.0.1:%s/metrics", ROUTER_PORT)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Detenido")
        server.server_close()


if __name__ == "__main__":
    import sys
    import urllib.parse
    main()
