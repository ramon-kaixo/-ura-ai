"""Dashboard de evolución del score de mutación de URA.

Registra cada ejecución del gate en ``coverage/gremlins/history/history.jsonl``
y regenera ``docs/udo/mutation_dashboard.md`` con:
- Gráfico ASCII de evolución del score.
- Tabla de los últimos 10 resultados.
- Tendencia (mejorando/estable/empeorando).

Uso: python scripts/update_mutation_dashboard.py --total N --zapped Z
                  --survived S --timeout T --pardoned P --tiempo SEG
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HISTORIAL = RAIZ / "coverage" / "gremlins" / "history" / "history.jsonl"
DASHBOARD = RAIZ / "docs" / "udo" / "mutation_dashboard.md"


def _score(zapped: int, timeout: int, total: int, pardoned: int) -> float:
    base = max(total - pardoned, 1)
    return round(100.0 * (zapped + timeout) / base, 2)


def _grafico(puntos: list[tuple[str, float]]) -> list[str]:
    if not puntos:
        return ["(sin datos)"]
    ancho = 40
    lineas = ["```", f"{'score %':>8} | {'':<40} | fecha"]
    for fecha, score in puntos[-20:]:
        barras = max(0, min(ancho, round(score / 100 * ancho)))
        lineas.append(f"{score:>8.2f} | {'#' * barras:<40} | {fecha}")
    lineas.append("```")
    return lineas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total", type=int, required=True)
    parser.add_argument("--zapped", type=int, required=True)
    parser.add_argument("--survived", type=int, required=True)
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("--error", type=int, default=0)
    parser.add_argument("--pardoned", type=int, default=0)
    parser.add_argument("--tiempo", type=int, default=0)
    args = parser.parse_args()

    score = _score(args.zapped, args.timeout, args.total, args.pardoned)
    registro = {
        "fecha": datetime.datetime.now(tz=datetime.UTC).isoformat(timespec="seconds"),
        "total": args.total,
        "zapped": args.zapped,
        "survived": args.survived,
        "timeout": args.timeout,
        "error": args.error,
        "pardoned": args.pardoned,
        "score": score,
        "tiempo_s": args.tiempo,
    }

    HISTORIAL.parent.mkdir(parents=True, exist_ok=True)
    with HISTORIAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro) + "\n")

    historial: list[dict] = []
    if HISTORIAL.exists():
        for linea in HISTORIAL.read_text(encoding="utf-8").splitlines():
            try:
                historial.append(json.loads(linea))
            except json.JSONDecodeError:
                continue

    puntos = [(h["fecha"][:10] + " " + h["fecha"][11:16], h["score"]) for h in historial]
    tendencia = "estable"
    if len(historial) >= 2:
        delta = historial[-1]["score"] - historial[-2]["score"]
        tendencia = "MEJORANDO" if delta > 0 else ("EMPEORANDO" if delta < 0 else "estable")

    ultimos = historial[-10:]
    filas = "\n".join(
        f"| {h['fecha']} | {h['total']} | {h['zapped']} | {h['survived']} "
        f"| {h['timeout']} | {h['pardoned']} | {h['score']}% | {h.get('tiempo_s', '-')}s |"
        for h in reversed(ultimos)
    )

    contenido = f"""# Dashboard de Mutación URA

Score = (zapped + timeout) / (total - pardoned). Timeout cuenta como detectado.

## Evolución

{chr(10).join(_grafico(puntos))}

**Tendencia: {tendencia}**

## Últimos 10 resultados

| fecha | mutantes | zapped | survived | timeout | pardoned | score | tiempo |
|---|---|---|---|---|---|---|---|
{filas}
"""
    DASHBOARD.write_text(contenido, encoding="utf-8")
    print(f"Dashboard actualizado: {DASHBOARD} (score={score}%, tendencia={tendencia})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
