#!/usr/bin/env python3
"""Parse de resultados de pytest + entorno — genera informe clasificado.

Clasifica fallos: 🔴 (crítico) / 🟠 (medio) / 🟡 (bajo) / 🟢 (ok).
Detecta desfases: modelos obsoletos, máquinas ausentes, servicios caídos.
NO auto-arregla. Solo genera informe en docs/udo/pendientes/.

Uso:
    parse_pytest_results.py --log /tmp/pytest_diario.log --entorno /tmp/ura_entorno_real.json
    parse_pytest_results.py --log /tmp/pytest_diario.log  (entorno opcional)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PENDIENTES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "udo" / "pendientes"

# Modelos que podrían estar obsoletos (desfase)
MODELOS_OBSOLETOS = ["qwen2.5", "gemini-2.0-flash", "llama2", "mixtral-8x7b"]
# Máquinas esperadas
MAQUINAS = ["gx10-64c3", "100.72.103.12"]


def parse_pytest_log(log_path: Path) -> tuple[list[str], list[str]]:
    """Extrae fallos y errores del log de pytest."""
    fallos: list[str] = []
    errores: list[str] = []
    if not log_path.exists():
        return fallos, errores
    for line in log_path.read_text(errors="replace").splitlines():
        m = re.search(r"^(FAILED|ERROR)\s+(.*)$", line.strip())
        if m:
            (fallos if m.group(1) == "FAILED" else errores).append(m.group(2))
    return fallos, errores


def detectar_desfase(entorno: dict | None) -> list[str]:
    """Detecta modelos obsoletos, máquinas ausentes, servicios caídos."""
    hallazgos: list[str] = []
    if not entorno:
        return hallazgos
    modelos = entorno.get("modelos_ollama", [])
    for modelo_obs in MODELOS_OBSOLETOS:
        if any(modelo_obs in m for m in modelos):
            hallazgos.append(f"Modelo potencialmente obsoleto en uso: {modelo_obs}")
    servicios = entorno.get("servicios", {})
    for svc, estado in servicios.items():
        if estado not in ("active", "ok"):
            hallazgos.append(f"Servicio {svc}: estado {estado}")
    return hallazgos


def clasificar(fallos: list[str], errores: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Clasifica en criticos/medios/bajos."""
    criticos: list[str] = []
    medios: list[str] = []
    bajos: list[str] = []
    todos = [(f, "FAILED") for f in fallos] + [(e, "ERROR") for e in errores]
    for item, tipo in todos:
        if tipo == "ERROR" or "segfault" in item.lower() or "timeout" in item.lower():
            criticos.append(item)
        elif "import" in item.lower():
            medios.append(item)
        else:
            bajos.append(item)
    return criticos, medios, bajos


def generar_informe(fallos: list[str], errores: list[str], hallazgos: list[str], fecha: str) -> Path:
    """Genera el informe markdown."""
    criticos, medios, bajos = clasificar(fallos, errores)
    PENDIENTES_DIR.mkdir(parents=True, exist_ok=True)
    out = PENDIENTES_DIR / f"TEST_AUDIT_{fecha}.md"
    with out.open("w") as f:
        f.write(f"# Auditoría de tests — {fecha}\n\n")
        f.write(f"- Fallos: {len(fallos)} | Errores: {len(errores)} | Desfases: {len(hallazgos)}\n\n")
        f.write("## 🔴 Críticos\n")
        for c in criticos or ["(ninguno)"]:
            f.write(f"- {c}\n")
        f.write("\n## 🟠 Medios\n")
        for m in medios or ["(ninguno)"]:
            f.write(f"- {m}\n")
        f.write("\n## 🟡 Bajos\n")
        for b in bajos or ["(ninguno)"]:
            f.write(f"- {b}\n")
        f.write("\n## Desfases del entorno\n")
        for h in hallazgos or ["(ninguno)"]:
            f.write(f"- {h}\n")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, help="ruta al log de pytest")
    parser.add_argument("--entorno", default="", help="ruta al JSON de entorno")
    parser.add_argument("--fecha", default="", help="fecha (default: hoy)")
    args = parser.parse_args(argv)

    fecha = args.fecha or __import__("datetime").date.today().isoformat()
    entorno: dict | None = None
    if args.entorno and Path(args.entorno).exists():
        try:
            entorno = json.loads(Path(args.entorno).read_text())
        except (json.JSONDecodeError, OSError):
            entorno = None

    fallos, errores = parse_pytest_log(Path(args.log))
    hallazgos = detectar_desfase(entorno)
    informe = generar_informe(fallos, errores, hallazgos, fecha)

    print(f"Informe generado: {informe}")
    print(f"  Fallos: {len(fallos)} | Errores: {len(errores)} | Desfases: {len(hallazgos)}")
    if fallos or errores or hallazgos:
        print("⚠️  Hay hallazgos. Revisar el informe (NO auto-arreglar).")
        return 1
    print("✅ Sin hallazgos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
