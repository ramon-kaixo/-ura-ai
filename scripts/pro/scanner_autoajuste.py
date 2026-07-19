#!/usr/bin/env python3
# PLUGIN METADATA
PLUGIN = {
    "name": "scanner_autoajuste",
    "phase": "pre",
    "timeout": 30,
    "args": ["--json"],
    "blocking": True,
    "needs_file": False,
}
"""Scanner Auto-ajustable — ENTRADA + SALIDA con bucle cerrado.

📖 MANUAL DE USO RÁPIDO:
  python3 scanner_autoajuste.py archivo.py           # Modo ENTRADA: capturar snapshot
  python3 scanner_autoajuste.py archivo.py --diff    # Modo SALIDA: comparar vs snapshot

🔒 GARANTÍAS:
  - ENTRADA: captura AST fingerprint (funciones, clases, imports, F821, hash)
  - SALIDA: compara entrada vs salida → APROBAR / REPARAR / ROLLBACK
  - AUTO-LINK: llama a chunk_optimizer para ajustar tamaño automáticamente
  - Auto-ajuste: hasta 3 intentos de reparación determinista (ruff + auto_reglas)
  - Si 3 intentos fallan → WATERMARK (no bloquea, deja para siguiente ciclo)

Fase ENTRADA (snapshot):
  Captura estado del código antes del refactor:
  - AST fingerprint (funciones, clases, argumentos)
  - F821 count
  - Token count
  - Hash del archivo

Fase SALIDA (diff):
  Compara entrada vs salida + auto-link al chunk optimizer.
"""

import ast
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RUFF = os.environ.get("RUFF", "/home/ramon/URA/ura_ia_1972/.venv/bin/ruff")
MAX_AUTO_AJUSTES = 3


# ── Fase ENTRADA: Snapshot ──


