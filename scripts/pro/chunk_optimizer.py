#!/usr/bin/env python3
"""Chunk Optimizer — Ajuste dinámico de tamaño según tasa de error.

Principio:
  Si el scanner muestra que el LLM produce buen código (F821 bajo),
  AUMENTAR el chunk → más código por llamada → menos llamadas → más rápido.

  Si el scanner muestra errores,
  REDUCIR el chunk → menos código → más precisión.

Es un bucle cerrado:
  Scanner SALIDA → mide calidad → Chunk Optimizer → ajusta tamaño → siguiente ciclo

Optimización GPU:
  Target: 70-80% del contexto del modelo.
  Si el modelo acepta 32K tokens y estamos usando 8K (25%), podemos subir a 22K.
  Más tokens por llamada = GPU más ocupada = menos overhead de llamadas.

  Con 107 funciones a 5K tokens cada una:    ~22 llamadas al LLM
  Con 107 funciones a 20K tokens cada una:   ~6 llamadas al LLM
  Ahorro potencial: ~70% menos llamadas.

Uso:
  python3 chunk_optimizer.py --estado           # Ver estado actual
  python3 chunk_optimizer.py --ajustar <f821_delta> <token_delta_pct>  # Ajustar
  python3 chunk_optimizer.py --recomendar <modelo>    # Recomendar tamaño
"""

PLUGIN = {
    "name": "chunk_optimizer",
    "phase": "pre",
    "timeout": 30,
    "blocking": False,
    "needs_file": False,
}

import json
import os
import time
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("CHUNK_CONFIG", ".nervioso/chunk_config.json"))

# Model context limits (max tokens)
MODEL_CONTEXT_LIMITS = {
    "deepseek-coder:6.7b": 32768,
    "qwen2.5-coder:14b": 32768,
    "qwen2.5-coder:32b": 32768,
    "qwen2.5-coder:q8_0": 32768,
    "qwen3:32b-q8_0": 32768,
    "llama3.3:70b": 4096,
    "default": 32768,
}

# Chunk size limits (tokens)
MIN_CHUNK = 2048
MAX_CHUNK_RATIO = 0.55  # Max 70% of model context
DEFAULT_CHUNK = 8192


def cargar() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return _nuevo()


def _nuevo() -> dict:
    return {
        "version": "1.0",
        "creado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "chunk_actual": DEFAULT_CHUNK,
        "modelo": "deepseek-coder:6.7b",
        "historico": [],
    }


