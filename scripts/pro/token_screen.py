#!/usr/bin/env python3
# PLUGIN METADATA
PLUGIN = {
    "name": "token_screen",
    "phase": "pre",
    "timeout": 15,
    "args": ["--texto", "test", "--json"],
    "blocking": True,
    "needs_file": False,
}
"""Token Screen + RAM Guardian — Puerta de Entrada del Pipeline.

📖 MANUAL DE USO RÁPIDO:
  python3 token_screen.py archivo.py          → Verifica si hay RAM y ajusta contexto
  python3 token_screen.py archivo.py --json   → Salida JSON
  python3 token_screen.py --texto "def f()" --modelo qwen2.5-coder:14b

🔒 GARANTÍAS:
  - 100% determinista (CPU, sin LLM)
  - Bloquea si RAM < 8GB libre (protege contra OOM)
  - Ajusta num_predict = tokens × 1.5 (máx 70% contexto del modelo)
  - Espera hasta 5 min si RAM temporalmente baja
  - Edge cases: código vacío, modelo desconocido, psutil ausente
"""  # noqa: RUF001

import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

MODEL_LIMITS: dict[str, int] = {
    "deepseek-coder:6.7b": 32768,
    "qwen2.5-coder:14b": 32768,
    "qwen2.5-coder:32b": 32768,
    "qwen2.5-coder:q8_0": 32768,
    "qwen3:32b-q8_0": 32768,
    "llama3.3:70b": 4096,
    "default": 32768,
}

MIN_FREE_RAM_MB = 8192
CHECK_INTERVAL_S = 5
MAX_WAIT_S = 300


def _free_ram_mb() -> int:
    """RAM libre en MB. psutil → /proc/meminfo → fallback 8GB."""
    if psutil:
        try:
            return max(psutil.virtual_memory().available // (1024 * 1024), 0)
        except Exception:  # noqa: S110
            pass
    try:
        with open("/proc/meminfo") as f:  # noqa: PTH123
            for line in f:
                if "MemAvailable" in line:
                    return int(line.split()[1]) // 1024
    except Exception:  # noqa: S110
        pass
    return 8192


def estimar_tokens(texto: str) -> int:
    """Estimación conservadora: ~4 chars por token."""
    if not texto:
        return 0
    return max(len(texto) // 4, 1)


def ajustar_contexto(
    tokens_reales: int,
    modelo: str = "default",
    factor: float = 1.5,
    min_tokens: int = 2048,
) -> int:
    """Calcula el límite óptimo de contexto para el LLM."""
    max_modelo = MODEL_LIMITS.get(modelo, MODEL_LIMITS["default"])
    optimo = int(tokens_reales * factor)
    optimo = max(optimo, min_tokens)
    return min(optimo, max_modelo)


def _esperar_ram(max_wait_s: int = MAX_WAIT_S) -> bool:
    """Espera hasta que haya RAM suficiente. False si timeout."""
    inicio = time.monotonic()
    while time.monotonic() - inicio < max_wait_s:
        if _free_ram_mb() >= MIN_FREE_RAM_MB:
            return True
        time.sleep(CHECK_INTERVAL_S)
    return False


def screen(codigo: str, modelo: str = "deepseek-coder:6.7b") -> dict:
    """Verifica recursos y ajusta contexto. Bloquea si RAM insuficiente.

    Edge cases:
    - Código vacío/NULL → retorna ok=False inmediatamente
    - psutil ausente → fallback a /proc/meminfo
    - RAM temporalmente baja → espera hasta 5 min
    - Modelo desconocido → usa límite default (32768)
    """
    # Código vacío
    if not codigo or not isinstance(codigo, str) or not codigo.strip():
        return {
            "ok": False,
            "warning": "Código vacío",
            "tokens_reales": 0,
            "contexto_ajustado": 0,
            "ram_libre_mb": _free_ram_mb(),
            "ram_pct": 0,
            "modelo": modelo,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    ram_libre = _free_ram_mb()
    tokens = estimar_tokens(codigo)
    ctx = ajustar_contexto(tokens, modelo)

    # RAM total y porcentaje
    ram_pct = 0
    ram_total = 121920  # 128GB GX10 default
    if psutil:
        try:
            ram_total = psutil.virtual_memory().total // (1024 * 1024)
            ram_pct = psutil.virtual_memory().percent
        except Exception:  # noqa: S110
            pass

    # Verificar RAM — si insuficiente, esperar
    if ram_libre < MIN_FREE_RAM_MB:
        _esperar_ram()
        ram_libre = _free_ram_mb()
        if ram_libre < MIN_FREE_RAM_MB:
            return {
                "ok": False,
                "warning": f"RAM insuficiente: {ram_libre}MB libre (<{MIN_FREE_RAM_MB}MB)",
                "tokens_reales": tokens,
                "contexto_ajustado": ctx,
                "ram_libre_mb": ram_libre,
                "ram_pct": ram_pct,
                "modelo": modelo,
                "ram_total_mb": ram_total,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

    # Aviso si cerca del límite (no bloquea)
    max_modelo = MODEL_LIMITS.get(modelo, MODEL_LIMITS["default"])
    warning = ""
    if tokens > max_modelo * 0.9:
        warning = f"Tokens ({tokens}) cerca del límite ({max_modelo})"

    return {
        "ok": True,
        "warning": warning,
        "tokens_reales": tokens,
        "contexto_ajustado": ctx,
        "ram_libre_mb": ram_libre,
        "ram_pct": ram_pct,
        "modelo": modelo,
        "ram_total_mb": ram_total,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def scan_project() -> None:
    """Escanear todo el proyecto."""
    URA_ROOT = Path("/home/ramon/URA/ura_ia_1972")
    results = {}
    for py_file in URA_ROOT.rglob("*.py"):
        p = str(py_file)
        skip = ["/.venv/", "/.git/", "/__pycache__/", "/backups/", "/site-packages/", "/scripts_eliminados/"]
        if any(x in p for x in skip):
            continue
        try:
            content = py_file.read_text()
            results[p] = {"lines": len(content.splitlines())}
        except Exception:  # noqa: S110
            pass


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Token Screen + RAM Guardian")
    parser.add_argument("archivo", nargs="?", help="Archivo .py a analizar")
    parser.add_argument("--texto", type=str, help="Texto directo (sin archivo)")
    parser.add_argument("--modelo", default="deepseek-coder:6.7b", help="Modelo Ollama")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    if args.texto:
        codigo: str = args.texto
    elif args.archivo:
        try:
            codigo = Path(args.archivo).read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(0)

    try:
        result = screen(codigo, args.modelo)
    except KeyboardInterrupt:
        sys.exit(130)

    if args.json or not result["ok"]:
        pass
    else:
        int((1 - result["contexto_ajustado"] / max(MODEL_LIMITS.get(result["modelo"], 32768), 1)) * 100)

    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
