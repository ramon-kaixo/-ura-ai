#!/usr/bin/env python3
"""Ajuste Dinámico de Contexto para Refactorización.

Calcula el contexto óptimo para el LLM según el tamaño del archivo.
"""

PLUGIN = {
    "name": "ajustar_contexto",
    "phase": "refactor",
    "timeout": 15,
    "blocking": False,
    "needs_file": False,
}

import sys
from pathlib import Path

# ── Estimación de tokens (sin tiktoken, compatible 100%) ──


def estimar_tokens(texto: str) -> int:
    """Estima tokens de forma conservative (promedio: 4 chars/token)."""
    chars = len(texto)
    estimado = chars // 4
    return max(estimado, 1)


def contar_lineas_codigo(texto: str) -> int:
    return len([l for l in texto.splitlines() if l.strip() and not l.strip().startswith("#")])


def ajustar_contexto(
    tokens_reales: int,
    max_modelo: int = 100000,
    factor_colchon: float = 1.5,
    min_chunk: int = 8192,
) -> int:
    """Calcula el límite de contexto óptimo para el LLM.

    Args:
        tokens_reales: Tokens estimados del fragmento.
        max_modelo: Máximo que soporta el modelo (ej: 100K).
        factor_colchon: Espacio extra para la respuesta (1.5 = 50%).
        min_chunk: Mínimo absoluto (no bajar de aquí).

    Returns:
        Límite óptimo de tokens para enviar al LLM.

    """
    optimo = int(tokens_reales * factor_colchon)
    optimo = max(optimo, min_chunk)
    return min(optimo, max_modelo)


def analizar_archivo(ruta: Path) -> dict:
    """Analiza un archivo y devuelve metadata de contexto."""
    codigo = ruta.read_text(encoding="utf-8")
    tokens = estimar_tokens(codigo)
    lineas = contar_lineas_codigo(codigo)
    optimo = ajustar_contexto(tokens)

    return {
        "archivo": str(ruta),
        "tokens_estimados": tokens,
        "lineas_codigo": lineas,
        "contexto_optimo": optimo,
        "contexto_maximo": 100000,
        "ahorro_estimado": f"{int((1 - optimo / 100000) * 100)}%",
        "recomendacion": f"Usar num_predict={optimo} en vez de default 100K",
    }


def scan_project() -> None:
    from pathlib import Path as _Path
    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Ajuste Dinámico de Contexto")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("archivo", nargs="?", help="Archivo a analizar")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--texto", type=str, help="Texto directo (sin archivo)")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    if args.texto:
        tokens = estimar_tokens(args.texto)
        optimo = ajustar_contexto(tokens)
        resultado = {
            "tokens_estimados": tokens,
            "contexto_optimo": optimo,
            "lineas_texto": len(args.texto.splitlines()),
        }
    elif args.archivo:
        resultado = analizar_archivo(Path(args.archivo))
    else:
        parser.print_help()
        sys.exit(1)

    if args.json:
        pass
    else:
        for _k, _v in resultado.items():
            pass


if __name__ == "__main__":
    main()
