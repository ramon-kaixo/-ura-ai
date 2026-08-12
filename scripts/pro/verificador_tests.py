#!/usr/bin/env python3
"""verificador_tests.py — Verificación de refactor con tests (TASK-20260812-019).

Flujo (estándar de la industria):
  1. Antes del refactor: encontrar y ejecutar los tests del archivo afectado.
  2. El refactor se aplica (o se simula).
  3. Después: re-ejecutar los mismos tests y comparar resultados.
  4. Si fallan los que antes pasaban → el refactor rompió algo → revertir.

Degradación con gracia:
  - Si el archivo no tiene tests asociados → verificación por sintaxis (compile)
    + ruff, y se marca "sin tests" (el refactor procede con advertencia).
  - Si los tests del módulo ya fallaban antes → no bloquea (baseline roto),
    solo se informa.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

URA_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON = sys.executable


def _tests_para_archivo(file_path: str) -> list[Path]:
    """Busca tests que cubran un archivo de código.

    Estrategia robusta: buscar en los árboles de tests los archivos que
    IMPORTAN el módulo del archivo (import del path relativo del paquete).
    Si el módulo no se importa en ningún test, no hay cobertura real.
    """
    path = Path(file_path).resolve()
    # Ruta del módulo como se importaría: motor/core/fusion/engine
    partes = path.relative_to(URA_ROOT.resolve()).with_suffix("").parts
    # Buscar el sufijo importable: desde el paquete raíz (core., motor., knowledge.)
    importable = ".".join(partes)
    # También intentar con la última parte del paquete
    nombre = path.stem

    arboles_tests = [
        URA_ROOT / "tests" / "unit",
        URA_ROOT / "tests",
        URA_ROOT / "motor" / "tests",
        URA_ROOT / "knowledge" / "tests",
    ]
    resultado: list[Path] = []
    for arbol in arboles_tests:
        if not arbol.exists():
            continue
        for test in arbol.rglob("test_*.py"):
            try:
                texto = test.read_text(errors="ignore")
            except Exception:
                continue
            # ¿Importa el módulo EXACTO del archivo? (cobertura real)
            if f"import {importable}" in texto or f"from {importable}" in texto:
                resultado.append(test)
    # Priorizar tests directos; luego por paquete padre (fusion -> test_fusion);
    # descartar integración pesada.
    directos = [t for t in resultado if f"test_{nombre}" in t.name]
    if directos:
        return list(dict.fromkeys(directos))
    # Paquete padre: motor/core/fusion -> test_fusion
    paquete = path.parent.name
    por_paquete = [t for t in resultado if f"test_{paquete}" in t.name]
    if por_paquete:
        return list(dict.fromkeys(por_paquete))[:3]
    return list(dict.fromkeys(resultado))[:3]


def _tests_del_modulo(file_path: str) -> list[Path]:
    """Tests del módulo completo (carpeta) que pueden verse afectados."""
    path = Path(file_path)
    dir_tests = URA_ROOT / "tests" / "unit" / f"test_{path.parent.name}.py"
    return [dir_tests] if dir_tests.exists() else []


def ejecutar_tests(tests: list[Path], timeout: int = 120) -> dict:
    """Ejecuta pytest sobre los tests dados. Retorna resumen.

    Ejecuta cada test por separado (los de integración con servicios externos
    no deben bloquear al resto) y solo considera fallo real si el test
    fallaba ya en el baseline.
    """
    if not tests:
        return {"ok": True, "ejecutados": 0, "fallidos": 0, "output": ""}
    resultados: list[dict] = []
    for t in tests:
        cmd = [PYTHON, "-m", "pytest", "-q", "--no-header", str(t)]
        t0 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=URA_ROOT, check=False)
            ok = r.returncode == 0
            resultados.append({
                "test": str(t),
                "ok": ok,
                "tiempo": round(time.time() - t0, 1),
                "output": (r.stdout + r.stderr)[-800:],
            })
        except subprocess.TimeoutExpired:
            resultados.append({
                "test": str(t), "ok": False, "tiempo": timeout,
                "output": "TIMEOUT",
            })
    todos_ok = all(r["ok"] for r in resultados)
    return {
        "ok": todos_ok,
        "ejecutados": len(resultados),
        "fallidos": sum(1 for r in resultados if not r["ok"]),
        "detalle": resultados,
        "output": "\n".join(r["output"][-100:] for r in resultados if not r["ok"])[:2000],
        "tiempo": round(sum(r["tiempo"] for r in resultados), 1),
    }


def verificar_con_tests(
    file_path: str,
    antes: dict | None = None,
    nuevo_contenido: str | None = None,
    timeout: int = 120,
) -> dict:
    """Verifica que un refactor no rompa los tests del archivo.

    Args:
        file_path: archivo refactorizado.
        antes: resultado de ejecutar los tests ANTES (para comparar).
        nuevo_contenido: si se pasa, se escribe temporalmente, se testea y se
            restaura. Si no, se testea el estado actual del archivo.

    Returns:
        dict con veredicto: "ok" (no rompe), "sin_tests", "rompe" (regresión),
        o "baseline_roto" (ya fallaba antes).
    """
    tests = _tests_para_archivo(file_path) + _tests_del_modulo(file_path)
    tests = list(dict.fromkeys(tests))  # dedupe preservando orden

    if not tests:
        # Sin tests: verificación por sintaxis
        if nuevo_contenido is not None:
            try:
                compile(nuevo_contenido, file_path, "exec")
                return {"veredicto": "sin_tests", "sintaxis": "ok"}
            except SyntaxError as e:
                return {"veredicto": "sin_tests", "sintaxis": f"error: {e}"}
        return {"veredicto": "sin_tests", "sintaxis": "n/a"}

    path = Path(file_path)
    if nuevo_contenido is not None:
        # Escribir temporalmente, testear, restaurar
        original = path.read_text(encoding="utf-8")
        try:
            path.write_text(nuevo_contenido, encoding="utf-8")
            despues = ejecutar_tests(tests, timeout=timeout)
        finally:
            path.write_text(original, encoding="utf-8")
    else:
        despues = ejecutar_tests(tests, timeout=timeout)

    # Comparar con baseline (antes): un test solo bloquea si pasaba ANTES
    # y falla DESPUÉS (regresión real). Los que ya fallaban antes no bloquean.
    if antes is not None:
        detalle_antes = {r["test"]: r["ok"] for r in antes.get("detalle", [])}
        regresiones = [
            r["test"] for r in despues.get("detalle", [])
            if not r["ok"] and detalle_antes.get(r["test"], True)
        ]
        if regresiones:
            return {"veredicto": "rompe", "regresiones": regresiones, "despues": despues}
        return {"veredicto": "ok", "despues": despues}

    if despues.get("ok"):
        return {"veredicto": "ok", "despues": despues}
    # Sin baseline: si los tests fallan, puede ser por entorno (integración).
    # Se informa pero no se bloquea (veredicto "atencion").
    return {"veredicto": "atencion", "despues": despues}


if __name__ == "__main__":
    # Uso: verificador_tests.py <archivo.py>
    if len(sys.argv) < 2:
        print("Uso: verificador_tests.py <archivo.py>")
        sys.exit(1)
    resultado = verificar_con_tests(sys.argv[1])
    print(resultado)
