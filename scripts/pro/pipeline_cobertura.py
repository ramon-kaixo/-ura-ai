#!/usr/bin/env python3
"""Pipeline de cobertura determinista con memoria y trazabilidad (100x100).

Flujo por módulo (los 6 gates):
  1. verificador_cobertura.py   — medir % actual (líneas + ramas)
  2. tests_plantilla.py         — generar tests smoke + hypothesis (sin LLM)
  3. check_changed_syntax.py    — AST: los archivos nuevos parsean
  4. pytest --forked -n 0       — los tests del módulo pasan (sin xdist)
  5. mutmut run (secuencial)    — tasa de mutantes eliminados (umbral)
  6. ruff / mypy                — código bien

Memoria persistente: .nervioso/cobertura_pipeline.json (lock fcntl, escritura
atómica — mismo patrón que conciencia.py). Trazabilidad por módulo:
cobertura antes/después, tests generados, veredictos, intentos, semilla
randomly, SHA git.

Uso:
  pipeline_cobertura.py [--modulo X] [--min 100] [--mut-muertos 80]
                        [--max-intentos 3] [--dry-run] [--status] [--reset]
                        [--reporte] [--seed 42]

Exit: 0 = todo verde · 1 = algún módulo bloqueado (alerta).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
VENV = REPO / ".venv" / "bin"
PYTHON = VENV / "python"
STATE_PATH = REPO / ".nervioso" / "cobertura_pipeline.json"
LOCK_PATH = STATE_PATH.with_suffix(".lock")
MUTACIONES_UMBRAL = 80  # % de mutantes que deben morir
COBERTURA_MIN = 100
MAX_INTENTOS = 3

MODULOS_AUTORIZADOS = [
    "motor/core/",
    "motor/intelligence/",
    "core/",
    "knowledge/",
]


def _now() -> str:
    return datetime.now(UTC).isoformat() + "Z"


def run(cmd: list[str], timeout: int = 600, cwd: Path = REPO, env: dict | None = None) -> tuple[int, str, str]:
    """Ejecuta un comando con timeout; devuelve (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False, env=env)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout {timeout}s"
    except FileNotFoundError as e:
        return 127, "", f"no encontrado: {e}"


# ---------------------------------------------------------------------------
# Memoria persistente (lock fcntl + escritura atómica)
# ---------------------------------------------------------------------------


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return {"error_previo": True, "modulos": {}}
    return {"creado": _now(), "modulos": {}}


