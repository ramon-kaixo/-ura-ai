"""Analizador automático de supervivientes de pytest-gremlins.

Lee el JSON de resultados, clasifica cada superviviente y genera un informe:
- Si la línea ya tiene pragma ``# gremlin: pardon[...]`` -> JUSTIFICADO.
- Si no -> TEST DÉBIL PROPUESTO, con esqueleto de test según el operador.
- Con ``--llm`` consulta Ollama local para redactar una PROPUESTA de test
  (nunca se aplica automáticamente: queda en el informe para revisión humana).

Uso:
    python scripts/analyze_survivors.py [--json RUTA] [--salir-md RUTA]
                                        [--fail-on-unresolved] [--llm]

Salida por defecto: docs/udo/mutation-survivors/<fecha>.md
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JSON_DEFECTO = RAIZ / "coverage" / "gremlins" / "gremlins.json"
MD_DIR = RAIZ / "docs" / "udo" / "mutation-survivors"

SUGERENCIAS = {
    "comparison": "Añadir un test en el valor límite (boundary) que distinga el operador antiguo y el nuevo.",
    "arithmetic": "Añadir un test que assertee el RESULTADO numérico exacto de la función.",
    "boolean": "Añadir un test que cubra ambas ramas de la condición booleana.",
    "return": "Añadir un test que assertee el valor retornado (no solo efectos laterales).",
    "boundary": "Añadir un test exactamente en el límite del rango.",
}


def _linea_tiene_pardon(ruta: Path, linea: int) -> bool:
    try:
        contenido = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    return any(0 <= idx < len(contenido) and "gremlin: pardon[" in contenido[idx] for idx in (linea - 1, linea - 2))


def _proposta_llm(descripcion: str, fragmento: str) -> str | None:
    """Pide a Ollama local una propuesta de test. Devuelve None si no está disponible."""
    import urllib.request

    prompt = (
        "Genera UN test pytest mínimo en español que mate este mutante.\n"
        f"Mutante: {descripcion}\nCódigo:\n{fragmento}\n"
        "Responde SOLO con el código del test."
    )
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps({"model": "qwen2.5-coder:7b", "prompt": prompt, "stream": False}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - URL local fija (Ollama)
            return json.loads(resp.read()).get("response", "").strip() or None
    except (OSError, ValueError):
        return None
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=JSON_DEFECTO)
    parser.add_argument("--salida-md", type=Path, default=None)
    parser.add_argument("--fail-on-unresolved", action="store_true")
    parser.add_argument("--llm", action="store_true", help="Propuestas de test vía Ollama local")
    args = parser.parse_args()

    if not args.json.exists():
        print(f"NO HAY RESULTADOS: {args.json}")
        return 1

    datos = json.loads(args.json.read_text(encoding="utf-8"))
    resultados = datos.get("results", [])
    supervivientes = [r for r in resultados if r.get("status") == "survived"]

    lineas_md = [
        f"# Supervivientes de mutación — {datetime.datetime.now(tz=datetime.UTC).date().isoformat()}",
        "",
        f"Total supervivientes: **{len(supervivientes)}**",
        "",
        "| fichero:línea | operador | descripción | estado | acción propuesta |",
        "|---|---|---|---|---|",
    ]
    sin_resolver = 0
    for r in supervivientes:
        ruta = RAIZ / r["file_path"]
        justificado = _linea_tiene_pardon(ruta, r["line_number"])
        if justificado:
            estado = "JUSTIFICADO (pardon)"
            accion = "Ninguna: equivalente documentado."
        else:
            estado = "TEST DÉBIL"
            accion = SUGERENCIAS.get(str(r.get("operator")), "Revisar manualmente.")
            sin_resolver += 1
            if args.llm:
                try:
                    src = ruta.read_text(encoding="utf-8").splitlines()
                    frag = "\n".join(src[max(0, r["line_number"] - 3) : r["line_number"] + 2])
                except OSError:
                    frag = "(no legible)"
                propuesta = _proposta_llm(str(r.get("description")), frag)
                if propuesta:
                    accion += f"\n\n> Propuesta LLM (REVISAR antes de aplicar):\n>\n> {propuesta[:400]}"
        lineas_md.append(
            f"| `{ruta.name}:{r['line_number']}` | {r.get('operator')} | {r.get('description')} | {estado} | {accion} |"
        )

    lineas_md.append("")
    veredicto = "TODOS RESUELTOS" if sin_resolver == 0 else f"{sin_resolver} SIN RESOLVER"
    lineas_md.append(f"Veredicto: **{veredicto}**")

    MD_DIR.mkdir(parents=True, exist_ok=True)
    salida = args.salida_md or MD_DIR / f"{datetime.datetime.now(tz=datetime.UTC).date().isoformat()}.md"
    salida.write_text("\n".join(lineas_md) + "\n", encoding="utf-8")
    print(f"Informe: {salida} — {veredicto}")
    if args.fail_on_unresolved and sin_resolver:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
