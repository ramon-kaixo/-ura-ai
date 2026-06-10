#!/usr/bin/env python3
"""Monitor VRAM en GB10: memoria unificada, procesos GPU, riesgo de contención."""
import subprocess, json, sys

def check_vram():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return {"error": "nvidia-smi failed"}
        parts = out.stdout.strip().split(",")
        gpu_mem_mib = int(parts[0].strip()) if len(parts) > 0 else 0
        gpu_util = int(parts[1].strip()) if len(parts) > 1 else 0
        gpu_temp = int(parts[2].strip()) if len(parts) > 2 else 0
    except Exception:
        return {"gpu_memory_gb": 0, "gpu_util_pct": 0, "gpu_temp_c": 0, "risk": "unknown"}

    try:
        out2 = subprocess.run(["free", "-g"], capture_output=True, text=True, timeout=5)
        for line in out2.stdout.splitlines():
            if "Mem:" in line:
                parts = line.split()
                ram_used = int(parts[2]) if len(parts) > 2 else 0
                ram_total = int(parts[1]) if len(parts) > 1 else 0
                break
    except Exception:
        ram_used, ram_total = 0, 0

    gpu_mem_gb = round(gpu_mem_mib / 1024, 1)
    risk = "bajo"
    if ram_used > ram_total * 0.85:
        risk = "medio"
    if ram_used > ram_total * 0.95:
        risk = "alto"

    return {
        "gpu_memory_gb": gpu_mem_gb,
        "gpu_util_pct": gpu_util,
        "gpu_temp_c": gpu_temp,
        "ram_used_gb": ram_used,
        "ram_total_gb": ram_total,
        "ram_free_gb": ram_total - ram_used,
        "risk": risk,
        "alerta": risk != "bajo",
    }

if __name__ == "__main__":
    print(json.dumps(check_vram(), indent=2))
    sys.exit(1 if check_vram()["alerta"] else 0)
