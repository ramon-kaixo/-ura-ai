#!/usr/bin/env python3
"""
agente_sandbox_codigo.py — Vigilante del sandbox de codigo URA

Modo mixto:
- AUTONOMO en lo aburrido (mover, testear, documentar)
- MANUAL en lo critico (Ramon aprueba antes de tocar produccion)
"""

import json
import time
import logging
import shutil
import subprocess
import hashlib
import os
from pathlib import Path
from datetime import datetime

SANDBOX_PENDIENTES = Path.home() / "URA" / "sandbox" / "pendientes"
SANDBOX_EN_PRUEBAS = Path.home() / "URA" / "sandbox" / "en_pruebas"
SANDBOX_ESPERA_APROBACION = Path.home() / "URA" / "sandbox" / "espera_aprobacion"
SANDBOX_APROBADOS = Path.home() / "URA" / "sandbox" / "aprobados"
SANDBOX_RECHAZADOS = Path.home() / "URA" / "sandbox" / "rechazados"
PRODUCCION = Path.home() / "URA" / "ura_ia_1972"
BACKUP = Path.home() / "URA" / "backup_versiones"
INVENTARIO = PRODUCCION / "data" / "inventario" / "inventario_codigo.json"
RAMALES = PRODUCCION / "data" / "ramales"
LOG_DIR = PRODUCCION / "logs"
INTERVALO = 60

PUSHOVER_USER = os.getenv("PUSHOVER_USER_KEY", "")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_APP_TOKEN", "")

for d in [
    SANDBOX_PENDIENTES,
    SANDBOX_EN_PRUEBAS,
    SANDBOX_ESPERA_APROBACION,
    SANDBOX_APROBADOS,
    SANDBOX_RECHAZADOS,
    BACKUP,
    RAMALES,
    LOG_DIR,
]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "agente_sandbox.log"), logging.StreamHandler()],
)
log = logging.getLogger("sandbox")


def pushover(msg, title="URA Sandbox", pri=0):
    if not PUSHOVER_USER or not PUSHOVER_TOKEN:
        return
    try:
        import requests

        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": PUSHOVER_TOKEN,
                "user": PUSHOVER_USER,
                "title": title,
                "message": msg,
                "priority": pri,
            },
            timeout=10,
        )
    except BaseException:
        pass


def md5(ruta):
    h = hashlib.md5(usedforsecurity=False)
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def es_critico(rel):
    return any(
        c in rel
        for c in [
            "core/central_router.py",
            "core/sandbox_orchestrator.py",
            "core/forensic_scribe.py",
            "api/main.py",
            "core/payment_guardian.py",
        ]
    )


def cargar_inventario():
    return json.loads(INVENTARIO.read_text()) if INVENTARIO.exists() else {"archivos": {}}


def actualizar_inventario(rel, h, ver):
    inv = cargar_inventario()
    if rel in inv["archivos"]:
        inv["archivos"][rel]["hash_md5"] = h
        inv["archivos"][rel]["version"] = ver
        inv["archivos"][rel]["ultima_modificacion"] = datetime.now().isoformat()
        INVENTARIO.write_text(json.dumps(inv, indent=2, ensure_ascii=False))
    else:
        inv["archivos"][rel] = {
            "hash_md5": h,
            "version": ver,
            "ultima_modificacion": datetime.now().isoformat(),
        }
        INVENTARIO.write_text(json.dumps(inv, indent=2, ensure_ascii=False))


def crear_ramal(rel, v_old, v_new, origen, razon):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre = f"cambio_{ts}_{rel.replace('/', '_')}.json"
    (RAMALES / nombre).write_text(
        json.dumps(
            {
                "fecha": datetime.now().isoformat(),
                "agente_origen": origen,
                "razon": razon,
                "archivo": rel,
                "version_anterior": v_old,
                "version_nueva": v_new,
                "estado": "esperando_aprobacion",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return nombre


def testear(archivo):
    try:
        r = subprocess.run(
            ["python3", "-m", "py_compile", str(archivo)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return r.returncode == 0, r.stderr[:200]
    except subprocess.TimeoutExpired:
        return False, "timeout"


def main():
    log.info("Agente sandbox iniciado (modo mixto)")
    pushover("Agente sandbox de codigo iniciado en GX10", "URA Sandbox")

    while True:
        pendientes = list(SANDBOX_PENDIENTES.glob("*.py"))
        for archivo in pendientes:
            rel = archivo.name
            # Extraer estructura de directorios del nombre (usando __ como /)
            sub_dir = ""
            if "_" in rel[:-3]:
                parts = rel[:-3].split("__")
                if len(parts) > 1:
                    sub_dir = "/".join(parts[:-1])
                    rel_path = sub_dir + "/" + parts[-1] + ".py"
                else:
                    rel_path = rel
            else:
                rel_path = rel

            prod_path = PRODUCCION / rel_path

            # Copiar al area de pruebas
            pruebas_path = SANDBOX_EN_PRUEBAS / archivo.name
            shutil.move(str(archivo), str(pruebas_path))
            log.info(f"Nuevo cambio: {rel} → en_pruebas")

            # Test rapido: compilar
            ok, err = testear(pruebas_path)
            if not ok:
                shutil.move(str(pruebas_path), str(SANDBOX_RECHAZADOS / archivo.name))
                log.warning(f"RECHAZADO {rel}: fallo compilacion - {err[:100]}")
                pushover(f"Cambio RECHAZADO en {rel}: {err[:100]}", "URA Sandbox")
                continue

            # ¿Critico? → Manual
            if es_critico(rel):
                shutil.move(str(pruebas_path), str(SANDBOX_ESPERA_APROBACION / archivo.name))
                log.warning(f"{rel} es CRITICO — requiere aprobacion de Ramon")
                pushover(f" Pendiente aprobacion: {rel} (archivo critico)", "URA Sandbox", 1)
            else:
                # Auto-aprobar cambio no critico
                shutil.move(str(pruebas_path), str(SANDBOX_APROBADOS / archivo.name))
                log.info(f"Aprobado automaticamente: {rel}")

        # Procesar aprobados: mover a produccion
        for archivo in SANDBOX_APROBADOS.glob("*.py"):
            rel = archivo.name
            prod_path = PRODUCCION / rel

            # Backup de produccion actual
            if prod_path.exists():
                backup_path = BACKUP / f"{rel}.{datetime.now().strftime('%Y%m%d_%H%M')}"
                shutil.copy2(str(prod_path), str(backup_path))
                log.info(f"Backup: {rel} → backup_versiones")

            # Sustitucion atomica
            nuevo_hash = md5(archivo)
            shutil.move(str(archivo), str(prod_path))
            actualizar_inventario(rel, nuevo_hash, "auto_aprobado")
            inv = cargar_inventario()
            v_old = (
                inv["archivos"].get(rel, {}).get("version", "desconocida")
                if rel in inv.get("archivos", {})
                else "desconocida"
            )
            crear_ramal(
                rel, v_old, "auto_aprobado", "agente_sandbox", "Cambio automatico no critico"
            )
            log.info(f"Produccion actualizado: {rel}")
            pushover(f" Cambio aplicado en produccion: {rel}")

        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