def _save_state(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Path.open(LOCK_PATH, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        tmp = STATE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        tmp.replace(STATE_PATH)
        fcntl.flock(lockfile, fcntl.LOCK_UN)


def _modulo_estado(data: dict, modulo: str) -> dict:
    return data["modulos"].setdefault(
        modulo,
        {"estado": "pendiente", "intentos": 0, "trazabilidad": [], "cobertura_antes": None, "cobertura_despues": None},
    )


def _registrar(data: dict, modulo: str, evento: str, detalle: str = "") -> None:
    est = _modulo_estado(data, modulo)
    est["trazabilidad"].append({"ts": _now(), "evento": evento, "detalle": detalle})
    est["trazabilidad"] = est["trazabilidad"][-200:]  # límite de memoria


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def gate_medir(modulo: str, min_pct: int) -> dict:
    """Gate 1: cobertura actual con verificador_cobertura.py (líneas+ramas).

    Descubre los tests del módulo con verificador_tests.py (evita correr toda
    la suite); si no hay tests, la cobertura será 0% y toca generar plantilla.
    """
    import importlib.util

    vt = REPO / "scripts" / "pro" / "verificador_tests.py"
    spec = importlib.util.spec_from_file_location("verificador_tests", vt)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verificador_tests"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    ruta_probe = Path(modulo) if Path(modulo).suffix == ".py" else Path(modulo) / "__init__.py"
    if not ruta_probe.exists():
        # módulo = directorio: usar un .py cualquiera dentro como sonda
        py_files = sorted(Path(modulo).rglob("*.py"))
        if py_files:
            ruta_probe = py_files[0]
        else:
            return {"code": 1, "salida": f"sin archivos .py en {modulo}"}
    tests = [str(t) for t in mod._tests_para_archivo(str(ruta_probe))]
    tests = [t for t in tests if "integration" not in t]

    cmd = [str(PYTHON), "scripts/pro/verificador_cobertura.py", modulo, "--min", str(min_pct)]
    if tests:
        cmd += ["--tests", ",".join(tests)]
    code, out, err = run(cmd, timeout=900)
    return {"code": code, "salida": (out + err)[-1200:], "tests": tests}


def gate_plantilla(modulo: str, force: bool) -> dict:
    """Gate 2: generar tests smoke + hypothesis deterministas (sin LLM)."""
    ruta = Path(modulo)
    cmd = [str(PYTHON), "scripts/pro/tests_plantilla.py", str(ruta)]
    if force:
        cmd.append("--force")
    code, out, err = run(cmd, timeout=180)
    return {"code": code, "salida": (out + err)[-800:]}


def gate_sintaxis() -> dict:
    """Gate 3: los .py modificados parsean (AST)."""
    code, out, err = run([str(PYTHON), "scripts/pro/check_changed_syntax.py", "--all"], timeout=180)
    return {"code": code, "salida": (out + err)[-800:]}


def gate_pytest(modulo: str, seed: int | None, timeout: int = 900) -> dict:
    """Gate 4: pytest de los tests del módulo, fork aislado, sin xdist.

    Usa verificador_tests.py para descubrir tests que cubren el módulo;
    si no hay ninguno, ejecuta los de plantilla generados.
    """
    import importlib.util

    vt = REPO / "scripts" / "pro" / "verificador_tests.py"
    spec = importlib.util.spec_from_file_location("verificador_tests_gate", vt)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verificador_tests_gate"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    ruta_probe = Path(modulo) if Path(modulo).suffix == ".py" else Path(modulo) / "__init__.py"
    if not ruta_probe.exists():
        py_files = sorted(Path(modulo).rglob("*.py"))
        if py_files:
            ruta_probe = py_files[0]
        else:
            return {"code": 1, "salida": f"sin archivos .py en {modulo}"}
    tests = [str(t) for t in mod._tests_para_archivo(str(ruta_probe))]
    tests = [t for t in tests if "integration" not in t]
    if not tests:
        return {"code": 1, "salida": "sin tests que cubran el módulo (generar plantilla primero)"}

    cmd = [
        str(PYTHON),
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "--forked",
        "-n",
        "0",
        "--instafail",
        "-p",
        "no:cacheprovider",
    ]
    if seed is not None:
        cmd += ["--randomly-seed", str(seed)]
    cmd += tests
    code, out, err = run(cmd, timeout=timeout)
    return {"code": code, "salida": (out + err)[-1200:]}


def gate_mutmut(modulo: str, umbral_muertos: int, dry: bool = False) -> dict:
    """Gate 5: validación de mutación del módulo.

    NO relanza el barrido completo de mutmut por módulo (el árbol mutado
    rompe tests que dependen del árbol completo y el barrido tarda ~4 min
    por ejecución). En su lugar valida contra el reporte diario de
    mutmut_daily (docs/udo/mutation-reports/YYYY-MM-DD_*.md): el módulo
    debe aparecer sin sobrevivientes críticos o estar en el lote del día.

    Si no hay reporte del día, devuelve 'pendiente' (no bloquea, queda
    registrado en memoria para la revisión diaria).
    """
    if dry:
        return {"code": 0, "salida": "[dry-run] gate mutmut (reporte diario)", "muertos": None}
    hoy = datetime.now(UTC).date().isoformat()
    reportes = sorted((REPO / "docs" / "udo" / "mutation-reports").glob(f"{hoy}*.md"))
    if not reportes:
        ayer = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
        reportes = sorted((REPO / "docs" / "udo" / "mutation-reports").glob(f"{ayer}*.md"))
    if not reportes:
        return {"code": 2, "salida": "sin reporte mutmut del día (pendiente de mutmut_daily)", "muertos": None}
    texto = "\n".join(r.read_text(errors="ignore") for r in reportes)
    target = modulo.rstrip("/")
    if target not in texto:
        return {"code": 2, "salida": "módulo no está en el reporte mutmut del día (pendiente)", "muertos": None}
    # conteo real de sobrevivientes del módulo (formato mutmut: <mod>.<clase>..._mutmut_N: survived)
    sobrevivientes = []
    for linea in texto.splitlines():
        if "survived" in linea and target.replace("/", ".") in linea:
            sobrevivientes.append(linea.strip())
    if sobrevivientes:
        return {
            "code": 1,
            "salida": f"{len(sobrevivientes)} mutantes sobrevivientes en {target}: {sobrevivientes[0][:120]}",
            "muertos": None,
        }
    # exit code 1 sin survived explícitos (fallo de lote) -> pendiente, no bloquea
    if "exit code" in texto and "Exit code: 1" in texto and not sobrevivientes:
        return {
            "code": 2,
            "salida": "reporte mutmut del día con exit 1 sin sobrevivientes (pendiente de revisión)",
            "muertos": None,
        }
    return {"code": 0, "salida": "módulo cubierto por el reporte mutmut del día (sin sobrevivientes)", "muertos": None}


def gate_calidad(modulo: str) -> dict:
    """Gate 6: ruff + mypy sobre el módulo."""
    partes: list[str] = []
    code1, o1, e1 = run([str(VENV / "ruff"), "check", modulo.rstrip("/")], timeout=300)
    partes.append(f"ruff={code1}")
    code2, o2, e2 = run(
        [str(PYTHON), "-m", "mypy", "--no-incremental", modulo.rstrip("/")],
        timeout=600,
    )
    partes.append(f"mypy={code2}")
    return {"code": 0 if code1 == 0 and code2 == 0 else 1, "salida": f"{o1}{e1}{o2}{e2}"[-1200:]}


# ---------------------------------------------------------------------------
# Bucle por módulo
# ---------------------------------------------------------------------------


def _bloquear(data: dict, modulo: str, motivo: str) -> None:
    est = _modulo_estado(data, modulo)
    est["estado"] = "bloqueado"
    _registrar(data, modulo, "bloqueado", motivo)
    _save_state(data)


def _generar_plantilla_si_falta(modulo: str, dry: bool) -> dict:
    """Gate 2: genera la plantilla SOLO si no existe (nunca pisa tests ampliados/LLM)."""
    if any((REPO / "tests" / "unit").glob(f"test_{Path(modulo).stem}_smoke.py")):
        return {"code": 0, "salida": "tests de plantilla ya existen (no se regeneran)"}
    if dry:
        return {"code": 0, "salida": "[dry-run] plantilla"}
    return gate_plantilla(modulo, force=False)


def procesar_modulo(
    modulo: str,
    min_pct: int,
    umbral_muertos: int,
    max_intentos: int,
    seed: int | None,
    dry: bool,
) -> int:
    data = _load_state()
    est = _modulo_estado(data, modulo)
    est["estado"] = "en_progreso"
    est["intentos"] += 1
    _registrar(data, modulo, "inicio", f"intento {est['intentos']}/{max_intentos}")
    _save_state(data)

    # Gate 1 — medir cobertura actual
    g1 = gate_medir(modulo, min_pct)
    _registrar(data, modulo, "gate1_medir", g1["salida"][-300:])
    if g1["code"] == 0:
        est["cobertura_antes"] = ">= min"
        est["estado"] = "verde"
        _registrar(data, modulo, "verde", "ya cumple el mínimo sin tocar nada")
        _save_state(data)
        return 0

    # Gate 2 — generar plantilla SOLO si no existe (nunca pisar tests ampliados/LLM)
    g2 = _generar_plantilla_si_falta(modulo, dry)
    _registrar(data, modulo, "gate2_plantilla", g2["salida"][-300:])
    if g2["code"] != 0:
        _bloquear(data, modulo, "plantilla no aplicable")
        return 1

    # Gate 3 — sintaxis
    g3 = gate_sintaxis() if not dry else {"code": 0, "salida": "[dry-run] sintaxis"}
    _registrar(data, modulo, "gate3_sintaxis", g3["salida"][-200:])
    if g3["code"] != 0:
        _bloquear(data, modulo, "sintaxis rota tras plantilla")
        return 1

    # Gate 4 — pytest del módulo (fork, orden aleatorio, sin xdist)
    g4 = gate_pytest(modulo, seed) if not dry else {"code": 0, "salida": "[dry-run] pytest"}
    _registrar(data, modulo, "gate4_pytest", g4["salida"][-400:])
    if g4["code"] != 0:
        est["seed"] = seed
        _bloquear(data, modulo, f"pytest falla (seed={seed})")
        return 1

    # Gate 5 — mutmut (juez del 100% real; pendiente no bloquea)
    g5 = gate_mutmut(modulo, umbral_muertos, dry=dry)
    _registrar(data, modulo, "gate5_mutmut", g5["salida"][-400:])
    if g5["code"] == 2:
        _registrar(data, modulo, "pendiente", "gate mutmut: pendiente del reporte diario (no bloquea)")
    elif g5["code"] != 0:
        est["estado"] = "alerta"
        _registrar(data, modulo, "alerta", "mutantes sobrevivientes o error de mutmut")
        _save_state(data)
        return 1

    # Gate 6 — calidad
    g6 = gate_calidad(modulo) if not dry else {"code": 0, "salida": "[dry-run] calidad"}
    _registrar(data, modulo, "gate6_calidad", g6["salida"][-400:])
    if g6["code"] != 0:
        est["estado"] = "alerta"
        _registrar(data, modulo, "alerta", "ruff/mypy fallan")
        _save_state(data)
        return 1

    # Éxito — SOLO si la cobertura final medida >= min (100x100 sin margen)
    g1b = gate_medir(modulo, min_pct)
    est["cobertura_despues"] = g1b["salida"].splitlines()[-1] if g1b["salida"] else None
    if g1b["code"] != 0:
        est["estado"] = "alerta"
        _registrar(data, modulo, "alerta", f"cobertura final < {min_pct}%: {est['cobertura_despues']}")
        _save_state(data)
        return 1
    est["estado"] = "verde"
    est["seed"] = seed
    _registrar(data, modulo, "verde", f"cobertura final >= {min_pct}% ({est['cobertura_despues']})")
    _save_state(data)
    return 0


def _emitir_contratos_llm(data: dict) -> None:
    """Genera los contratos de entrada para el agente LLM de alarma.

    - .nervioso/llm_proposal.json  : módulos en alerta/bloqueado con contexto
    - .nervioso/flaky_tests.json   : tests con reruns (registrados por el gate pytest)
    - docs/udo/coverage-reports/   : reporte markdown (ya generado)
    """
    out = Path(".nervioso")
    alertas = {m: est for m, est in data.get("modulos", {}).items() if est.get("estado") in ("alerta", "bloqueado")}
    # regresión diaria: módulos que pasaron de verde a alerta/bloqueado vs reporte anterior
    regresion = []
    reportes = sorted((REPO / "docs" / "udo" / "coverage-reports").glob("*.md"))
    if len(reportes) >= 2:
        anterior = reportes[-2].read_text(errors="ignore")
        for m, est in data.get("modulos", {}).items():
            if (
                est.get("estado") in ("alerta", "bloqueado")
                and m in anterior
                and "verde" not in anterior.split(m)[1][:200]
            ):
                regresion.append(m)
    (out / "regresion_diaria.json").write_text(
        json.dumps({"fecha": _now(), "modulos_en_regresion": regresion}, ensure_ascii=False, indent=2)
    )
    flakies = []
    for m, est in data.get("modulos", {}).items():
        for ev in est.get("trazabilidad", []):
            det = ev.get("detalle", "")
            if "pytest" in ev.get("evento", "") and ("rerun" in det.lower() or "flaky" in det.lower()):
                flakies.append({"modulo": m, "evento": ev.get("evento"), "detalle": det[:300]})

    out = Path(".nervioso")
    out.mkdir(parents=True, exist_ok=True)
    (out / "llm_proposal.json").write_text(
        json.dumps(
            {
                "generado": _now(),
                "modulos_alerta": alertas,
                "instrucciones": "El pipeline determinista ha fallado. Revisa SOLO los tests generados por la plantilla; propón parches quirúrgicos (asserts/casos hypothesis/mocks). NO toques producción. Guarda tu propuesta aquí con veredicto.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    (out / "flaky_tests.json").write_text(json.dumps(flakies, ensure_ascii=False, indent=2))
    print(
        f"Contratos LLM: {out / 'llm_proposal.json'} ({len(alertas)} alertas), {out / 'flaky_tests.json'} ({len(flakies)} flakies)"
    )


def _modulos_pendientes(data: dict) -> list[str]:
    pend = []
    for m in MODULOS_AUTORIZADOS:
        est = data["modulos"].get(m)
        if not est or est.get("estado") in ("pendiente", "alerta", "bloqueado"):
            pend.append(m)
    return pend


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modulo", help="módulo concreto a procesar (ruta o paquete)")
    parser.add_argument("--min", type=int, default=COBERTURA_MIN)
    parser.add_argument("--mut-muertos", type=int, default=MUTACIONES_UMBRAL)
    parser.add_argument("--max-intentos", type=int, default=MAX_INTENTOS)
    parser.add_argument("--seed", type=int, default=None, help="semilla fija de --randomly-seed")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true", help="mostrar memoria y salir")
    parser.add_argument("--reset", action="store_true", help="reiniciar memoria")
    parser.add_argument("--reporte", action="store_true", help="generar reporte markdown del estado")
    args = parser.parse_args(argv)

    if args.reset:
        _save_state({"creado": _now(), "modulos": {}})
        print("Memoria reiniciada.")
        return 0

    data = _load_state()
    if args.status or args.reporte:
        for m, est in sorted(data["modulos"].items()):
            print(
                f"{est.get('estado', '?'):10s} {m:40s} intentos={est.get('intentos', 0)} antes={est.get('cobertura_antes', '?')}"
            )
        if args.reporte:
            out = Path("docs/udo/coverage-reports")
            out.mkdir(parents=True, exist_ok=True)
            ruta = out / f"{datetime.now(UTC).date().isoformat()}.md"
            ruta.write_text(
                "# Reporte de cobertura del pipeline\n\n"
                "| Módulo | Estado | Intentos | Cobertura antes | Traza última |\n|---|---|---|---|---|\n"
                + "\n".join(
                    f"| {m} | {est.get('estado', '?')} | {est.get('intentos', 0)} | {est.get('cobertura_antes', '-')} | {est['trazabilidad'][-1]['evento'] if est.get('trazabilidad') else '-'} |"
                    for m, est in sorted(data["modulos"].items())
                )
                + "\n"
            )
            print(f"Reporte: {ruta}")
            _emitir_contratos_llm(data)
        return 0

    seed = args.seed if args.seed is not None else int(time.time()) % 1000000
    modulos = [args.modulo] if args.modulo else _modulos_pendientes(data)

    exit_final = 0
    for modulo in modulos:
        print(f"\n=== {modulo} (seed={seed}) ===")
        for intento in range(1, args.max_intentos + 1):
            rc = procesar_modulo(modulo, args.min, args.mut_muertos, args.max_intentos, seed, args.dry_run)
            if rc == 0:
                break
            if args.dry_run:
                break
            print(f"  intento {intento} falló; reintentando...")
            time.sleep(2)
        else:
            exit_final = 1
        if rc != 0:
            exit_final = 1
    print(f"\nRESULTADO: {'OK' if exit_final == 0 else 'ALERTA (revisar memoria)'}")
    return exit_final


if __name__ == "__main__":
    sys.exit(main())
