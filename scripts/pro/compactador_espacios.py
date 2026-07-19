#!/usr/bin/env python3
"""COMPACTADOR DE ESPACIOS - Reduce codigo Python 25-30% quitando huecos."""

import json
import sys
from pathlib import Path


def compactar(codigo: str) -> tuple:  # noqa: C901, PLR0915
    lineas = codigo.split("\n")
    compactado = []
    anchors = []
    stats = {
        "lineas_original": len(lineas),
        "comentarios": 0,
        "docstrings": 0,
        "blancos": 0,
        "espacios_extra": 0,
    }

    en_docstring = False
    delimiter_docstring = None

    for i, linea in enumerate(lineas):
        stripped = linea.strip()
        num_original = i + 1

        if en_docstring:
            if delimiter_docstring in stripped:
                en_docstring = False
            stats["docstrings"] += 1
            anchors.append({"original": num_original, "tipo": "docstring", "eliminado": True})
            continue

        if stripped.startswith(('"""', "'''")):
            count = stripped.count(stripped[:3])
            if count == 1:
                en_docstring = True
                delimiter_docstring = stripped[:3]
            stats["docstrings"] += 1
            anchors.append({"original": num_original, "tipo": "docstring", "eliminado": True})
            continue

        if stripped == "":
            stats["blancos"] += 1
            anchors.append({"original": num_original, "tipo": "blanco", "eliminado": True})
            continue

        if stripped.startswith("#"):
            stats["comentarios"] += 1
            anchors.append({"original": num_original, "tipo": "comentario", "eliminado": True})
            continue

        if "#" in stripped:
            partes = stripped.split("#")
            codigo_parte = "#".join(partes[:-1]).rstrip()
            if codigo_parte:
                indentacion = linea[: len(linea) - len(linea.lstrip())]
                nueva = indentacion + codigo_parte
                stats["comentarios"] += 1
                anchors.append(
                    {"original": num_original, "tipo": "comentario_inline", "eliminado": True},
                )
                compactado.append(nueva)
                continue
            stats["comentarios"] += 1
            anchors.append({"original": num_original, "tipo": "comentario", "eliminado": True})
            continue

        indentacion = linea[: len(linea) - len(linea.lstrip())]
        nueva_linea = indentacion + " ".join(stripped.split())

        if len(linea) - len(nueva_linea) > 0:
            stats["espacios_extra"] += 1

        compactado.append(nueva_linea)
        anchors.append(
            {
                "original": num_original,
                "compactado": len(compactado),
                "tipo": "codigo",
                "indentacion": len(indentacion),
            },
        )

    lineas_compactadas = len(compactado)
    reduccion = round((1 - lineas_compactadas / len(lineas)) * 100, 1) if lineas else 0
    stats["lineas_compactado"] = lineas_compactadas
    stats["reduccion_pct"] = reduccion

    return "\n".join(compactado), anchors, stats


def descompactar(codigo_compactado: str, anchors: list) -> str:
    lineas_compactadas = codigo_compactado.split("\n")
    lineas_originales = []
    indice_compactado = 0

    for anchor in anchors:
        if anchor["tipo"] == "codigo":
            if indice_compactado < len(lineas_compactadas):
                lineas_originales.append(lineas_compactadas[indice_compactado])
                indice_compactado += 1
            else:
                lineas_originales.append("")
        elif anchor["tipo"] in ("blanco", "comentario", "docstring", "comentario_inline"):
            lineas_originales.append("")

    return "\n".join(lineas_originales)


def compactar_archivo(ruta: Path) -> dict:
    codigo = ruta.read_text(encoding="utf-8")
    compactado, anchors, stats = compactar(codigo)

    nervioso = ruta.parent / ".nervioso"
    nervioso.mkdir(exist_ok=True)

    mapa_path = nervioso / f"{ruta.stem}_anchors.json"
    mapa_path.write_text(
        json.dumps(
            {"archivo": str(ruta), "anchors": anchors, "stats": stats},
            indent=2,
            ensure_ascii=False,
        ),
    )

    compact_path = nervioso / f"{ruta.stem}_compactado.py"
    compact_path.write_text(compactado)

    return {
        "original": str(ruta),
        "compactado": str(compact_path),
        "mapa": str(mapa_path),
        "stats": stats,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Compactador de espacios Python")
    parser.add_argument("archivo", help="Archivo a compactar")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--descompactar", action="store_true", help="Descompactar usando mapa")
    args = parser.parse_args()

    ruta = Path(args.archivo)
    if not ruta.exists():
        sys.exit(1)

    if args.descompactar:
        mapa_path = ruta.parent / ".nervioso" / f"{ruta.stem}_anchors.json"
        if not mapa_path.exists():
            sys.exit(1)
        mapa = json.loads(mapa_path.read_text())
        descompactar(ruta.read_text(), mapa["anchors"])
    else:
        resultado = compactar_archivo(ruta)
        if args.json:
            pass
        else:
            resultado["stats"]


if __name__ == "__main__":
    main()
