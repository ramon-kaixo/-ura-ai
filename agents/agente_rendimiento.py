#!/usr/bin/env python3
"""
agente_rendimiento.py — Monitoriza y gestiona CPU y RAM
"""

import logging

logger = logging.getLogger(__name__)
import subprocess
from datetime import datetime
from pathlib import Path

import psutil

SISTEMA = Path(__file__).parent.parent
LOG = SISTEMA / "logs" / "rendimiento.log"
LOG.parent.mkdir(exist_ok=True)

LIMITE_CPU = 80.0
LIMITE_RAM = 85.0
LIBERAR_RAM_UMBRAL = 15.0  # Porcentaje de RAM libre mínimo antes de intentar liberar


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def obtener_procesos():
    procesos = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            info["cpu_percent"] = info.get("cpu_percent") or 0
            info["memory_percent"] = info.get("memory_percent") or 0
            procesos.append(info)
        except Exception as e:
            logger.warning(f"Error silencioso en agente_rendimiento.get_processes: {e}")
            # fallback: continuar
    return sorted(procesos, key=lambda x: x.get("cpu_percent", 0), reverse=True)


def procesos_criticos():
    criticos = []
    for p in obtener_procesos()[:10]:
        cpu = p.get("cpu_percent", 0)
        ram = p.get("memory_percent", 0)
        if cpu > LIMITE_CPU or ram > LIMITE_RAM:
            criticos.append(p)
    return criticos


def matar_proceso(pid):
    try:
        subprocess.run(["kill", str(pid)], check=True)
        return True
    except:
        return False


def obtener_memoria_liberable() -> float:
    """
    Obtiene la memoria liberable usando vm_stat (macOS)

    Returns:
        Memoria liberable en GB
    """
    try:
        result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)

        if result.returncode != 0:
            return 0.0

        # Parsear vm_stat output
        # "Pages free: 12345" - páginas libres
        # "Pages purgeable: 67890" - páginas purgeables
        # 1 página = 4096 bytes en macOS ARM64
        page_size = 4096
        free_pages = 0
        purgeable_pages = 0

        for line in result.stdout.split("\n"):
            if "Pages free:" in line:
                free_pages = int(line.split(":")[1].strip().replace(".", ""))
            elif "Pages purgeable:" in line:
                purgeable_pages = int(line.split(":")[1].strip().replace(".", ""))

        total_liberable_bytes = (free_pages + purgeable_pages) * page_size
        liberable_gb = total_liberable_bytes / (1024**3)

        return liberable_gb

    except Exception as e:
        log(f"Error obteniendo memoria liberable: {e}")
        return 0.0


def liberar_ram(forzar: bool = False) -> dict:
    """
    Libera RAM inactiva usando sudo purge (macOS)

    Args:
        forzar: Forzar liberación sin verificar umbral

    Returns:
        Diccionario con resultado de la operación
    """
    ram = psutil.virtual_memory()
    ram_libre_gb = ram.available / (1024**3)
    ram_libre_pct = ram.percent  # Porcentaje usado, no libre
    ram_libre_real_pct = 100 - ram_libre_pct  # Porcentaje libre

    # Verificar si es necesario liberar (a menos que se fuerce)
    if not forzar and ram_libre_real_pct >= LIBERAR_RAM_UMBRAL:
        log(
            f"RAM libre: {ram_libre_real_pct:.1f}% ({ram_libre_gb:.1f} GB) - No necesario liberar (umbral: {LIBERAR_RAM_UMBRAL}%)"
        )
        return {
            "ejecutado": False,
            "razon": "RAM suficiente",
            "ram_libre_antes_gb": ram_libre_gb,
            "ram_libre_antes_pct": ram_libre_real_pct,
            "ram_liberada_gb": 0.0,
        }

    log(f"Liberando RAM - Libre: {ram_libre_real_pct:.1f}% ({ram_libre_gb:.1f} GB)")

    try:
        # Ejecutar sudo purge
        result = subprocess.run(["sudo", "purge"], capture_output=True, text=True, timeout=30)

        # Verificar resultado
        if result.returncode == 0:
            # Medir RAM después
            ram_despues = psutil.virtual_memory()
            ram_libre_despues_gb = ram_despues.available / (1024**3)
            ram_liberada_gb = ram_libre_despues_gb - ram_libre_gb

            log(
                f"RAM liberada: {ram_liberada_gb:.2f} GB ({ram_libre_gb:.1f} GB -> {ram_libre_despues_gb:.1f} GB)"
            )

            return {
                "ejecutado": True,
                "exito": True,
                "ram_libre_antes_gb": ram_libre_gb,
                "ram_libre_antes_pct": ram_libre_real_pct,
                "ram_libre_despues_gb": ram_libre_despues_gb,
                "ram_liberada_gb": ram_liberada_gb,
                "stderr": result.stderr,
            }
        else:
            # Si falla por contraseña u otro error
            log(f"Error ejecutando sudo purge: {result.stderr}")
            return {
                "ejecutado": True,
                "exito": False,
                "razon": "Error sudo purge",
                "ram_libre_antes_gb": ram_libre_gb,
                "ram_libre_antes_pct": ram_libre_real_pct,
                "stderr": result.stderr,
            }

    except subprocess.TimeoutExpired:
        log("Timeout ejecutando sudo purge")
        return {
            "ejecutado": True,
            "exito": False,
            "razon": "Timeout",
            "ram_libre_antes_gb": ram_libre_gb,
            "ram_libre_antes_pct": ram_libre_real_pct,
        }
    except Exception as e:
        log(f"Excepción liberando RAM: {e}")
        return {
            "ejecutado": True,
            "exito": False,
            "razon": str(e),
            "ram_libre_antes_gb": ram_libre_gb,
            "ram_libre_antes_pct": ram_libre_real_pct,
        }


