#!/usr/bin/env python3
# PLUGIN METADATA
PLUGIN = {
    "name": "gpu_health",
    "phase": "pre",
    "timeout": 10,
    "args": ["--json"],
    "blocking": True,
    "needs_file": False,
}
"""GPU Health Check — Detección temprana del bug de power cap (15W/650MHz).

El bug conocido del GB10 (DGX Spark / ASUS GX10) deja la GPU atrapada en:
  - Power draw ≤ 15W
  - Graphics clock ≤ 650 MHz
  - P-State P08/P12
  - SW Power Capping acumulando microsegundos
  - T.Limit Temp artificialmente bajo (~50°C)

Este script detecta ese patrón y alerta antes de que el pipeline empiece.

USO:
  python3 gpu_health.py              → Salida legible
  python3 gpu_health.py --json       → Salida JSON
  python3 gpu_health.py --watch      → Loop de monitoreo cada 2s
"""

import subprocess
import sys
import time

# Umbrales de detección del bug
CLOCK_MIN_MHZ = 1000  # Si clock < 1000MHz → bug
POWER_MIN_W = 20  # Si power idle < 20W no es bug, si power bajo carga < 20W → bug
PSTATE_BAD = {"P08", "P12", "P02", "P8"}
TEMP_LIMIT_ARTIFICIAL_MIN = 45
TEMP_LIMIT_ARTIFICIAL_MAX = 55  # Si T.Limit está entre 45-55°C → sospechoso


def _run_nvidia_smi(*args: str) -> list[str]:
    try:
        r = subprocess.run(
            ["nvidia-smi", *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return r.stdout.splitlines()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _run_nvidia_smi_q(*fields: str) -> dict[str, str]:
    """Query one-line fields from nvidia-smi."""
    query = ",".join(fields)
    lines = _run_nvidia_smi(
        "--query-gpu=" + query,
        "--format=csv,noheader,nounits",
    )
    if not lines or not lines[0].strip():
        return {}
    parts = [p.strip() for p in lines[0].split(",")]
    return dict(zip(fields, parts, strict=False))


def parse_detail_section(lines: list[str], section: str) -> dict[str, str]:
    """Parse a section from `nvidia-smi -q` output."""
    result: dict[str, str] = {}
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(section):
            in_section = True
            continue
        if in_section:
            if stripped == "" or (not stripped.startswith(" ") and ":" in stripped):
                break
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                result[key.strip()] = val.strip()
    return result


def get_full_status() -> dict:
    """Obtener estado completo de la GPU."""
    status: dict = {}

    # Lectura rápida
    quick = _run_nvidia_smi_q("pstate", "temperature.gpu", "power.draw", "clocks.current.graphics")
    status["pstate"] = quick.get("pstate", "N/A")
    status["temp_c"] = quick.get("temperature.gpu", "N/A")
    status["power_w"] = quick.get("power.draw", "N/A")
    status["clock_mhz"] = quick.get("clocks.current.graphics", "N/A")

    # Lectura detallada
    detail_lines = _run_nvidia_smi("-q")
    if detail_lines:
        clocks = parse_detail_section(detail_lines, "Clocks Event Reasons")
        status["sw_power_cap_active"] = clocks.get("SW Power Cap", "N/A")
        status["hw_slowdown"] = clocks.get("HW Slowdown", "N/A")
        status["hw_thermal_slowdown"] = clocks.get("HW Thermal Slowdown", "N/A")
        status["hw_power_brake"] = clocks.get("HW Power Brake Slowdown", "N/A")
        status["sw_thermal_slowdown"] = clocks.get("SW Thermal Slowdown", "N/A")

        counters = parse_detail_section(detail_lines, "Clocks Event Reasons Counters")
        status["sw_power_cap_us"] = counters.get("SW Power Capping", "0 us")

        # Search for T.Limit directly in raw output
        for line in detail_lines:
            if "GPU T.Limit Temp" in line:
                status["t_limit_temp"] = line.split(":")[-1].strip()
                break

        power = parse_detail_section(detail_lines, "GPU Power Readings")
        status["power_limit"] = power.get("Current Power Limit", "N/A")

    return status


def detect_bug(status: dict) -> dict:
    """Detectar el bug de power cap 15W/650MHz."""
    issues: list[str] = []
    warnings: list[str] = []

    pstate = status.get("pstate", "N/A")
    clock_str = status.get("clock_mhz", "0")
    power_str = status.get("power_w", "0")
    sw_cap = status.get("sw_power_cap_active", "N/A")
    sw_cap_us = status.get("sw_power_cap_us", "0 us")
    t_limit = status.get("t_limit_temp", "N/A")

    try:
        clock = int(clock_str)
    except (ValueError, TypeError):
        clock = 0
    try:
        power = float(power_str)
    except (ValueError, TypeError):
        power = 0.0
    us_val = 0

    # 1. P-State anómalo
    if pstate in PSTATE_BAD:
        issues.append(f"P-State anómalo: {pstate}")

    # 2. Clock congelado bajo
    if 0 < clock < CLOCK_MIN_MHZ:
        issues.append(f"Clock congelado: {clock} MHz (< {CLOCK_MIN_MHZ} MHz)")

    # 3. Power cap activo por software
    if sw_cap == "Active" or sw_cap == "Active":
        issues.append(f"SW Power Cap ACTIVO ({sw_cap})")

    # 4. SW Power Capping acumulando microsegundos
    try:
        us_val = int(sw_cap_us.replace(" us", "").replace(",", ""))
        if us_val > 1000:
            warnings.append(f"SW Power Capping acumulado: {us_val} µs (> 1ms)")
    except (ValueError, AttributeError):
        pass

    # 5. T.Limit Temp artificialmente bajo (solo como warning si hay otros síntomas)
    try:
        t_limit_val = int(t_limit.replace(" C", ""))
        if t_limit_val <= 45 and us_val > 1000:
            warnings.append(f"T.Limit Temp bajo ({t_limit_val}°C) con SW Power Capping acumulado")
    except (ValueError, AttributeError):
        pass

    verdict = "BUG" if issues else ("WARN" if warnings else "OK")
    return {
        "verdict": verdict,
        "issues": issues,
        "warnings": warnings,
        "healthy": verdict == "OK",
        "pstate": pstate,
        "clock_mhz": clock,
        "power_w": power,
        "sw_power_cap_us": sw_cap_us,
        "t_limit_temp": t_limit,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="GPU Health Check")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--watch", action="store_true", help="Loop de monitoreo continuo")
    args = parser.parse_args()

    if args.watch:
        try:
            while True:
                status = get_full_status()
                result = detect_bug(status)
                ts = time.strftime("%H:%M:%S")
                (
                    f"[{ts}] P{status.get('pstate', '?')} | "
                    f"{status.get('clock_mhz', '?')} MHz | "
                    f"{status.get('power_w', '?')}W | "
                    f"{status.get('temp_c', '?')}°C | "
                    f"{result['verdict']}"
                )
                if result["issues"]:
                    pass
                if result["warnings"]:
                    pass
                time.sleep(2)
        except KeyboardInterrupt:
            return

    status = get_full_status()
    result = detect_bug(status)

    if args.json:
        pass
    elif result["verdict"] == "BUG":
        for _i in result["issues"]:
            pass
        sys.exit(2)
    elif result["verdict"] == "WARN":
        for _w in result["warnings"]:
            pass
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
