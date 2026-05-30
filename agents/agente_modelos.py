#!/usr/bin/env python3
"""
agente_modelos.py — Gestiona modelos Ollama
"""

import logging

logger = logging.getLogger(__name__)
import subprocess
from datetime import datetime
from pathlib import Path

SISTEMA = Path(__file__).parent.parent
LOG = SISTEMA / "logs" / "modelos.log"
LOG.parent.mkdir(exist_ok=True)

MODELO_PRINCIPAL = "principal"
TIEMPO_DESCARGA_MIN = 30


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def obtener_modelos():
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lineas = result.stdout.strip().split("\n")[1:]
            modelos = []
            for linea in lineas:
                if linea.strip():
                    partes = linea.split()
                    if len(partes) >= 3:
                        modelos.append(
                            {
                                "nombre": partes[0],
                                "id": partes[1] if len(partes) > 1 else "",
                                "size": partes[2] if len(partes) > 2 else "",
                            }
                        )
            return modelos
    except Exception as e:
        log(f"ERROR listando modelos: {e}")
    return []


def modelos_en_memoria():
    try:
        result = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lineas = result.stdout.strip().split("\n")[1:]
            return [l.split()[0] for l in lineas if l.strip()]
    except Exception as e:
        logger.warning(f"Error silencioso en agente_modelos.list_models: {e}")
        # fallback: lista vacía
    return []


def descargar_modelo(nombre):
    try:
        log(f"Descargando {nombre}...")
        result = subprocess.run(
            ["ollama", "pull", nombre], capture_output=True, text=True, timeout=3600
        )
        return result.returncode == 0
    except Exception as e:
        log(f"ERROR descargando {nombre}: {e}")
        return False


def descargar_si_necesario(nombre):
    modelos = [m["nombre"] for m in obtener_modelos()]
    if nombre not in modelos:
        return descargar_modelo(nombre)
    return True


def liberar_memoria():
    try:
        subprocess.run(["ollama", "dup"], capture_output=True, timeout=30)
        log("Memoria liberada")
        return True
    except:
        return False


def estado_ollama():
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except:
        return False


def generar_informe():
    modelos = obtener_modelos()
    en_memoria = modelos_en_memoria()
    ollama_ok = estado_ollama()

    informe = f"""
╔══════════════════════════════════════════════════════╗
║           INFORME DE MODELOS — {datetime.now().strftime("%Y-%m-%d %H:%M")}
╠══════════════════════════════════════════════════════╣
║  Ollama:        {"✅ Activo" if ollama_ok else "❌ No responde"}
║  Modelos:       {len(modelos)}
║  En memoria:     {len(en_memoria)}
╚══════════════════════════════════════════════════════╝

📦 MODELOS DESCARGADOS:
"""
    for m in modelos:
        en_ram = "🟢" if m["nombre"] in en_memoria else "⚪"
        informe += f"  {en_ram} {m['nombre']} ({m['size']})\n"

    if en_memoria:
        informe += "\n🧠 EN MEMORIA:\n"
        for m in en_memoria:
            informe += f"  → {m}\n"

    return informe


if __name__ == "__main__":
    import sys

    if "--informe" in sys.argv or "--report" in sys.argv:
        print(generar_informe())
    elif "--pull" in sys.argv and len(sys.argv) > 2:
        descargar_modelo(sys.argv[2])
    elif "--ps" in sys.argv:
        print("En memoria:", modelos_en_memoria())
    elif "--list" in sys.argv:
        for m in obtener_modelos():
            print(f"{m['nombre']} ({m['size']})")
    elif "--free" in sys.argv:
        liberar_memoria()
    else:
        print(generar_informe())