def guardar(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def recomendar(modelo: str = "deepseek-coder:6.7b") -> dict:
    """Devuelve el chunk recomendado según el histórico de errores."""
    data = cargar()
    max_context = MODEL_CONTEXT_LIMITS.get(modelo, 32768)
    max_chunk = int(max_context * MAX_CHUNK_RATIO)
    chunk = data.get("chunk_actual", DEFAULT_CHUNK)

    # Ajustar al modelo
    if modelo != data.get("modelo"):
        # Si cambia de modelo, resetear histórico
        data["modelo"] = modelo
        data["chunk_actual"] = DEFAULT_CHUNK
        data["historico"] = []
        chunk = DEFAULT_CHUNK

    # Asegurar dentro de límites
    chunk = max(chunk, MIN_CHUNK)
    chunk = min(chunk, max_chunk)

    # Calcular uso de GPU
    gpu_usage = round(chunk / max_context * 100, 1)

    return {
        "chunk_recomendado": chunk,
        "max_context": max_context,
        "max_chunk": max_chunk,
        "min_chunk": MIN_CHUNK,
        "gpu_usage_pct": gpu_usage,
        "target_pct": round(MAX_CHUNK_RATIO * 100),
        "modelo": modelo,
        "llamadas_estimadas": round(100000 / chunk),  # ~100K tokens totales
    }


def ajustar(f821_delta: int, token_delta_pct: float, modelo: str | None = None) -> dict:
    """Ajusta el chunk según la calidad del último refactor.

    Args:
        f821_delta: Cambio en F821 (negativo = mejora, positivo = empeora)
        token_delta_pct: Divergencia de tokens en %

    """
    data = cargar()
    if modelo:
        data["modelo"] = modelo

    chunk_actual = data.get("chunk_actual", DEFAULT_CHUNK)
    max_context = MODEL_CONTEXT_LIMITS.get(data.get("modelo", "default"), 32768)
    max_chunk = int(max_context * MAX_CHUNK_RATIO)

    # Evaluar calidad
    calidad = "buena"
    if f821_delta <= 0 and token_delta_pct <= 15:
        calidad = "buena"
    elif f821_delta <= 2 and token_delta_pct <= 30:
        calidad = "aceptable"
    elif f821_delta <= 5:
        calidad = "degradada"
    else:
        calidad = "mala"

    # Ajustar chunk con damping para evitar oscilacion
    if calidad == "buena":
        nuevo = int(chunk_actual * 1.10)  # +10% (mas conservador)
        accion = "AUMENTAR"
    elif calidad == "aceptable":
        nuevo = chunk_actual  # mantener
        accion = "MANTENER"
    elif calidad == "degradada":
        nuevo = int(chunk_actual * 0.70)  # -30%
        accion = "REDUCIR"
    else:  # mala
        nuevo = int(chunk_actual * 0.50)  # -50%
        accion = "REDUCIR_FUERTE"

    # Limitar
    nuevo = max(nuevo, MIN_CHUNK)
    nuevo = min(nuevo, max_chunk)

    data["chunk_actual"] = nuevo

    # Registrar en histórico
    data["historico"].append(
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "f821_delta": f821_delta,
            "token_delta_pct": token_delta_pct,
            "calidad": calidad,
            "accion": accion,
            "chunk_anterior": chunk_actual,
            "chunk_nuevo": nuevo,
        },
    )

    # Mantener solo últimos 20 ajustes
    if len(data["historico"]) > 20:
        data["historico"] = data["historico"][-20:]

    guardar(data)

    gpu_usage = round(nuevo / max_context * 100, 1)

    return {
        "accion": accion,
        "calidad": calidad,
        "chunk_anterior": chunk_actual,
        "chunk_nuevo": nuevo,
        "cambio_pct": round((nuevo / max(chunk_actual, 1) - 1) * 100, 1),
        "gpu_usage_pct": gpu_usage,
        "modelo": data.get("modelo"),
    }


def estado() -> dict:
    """Devuelve el estado actual y la tendencia."""
    data = cargar()
    hist = data.get("historico", [])

    # Tendencia (últimos 3 ajustes)
    ultimos = hist[-3:]
    tendencia = "estable"
    if len(ultimos) >= 2:
        tendencias = [a.get("accion", "") for a in ultimos]
        if all(t == "AUMENTAR" for t in tendencias):
            tendencia = "creciendo"
        elif all(t in ("REDUCIR", "REDUCIR_FUERTE") for t in tendencias):
            tendencia = "decreciendo"

    rec = recomendar(data.get("modelo", "deepseek-coder:6.7b"))

    return {
        **rec,
        "tendencia": tendencia,
        "ajustes_historicos": len(hist),
        "ultimo_ajuste": hist[-1] if hist else None,
    }


def scan_project() -> None:
    from pathlib import Path as _Path
    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Chunk Optimizer dinámico")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--estado", action="store_true", help="Ver estado actual")
    parser.add_argument(
        "--ajustar",
        nargs=2,
        metavar=("F821_DELTA", "TOKEN_DELTA_PCT"),
        help="Ajustar chunk según calidad (ej: --ajustar -2 10)",
    )
    parser.add_argument("--recomendar", type=str, help="Recomendar tamaño para modelo")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    if args.ajustar:
        delta = int(args.ajustar[0])
        tok_pct = float(args.ajustar[1])
        ajustar(delta, tok_pct)
        if args.json:
            pass
        else:
            pass
        return

    if args.estado or not args.ajustar:
        e = estado()
        if args.json:
            pass
        elif e["ultimo_ajuste"]:
            e["ultimo_ajuste"]


if __name__ == "__main__":
    main()
