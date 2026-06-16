#!/usr/bin/env python3
"""Pipeline Supremo — Orquestador completo de refactorizacion URA.

FLUJO CORRECTO:
  0. Guardian disco (SHA-256 scan)
  1. Token screen (RAM check)
  2. Scanner entrada (snapshot AST)
  3. Poda mecanica (dead code + chromatic map)
  4. Refactor con compactacion (compacta -> LLM -> descompacta)
  5. Compactadora (reensamblaje + validacion AST/tokens/chromatic)
  6. Auto-reglas (reglas deterministas F821)
  7. Scanner salida (diff + chunk_optimizer bucle cerrado)
  8. Inspectores + OpenClaw (paralelo)
  9. Alineador (validacion de respuestas)
  10. Decision consenso (ESCRIBIR/WATERMARK/REPARAR/ROLLBACK)
  11. Guardian verify (post-escritura)

FUSIONADO CON:
  - alineador.py (validacion de calidad de respuestas URA/OpenClaw)
"""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

URA_ROOT = Path("/home/ramon/URA/ura_ia_1972")
SCRIPTS = URA_ROOT / "scripts/pro"
NERVIOSO = URA_ROOT / ".nervioso"
NERVIOSO.mkdir(parents=True, exist_ok=True)

GUARDIAN = URA_ROOT / "core" / "guardian_disco.py"


def run_step(cmd, timeout=60, json_output=True):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(URA_ROOT))
        if json_output and r.stdout:
            return json.loads(r.stdout)
        return {"raw": r.stdout[:200] if r.stdout else "", "returncode": r.returncode}
    except Exception as e:
        return {"error": str(e)}


def update_conciencia(proceso, estado, progreso=None) -> None:
    args = [sys.executable, str(SCRIPTS / "conciencia.py"), "--escribir", proceso, estado]
    subprocess.run(args, capture_output=True, cwd=str(URA_ROOT))
    if progreso:
        subprocess.run(
            [sys.executable, str(SCRIPTS / "conciencia.py"), "--progreso", progreso],
            capture_output=True,
            cwd=str(URA_ROOT),
        )


# -- Steps --


def step_guardian():
    return run_step([sys.executable, str(GUARDIAN), "--scan", "--json"], timeout=60)


def step_token_screen(ruta):
    update_conciencia("token_screen", "activo")
    result = run_step(
        [sys.executable, str(SCRIPTS / "token_screen.py"), str(ruta), "--json"], timeout=30,
    )
    update_conciencia("token_screen", "idle" if result.get("ok") else "bloqueado")
    return result


def step_scanner_entrada(ruta):
    update_conciencia("scanner", "entrada")
    result = run_step(
        [sys.executable, str(SCRIPTS / "scanner_autoajuste.py"), str(ruta), "--json"], timeout=30,
    )
    update_conciencia("scanner", "idle")
    return result


def step_poda(ruta):
    update_conciencia("poda", "activo")
    result = run_step(
        [sys.executable, str(SCRIPTS / "poda_mecanica.py"), str(ruta), "--json"], timeout=30,
    )
    update_conciencia("poda", "idle")
    return result


def step_refactor():
    update_conciencia("refactorer", "activo")
    r = subprocess.run(
        [sys.executable, "-u", str(SCRIPTS / "refactor_large_functions_v2.py")],
        capture_output=True,
        text=True,
        timeout=3600,
        cwd=str(URA_ROOT),
    )
    update_conciencia("refactorer", "idle")
    output = r.stdout[-1000:] if r.stdout else ""
    return {"status": "ejecutado", "output": output}


def step_compactadora(ruta, chromatic_map=None):
    update_conciencia("compactadora", "activo")
    results = {}
    if chromatic_map:
        map_path = NERVIOSO / "chromatic_map_temp.json"
        map_path.write_text(json.dumps(chromatic_map))
        r_compact = run_step(
            [sys.executable, str(SCRIPTS / "compactadora.py"), "--metadata", str(map_path), "--json"],
            timeout=30,
        )
        results["validacion"] = r_compact
    run_step([sys.executable, str(SCRIPTS / "auto_reglas.py"), "--generar"], timeout=15)
    results["auto_reglas"] = "ok"
    update_conciencia("compactadora", "idle")
    update_conciencia("auto_reglas", "idle")
    return results


def step_scanner_salida(ruta):
    update_conciencia("scanner", "salida")
    result = run_step(
        [sys.executable, str(SCRIPTS / "scanner_autoajuste.py"), str(ruta), "--diff", "--json"],
        timeout=30,
    )
    update_conciencia("scanner", "idle")
    return result


def step_inspectores(ruta):
    update_conciencia("inspectores", "activo")
    result = run_step(
        [sys.executable, str(SCRIPTS / "inspectores.py"), str(ruta), "--json"], timeout=60,
    )
    update_conciencia("inspectores", "idle")
    return result


def step_openclaw(ruta):
    update_conciencia("openclaw", "activo")
    result = run_step(
        [sys.executable, str(SCRIPTS / "openclaw_reviewer.py"), str(ruta), "--json"], timeout=180,
    )
    update_conciencia("openclaw", "idle")
    return result


def step_alineador():
    update_conciencia("alineador", "activo")
    result = run_step([sys.executable, str(SCRIPTS / "alineador.py")], timeout=30)
    update_conciencia("alineador", "idle")
    return result


def step_guardian_verify(archivo):
    return run_step([sys.executable, str(GUARDIAN), "--verify", archivo, "--"], timeout=10)


# -- SDA Gate --