def obtener_estado():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disco = psutil.disk_usage("/")
    memoria_liberable_gb = obtener_memoria_liberable()

    return {
        "cpu": cpu,
        "ram_uso": ram.percent,
        "ram_disponible_gb": ram.available / (1024**3),
        "ram_liberable_gb": memoria_liberable_gb,
        "disco_uso": disco.percent,
        "procesos_criticos": len(procesos_criticos()),
    }


def generar_informe():
    estado = obtener_estado()
    criticos = procesos_criticos()

    informe = f"""
╔══════════════════════════════════════════════════════╗
║        INFORME DE RENDIMIENTO — {datetime.now().strftime("%Y-%m-%d %H:%M")}
╠══════════════════════════════════════════════════════╣
║  CPU:           {estado["cpu"]:.1f}%
║  RAM:           {estado["ram_uso"]:.1f}% ({estado["ram_disponible_gb"]:.1f} GB libre)
║  RAM liberable: {estado["ram_liberable_gb"]:.1f} GB
║  Disco:         {estado["disco_uso"]:.1f}% usado
║  Procesos críticos: {estado["procesos_criticos"]}
╚══════════════════════════════════════════════════════╝
"""
    if criticos:
        informe += "\n⚠️  PROCESOS CRÍTICOS:\n"
        for p in criticos[:5]:
            informe += f"  - {p['name']} (PID {p['pid']}): CPU {p['cpu_percent']:.1f}%, RAM {p['memory_percent']:.1f}%\n"

    return informe


if __name__ == "__main__":
    import sys

    if "--informe" in sys.argv or "--report" in sys.argv:
        print(generar_informe())
    elif "--estado" in sys.argv:
        import json

        print(json.dumps(obtener_estado()))
    elif "--liberar" in sys.argv or "--purge" in sys.argv:
        import json

        forzar = "--forzar" in sys.argv
        resultado = liberar_ram(forzar=forzar)
        print(json.dumps(resultado, indent=2))
    else:
        estado = obtener_estado()

        # Calcular porcentaje de RAM libre
        ram_libre_pct = 100 - estado["ram_uso"]

        # Intentar liberar RAM si es baja (antes de matar procesos)
        if ram_libre_pct < LIBERAR_RAM_UMBRAL:
            log(f"RAM baja: {ram_libre_pct:.1f}% (< {LIBERAR_RAM_UMBRAL}%), intentando liberar...")
            resultado_liberacion = liberar_ram()
            if resultado_liberacion["ejecutado"] and resultado_liberacion["exito"]:
                print(f"✓ RAM liberada: {resultado_liberacion['ram_liberada_gb']:.2f} GB")
            elif resultado_liberacion["ejecutado"] and not resultado_liberacion["exito"]:
                print(
                    f"⚠️  No se pudo liberar RAM: {resultado_liberacion.get('razon', 'Error desconocido')}"
                )

        # Verificar procesos críticos después de intentar liberar RAM
        estado_actualizado = obtener_estado()
        if estado_actualizado["procesos_criticos"] > 0:
            log(f"ALERTA: {estado_actualizado['procesos_criticos']} procesos críticos")
            print(generar_informe())
        else:
            print(
                f"✓ Sistema OK — CPU: {estado_actualizado['cpu']:.1f}%, RAM: {estado_actualizado['ram_uso']:.1f}% (liberable: {estado_actualizado['ram_liberable_gb']:.1f} GB)"
            )
