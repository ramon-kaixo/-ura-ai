#!/usr/bin/env python3
"""Monitor VRAM en GB10: memoria unificada, procesos GPU, riesgo de contención."""
import subprocess, json, sys

def check_vram():
    # GB10 has unified memory via NVLink-C2C — GPU memory IS system RAM
    gpu_util = 0
    gpu_temp = 0
    gpu_mem_mib = 0
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            parts = out.stdout.strip().split(",")
            gpu_util = int(parts[0].strip()) if len(parts) > 0 else 0
            gpu_temp = int(parts[1].strip()) if len(parts) > 1 else 0
        # Get GPU processes memory
        out2 = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        if out2.returncode == 0:
            for line in out2.stdout.strip().split("\n"):
                if line.strip():
                    parts2 = line.split(",")
                    if len(parts2) >= 2:
                        gpu_mem_mib += int(parts2[1].strip())
    except Exception:
        pass

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
    r = check_vram(); sys.exit(1 if r.get("alerta", False) else 0)