def verificar_consenso_SDA(propuesta_plan: str) -> bool:
    ruta_plan = "/tmp/ura_debate_plan.json"
    with open(ruta_plan, "w") as f:
        json.dump({"plan": propuesta_plan, "author": "pipeline"}, f, ensure_ascii=False)
    cmd = [
        sys.executable,
        str(SCRIPTS / "plan_validator.py"),
        "--debate",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(URA_ROOT), timeout=300)
    if proc.returncode == 0:
        return True
    elif proc.returncode == 2:
        print("[SDA WARNING] REQUERIDA ARBITRACION HUMANA. Deteniendo pipeline.")
        return False
    else:
        print(f"[SDA ERROR] Fallo interno o rechazo del comite: {proc.stderr[:500]}")
        return False


# -- Pipeline completo --


def ejecutar(ruta):
    report = {"archivo": str(ruta), "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"), "pasos": {}}
    t0 = time.time()

    report["pasos"]["guardian"] = step_guardian()

    report["pasos"]["token_screen"] = step_token_screen(ruta)
    if not report["pasos"]["token_screen"].get("ok"):
        report["resultado"] = "BLOQUEADO (RAM/tokens)"
        return report

    report["pasos"]["scanner_entrada"] = step_scanner_entrada(ruta)

    poda_result = step_poda(ruta)
    report["pasos"]["poda"] = poda_result
    chromatic_map = poda_result.get("mapa_cromatico")

    if not verificar_consenso_SDA(f"Refactorizar {ruta.name} en {ruta.parent.name}"):
        print("[PIPELINE] Abortando: El Comite Local bloqueo el plan.")
        report["resultado"] = "BLOQUEADO_SDA"
        return report

    report["pasos"]["refactor"] = step_refactor()

    report["pasos"]["compactadora"] = step_compactadora(ruta, chromatic_map)

    salida = step_scanner_salida(ruta)
    report["pasos"]["scanner_salida"] = salida

    if salida.get("accion") == "ROLLBACK":
        report["resultado"] = "ROLLBACK"
        return report

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_ins = ex.submit(step_inspectores, ruta)
        fut_oc = ex.submit(step_openclaw, ruta)
        report["pasos"]["inspectores"] = fut_ins.result()
        report["pasos"]["openclaw"] = fut_oc.result()

    report["pasos"]["alineador"] = step_alineador()

    ins_fallos = report["pasos"]["inspectores"].get("fallos", 5)
    oc_veredicto = report["pasos"]["openclaw"].get("veredicto", "RECHAZAR")
    alineador_ok = report["pasos"]["alineador"].get("ok", False)
    ins_ok = ins_fallos < 5
    oc_ok = oc_veredicto == "APROBAR"

    if not alineador_ok:
        report["resultado"] = "RECHAZADO (alineador)"
    elif ins_ok and oc_ok:
        report["resultado"] = "ESCRIBIR"
    elif ins_ok and not oc_ok:
        report["resultado"] = "WATERMARK"
    elif not ins_ok and oc_ok:
        report["resultado"] = "REPARAR"
    else:
        report["resultado"] = "ROLLBACK"

    report["pasos"]["guardian_verify"] = step_guardian_verify(str(ruta))
    report["tiempo_total_s"] = round(time.time() - t0, 1)

    return report


def init_conciencia() -> None:
    subprocess.run(
        [sys.executable, str(SCRIPTS / "conciencia.py"), "--reset"],
        capture_output=True,
        cwd=str(URA_ROOT),
    )
    for p in [
        "token_screen", "scanner", "refactorer", "compactadora",
        "auto_reglas", "inspectores", "openclaw", "alineador",
    ]:
        subprocess.run(
            [sys.executable, str(SCRIPTS / "conciencia.py"), "--escribir", p, "idle"],
            capture_output=True,
            cwd=str(URA_ROOT),
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline Supremo")
    parser.add_argument("archivo", nargs="?", help="Archivo a procesar")
    parser.add_argument("--init", action="store_true", help="Inicializar conciencia")
    parser.add_argument("--status", action="store_true", help="Ver estado")
    parser.add_argument("--task", help="Plan de tarea para validacion SDA antes de ejecutar pipeline")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.init:
        init_conciencia()
        return

    if args.status:
        subprocess.run([sys.executable, str(SCRIPTS / "conciencia.py"), "--leer"])
        return

    if args.task:
        print(f"[SDA] Evaluando plan: {args.task}")
        ok = verificar_consenso_SDA(args.task)
        if ok:
            print("[SDA] CONSENSUS alcanzado. Procediendo con pipeline.")
            if args.archivo:
                ruta = Path(args.archivo)
            else:
                ruta = URA_ROOT / "bitacora" / f"task_{time.strftime('%Y%m%d_%H%M%S')}.md"
                ruta.write_text(f"# Task: {args.task}\n")
            init_conciencia()
            report = ejecutar(ruta)
            (NERVIOSO / f"report_{time.strftime('%Y%m%d_%H%M%S')}.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
            )
            if args.json:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                resultado = report.get("resultado", "?")
                print(f"[PIPELINE] Resultado: {resultado}")
                if resultado in ("BLOQUEADO_SDA", "ROLLBACK", "RECHAZADO"):
                    sys.exit(2)
                elif resultado == "ESCRIBIR":
                    sys.exit(0)
                else:
                    sys.exit(1)
        else:
            sys.exit(2)
        return

    if args.archivo:
        ruta = Path(args.archivo)
        if not ruta.exists():
            sys.exit(1)
        init_conciencia()
        report = ejecutar(ruta)
        (NERVIOSO / f"report_{time.strftime('%Y%m%d_%H%M%S')}.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
        )
        if args.json:
            pass
        else:
            report.get("resultado", "?")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
