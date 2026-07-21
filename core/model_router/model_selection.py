"""Selección de modelos — clasificación, configuración y selección por ruta."""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from collections import defaultdict

log = logging.getLogger(__name__)

DEFAULT_TIPO = "respuesta_rapida"
FALLBACK_MODEL = "qwen2.5:3b"

MODEL_CONFIG = {
    "deepseek-coder:6.7b": {"temperature": 0.2, "top_p": 0.95, "num_predict": 8192},
    "qwen2.5-coder:14b": {"temperature": 0.0, "top_p": 0.9, "num_predict": 8192},
    "qwen2.5-coder:14b-instruct-q8_0": {"temperature": 0.0, "top_p": 0.9, "num_predict": 8192},
    "qwen2.5-coder:32b": {"temperature": 0.1, "top_p": 0.9, "num_predict": 8192},
    "qwen2.5:3b": {"temperature": 0.3, "top_p": 0.9, "num_predict": 4096},
    "qwen3:14b": {"temperature": 0.1, "top_p": 0.9, "num_predict": 8192},
    "qwen3:32b-q8_0": {"temperature": 0.1, "top_p": 0.9, "num_predict": 16384},
    "llama3.2:3b": {"temperature": 0.3, "top_p": 0.9, "num_predict": 2048},
    "llama3:latest": {"temperature": 0.2, "top_p": 0.9, "num_predict": 4096},
    "llama3.2-vision:11b": {"temperature": 0.2, "top_p": 0.9, "num_predict": 2048},
    "llava:latest": {"temperature": 0.2, "top_p": 0.9, "num_predict": 2048},
    "codestral:22b": {"temperature": 0.1, "top_p": 0.95, "num_predict": 8192},
}

success_rates: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"ok": 0, "total": 0}))
success_rates_lock = threading.Lock()
DEFAULT_MODEL_PARAMS = {"temperature": 0.2, "top_p": 0.9, "num_predict": 4096}

MODELO_ROUTES = {
    "razonamiento": {
        "descripcion": "Razonamiento profundo y planificacion",
        "modelos": ["qwen3:32b-q8_0", "qwen3:14b", "deepseek-coder:6.7b", "llama3:latest"],
        "fallback": "qwen2.5:3b",
    },
    "codigo_complejo": {
        "descripcion": "Codigo complejo, refactoring, arquitectura",
        "modelos": ["qwen2.5-coder:32b", "qwen2.5-coder:14b-instruct-q8_0", "qwen2.5-coder:14b", "qwen3:32b-q8_0"],
        "fallback": "qwen2.5:3b",
    },
    "codigo_rapido": {
        "descripcion": "Codigo rapido, scripts, fixes",
        "modelos": ["qwen2.5-coder:14b-instruct-q8_0", "llama3.2:3b", "deepseek-coder:6.7b", "qwen2.5:3b"],
        "fallback": "llama3.2:3b",
    },
    "respuesta_rapida": {
        "descripcion": "Respuestas rapidas, clasificacion, resumenes",
        "modelos": ["qwen2.5:3b", "llama3.2:3b"],
        "fallback": "llama3.2:3b",
    },
    "vision": {
        "descripcion": "Analisis de imagenes y vision",
        "modelos": ["llama3.2-vision:11b", "llava:latest"],
        "fallback": "llava:latest",
    },
    "embeddings": {
        "descripcion": "Generacion de embeddings",
        "modelos": ["nomic-embed-text:latest", "mxbai-embed-large"],
        "fallback": "nomic-embed-text:latest",
    },
}

PATRONES_CLASIFICACION = {
    "razonamiento": [
        "analizar",
        "planificar",
        "disenar",
        "arquitectura",
        "estrategia",
        "por que",
        "explicar",
        "razonamiento",
        "logica",
        "evaluar",
    ],
    "codigo_complejo": [
        "refactor",
        "arquitectura",
        "patron",
        "optimizar codigo",
        "reestructurar",
        "mejorar",
        "revisar codigo",
        "debug complejo",
    ],
    "codigo_rapido": [
        "fix",
        "bug",
        "error",
        "corregir",
        "script",
        "funcion",
        "implementar",
        "crear funcion",
        "escribir codigo",
    ],
    "respuesta_rapida": ["que es", "definir", "resumir", "clasificar", "listar", "explicar brevemente", "describir"],
    "vision": ["imagen", "foto", "grafico", "visual", "analizar imagen", "extraer de imagen", "ocr", "texto en imagen"],
    "embeddings": ["embedding", "vector", "similitud", "buscar", "semantico", "representacion", "codificar"],
}


def clasificar_peticion(messages: list) -> str:
    if not messages:
        return DEFAULT_TIPO
    texto_completo = " ".join(msg.get("content", "") for msg in messages if isinstance(msg.get("content"), str)).lower()
    scores = dict.fromkeys(PATRONES_CLASIFICACION, 0)
    for tipo, patrones in PATRONES_CLASIFICACION.items():
        for patron in patrones:
            if patron in texto_completo:
                scores[tipo] += 1
    tipo_max = max(scores, key=scores.get)
    return tipo_max if scores[tipo_max] > 0 else DEFAULT_TIPO


def obtener_modelos_disponibles(url: str | None = None) -> set[str]:
    """Obtiene modelos disponibles desde una URL de Ollama."""
    from core.model_router.router import OLLAMA_URL

    target = url or OLLAMA_URL
    try:
        req = urllib.request.Request(f"{target}/api/tags")  # noqa: S310
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
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
        from core.model_router.metrics import metrics

        metrics.increment("model_fallback", {"tipo": tipo, "fallback_model": fallback})
        return fallback
    if disponibles:
        return next(iter(disponibles))
    log.warning("No hay modelos disponibles para tipo %s", tipo)
    return route["modelos"][0]