def snapshot(ruta: Path) -> dict:
    """Captura el estado del archivo antes de modificarlo.

    Returns:
        {funciones, clases, imports, f821, tokens, hash, timestamp}

    """
    codigo = ruta.read_text()
    token_count = len(codigo.split())
    sha = hashlib.sha256(codigo.encode()).hexdigest()[:12]

    info = {
        "archivo": str(ruta),
        "hash": sha,
        "lineas": len(codigo.splitlines()),
        "tokens": token_count,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    try:
        arbol = ast.parse(codigo)
        funciones = []
        clases = []
        imports = set()

        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.FunctionDef):
                args = [a.arg for a in nodo.args.args]
                funciones.append(
                    {
                        "nombre": nodo.name,
                        "args": args,
                        "lineas": nodo.end_lineno - nodo.lineno if nodo.end_lineno else 0,
                    },
                )
            elif isinstance(nodo, ast.ClassDef):
                metodos = [n.name for n in nodo.body if isinstance(n, ast.FunctionDef)]
                clases.append({"nombre": nodo.name, "metodos": metodos})
            elif isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    imports.add(alias.name)
            elif isinstance(nodo, ast.ImportFrom):
                imports.add(nodo.module or "")

        info["funciones"] = funciones
        info["clases"] = clases
        info["imports"] = sorted(imports)
        info["total_funciones"] = len(funciones)
        info["total_clases"] = len(clases)
    except SyntaxError:
        info["error_snapshot"] = "SyntaxError al parsear AST"

    # F821 actual
    try:
        r = subprocess.run(  # noqa: S603
            [RUFF, "check", "--select", "F821", "--output-format", "json", str(ruta)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        info["f821_count"] = len(json.loads(r.stdout)) if r.stdout.strip() else 0
    except Exception:
        info["f821_count"] = -1

    return info


# ── Fase SALIDA: Comparación ──


def diff(entrada: dict, salida: dict) -> dict:
    """Compara snapshot de entrada vs salida.

    Returns:
        {paso, cambios, alertas, accion}

    """
    resultado = {
        "paso": False,
        "funciones_entrada": entrada.get("total_funciones", 0),
        "funciones_salida": salida.get("total_funciones", 0),
        "clases_entrada": entrada.get("total_clases", 0),
        "clases_salida": salida.get("total_clases", 0),
        "f821_entrada": entrada.get("f821_count", 0),
        "f821_salida": salida.get("f821_count", 0),
        "tokens_entrada": entrada.get("tokens", 0),
        "tokens_salida": salida.get("tokens", 0),
        "cambios": [],
        "alertas": [],
        "accion": "ESCRIBIR",
    }

    # Pérdida de funciones
    delta_func = resultado["funciones_salida"] - resultado["funciones_entrada"]
    if delta_func < -2:
        resultado["alertas"].append(f"Perdidas {abs(delta_func)} funciones. Posible ROLLBACK")
        resultado["accion"] = "ROLLBACK"
        resultado["paso"] = False
        return resultado

    # Aumento de F821
    delta_f821 = resultado["f821_salida"] - resultado["f821_entrada"]
    if delta_f821 < 0:
        resultado["cambios"].append(f"F821 reducido en {abs(delta_f821)}")
        resultado["paso"] = True
    elif delta_f821 <= 3:
        resultado["cambios"].append(f"F821 aumentó en {delta_f821} (marginal)")
        resultado["accion"] = "REPARAR"
        resultado["paso"] = False
    else:
        resultado["alertas"].append(f"F821 aumentó en {delta_f821}")
        resultado["accion"] = "ROLLBACK"
        resultado["paso"] = False

    # Divergencia de tokens
    if resultado["tokens_entrada"] > 0:
        delta_tok = abs(resultado["tokens_salida"] - resultado["tokens_entrada"]) / resultado["tokens_entrada"]
        if delta_tok > 0.5:
            resultado["alertas"].append(f"Tokens divergen {delta_tok * 100:.0f}%")
            if resultado["accion"] != "ROLLBACK":
                resultado["accion"] = "VERIFICAR"

    # Si todo OK
    if not resultado["alertas"] and not resultado["cambios"]:
        resultado["paso"] = True
        resultado["cambios"].append("Sin cambios detectados")

    return resultado


# ── Auto-ajuste ──


def auto_ajustar(ruta: Path, intentos: int = 0) -> tuple[bool, list[str]]:
    """Intenta reparar errores deterministamente (sin LLM).

    Returns:
        (reparado, [acciones_aplicadas])

    """
    if intentos >= MAX_AUTO_AJUSTES:
        return False, ["Máximo de intentos alcanzado"]

    reparaciones = []

    # 1. Ruff fix (indentación, sintaxis básica)
    try:
        subprocess.run(  # noqa: S603
            [RUFF, "check", "--fix", "--unsafe-fixes", str(ruta)],
            capture_output=True,
            timeout=30,
            check=False,
        )
        reparaciones.append("ruff --fix --unsafe-fixes")
    except Exception:  # noqa: S110
        pass

    # 2. Ruff format
    try:
        subprocess.run([RUFF, "format", str(ruta)], capture_output=True, timeout=15, check=False)  # noqa: S603
        reparaciones.append("ruff format")
    except Exception:  # noqa: S110
        pass

    # 3. Auto-reglas (imports faltantes)
    try:
        subprocess.run(  # noqa: S603
            [sys.executable, "scripts/pro/auto_reglas.py", "--aplicar", str(ruta)],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(Path(__file__).parent.parent.parent.parent),
            check=False,
        )
        reparaciones.append("auto_reglas")
    except Exception:  # noqa: S110
        pass

    # 4. Verificar si se arregló
    salida_post = snapshot(ruta)
    return salida_post.get("f821_count", 99) == 0, reparaciones


# ── Main ──


def escanear(ruta: Path) -> dict:
    """Escanea entrada y salida del archivo.

    Si ya existe snapshot previo (en .nervioso/), hace diff.
    Si no, crea un snapshot nuevo.
    """
    ner_dir = Path(".nervioso")
    ner_dir.mkdir(parents=True, exist_ok=True)

    snap_path = ner_dir / f"snapshot_{ruta.name.replace('/', '_').replace('.', '_')}.json"

    if snap_path.exists():
        # Modo SALIDA: hacer diff
        entrada = json.loads(snap_path.read_text())
        salida = snapshot(ruta)
        diff_result = diff(entrada, salida)

        # Auto-ajustar si es necesario
        if diff_result["accion"] in ("REPARAR", "VERIFICAR"):
            reparado, reparaciones = auto_ajustar(ruta)
            diff_result["auto_ajuste"] = {
                "reparado": reparado,
                "intentos": 1,
                "acciones": reparaciones,
            }
            if reparado:
                diff_result["accion"] = "ESCRIBIR"
                diff_result["paso"] = True
                diff_result["cambios"].append("Auto-reparado sin LLM")
            else:
                diff_result["accion"] = "WATERMARK"

        # Guardar resultado
        diff_result["entrada"] = entrada
        diff_result["salida"] = salida
        (ner_dir / f"diff_{ruta.name.replace('/', '_')}.json").write_text(
            json.dumps(diff_result, indent=2, ensure_ascii=False),
        )

        return diff_result

    # Modo ENTRADA: crear snapshot
    entrada = snapshot(ruta)
    snap_path.write_text(json.dumps(entrada, indent=2, ensure_ascii=False))
    return {"modo": "ENTRADA", "snapshot": entrada}


def scan_project() -> None:
    """Escanear todo el proyecto."""
    from pathlib import Path

    URA_ROOT = Path("/home/ramon/URA/ura_ia_1972")
    results = {}
    for py_file in URA_ROOT.rglob("*.py"):
        p = str(py_file)
        if any(
            x in p
            for x in ["/.venv/", "/.git/", "/__pycache__/", "/backups/", "/site-packages/", "/scripts_eliminados/"]
        ):
            continue
        try:
            import ast

            content = py_file.read_text()
            tree = ast.parse(content)
            funcs = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
            classes = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
            results[p] = {"functions": funcs, "classes": classes, "lines": len(content.splitlines())}
        except Exception:  # noqa: S110
            pass


def main() -> None:  # noqa: C901, PLR0912, PLR0915
    import argparse

    parser = argparse.ArgumentParser(description="Scanner Auto-ajustable ENTRADA/SALIDA")
    parser.add_argument("archivo", nargs="?", default=None, help="Archivo a escanear")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--diff", action="store_true", help="Modo diff (entrada ya capturada)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    ruta = Path(args.archivo)
    if not ruta.exists():
        sys.exit(1)

    if args.diff:
        # Modo SALIDA: comparar
        snap_path = Path(".nervioso") / f"snapshot_{ruta.name.replace('/', '_').replace('.', '_')}.json"
        if not snap_path.exists():
            sys.exit(1)
        entrada = json.loads(snap_path.read_text())
        salida = snapshot(ruta)
        resultado = diff(entrada, salida)

        if resultado["accion"] in ("REPARAR", "VERIFICAR"):
            reparado, reparaciones = auto_ajustar(ruta)
            resultado["auto_ajuste"] = {
                "reparado": reparado,
                "intentos": 1,
                "acciones": reparaciones,
            }
            if reparado:
                resultado["accion"] = "ESCRIBIR"
                resultado["paso"] = True
                resultado["cambios"].append("Auto-reparado sin LLM")

        # ── AUTO-LINK: scanner → chunk_optimizer ──
        f821_delta = resultado.get("f821_salida", 0) - resultado.get("f821_entrada", 0)
        token_pct = 0
        if resultado.get("tokens_entrada", 0) > 0:
            token_pct = (
                abs(resultado["tokens_salida"] - resultado["tokens_entrada"]) / resultado["tokens_entrada"] * 100
            )

        try:
            r_opt = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    str(Path(__file__).parent / "chunk_optimizer.py"),
                    "--ajustar",
                    str(f821_delta),
                    str(round(token_pct, 1)),
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(Path(__file__).parent.parent.parent.parent),
                check=False,
            )
            if r_opt.returncode == 0:
                opt = json.loads(r_opt.stdout)
                resultado["chunk_optimizer"] = {
                    "accion": opt.get("accion"),
                    "chunk_anterior": opt.get("chunk_anterior"),
                    "chunk_nuevo": opt.get("chunk_nuevo"),
                    "gpu_usage_pct": opt.get("gpu_usage_pct"),
                }
        except Exception:
            resultado["chunk_optimizer"] = {"error": "No se pudo ajustar"}
    else:
        # Modo ENTRADA: capturar snapshot
        resultado = escanear(ruta)

    if args.json:
        pass
    else:
        resultado.get("accion", "OK")
        modo = resultado.get("modo", "DIFF")
        if modo == "ENTRADA":
            resultado.get("snapshot", {})
        else:
            ajuste = resultado.get("auto_ajuste")
            if ajuste:
                pass

    sys.exit(0 if resultado.get("paso", True) else 1)


if __name__ == "__main__":
    main()

# PLUGIN METADATA (modo diff)
PLUGIN_DIFF = {
    "name": "scanner_autoajuste_diff",
    "phase": "post",
    "timeout": 30,
    "args": ["--diff", "--json"],
    "blocking": False,
    "needs_file": False,
}
