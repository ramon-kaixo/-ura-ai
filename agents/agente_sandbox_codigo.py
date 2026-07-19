#!/usr/bin/env python3
"""agente_sandbox_codigo.py — Vigilante del sandbox de codigo URA.

Modo mixto:
- AUTONOMO en lo aburrido (mover, testear, documentar)
- MANUAL en lo critico (Ramon aprueba antes de tocar produccion)
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

SANDBOX_PENDIENTES = Path.home() / "URA" / "sandbox" / "pendientes"
SANDBOX_EN_PRUEBAS = Path.home() / "URA" / "sandbox" / "en_pruebas"
SANDBOX_ESPERA_APROBACION = Path.home() / "URA" / "sandbox" / "espera_aprobacion"
SANDBOX_APROBADOS = Path.home() / "URA" / "sandbox" / "aprobados"
SANDBOX_RECHAZADOS = Path.home() / "URA" / "sandbox" / "rechazados"
PRODUCCION = Path.home() / "URA" / "ura_ia_1972"
BACKUP = Path.home() / "URA" / "backup_versiones"
INVENTARIO = PRODUCCION / "data" / "inventario" / "inventario_codigo.json"
RAMALES = PRODUCCION / "data" / "ramales"
BRANCHES = RAMALES
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


def pushover(msg, title="URA Sandbox", pri=0) -> None:
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
        log.exception("Error enviando notificación Pushover")


def md5(ruta):
    h = hashlib.md5(usedforsecurity=False)
    with Path(ruta).open("rb") as f:
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


def actualizar_inventario(rel, h, ver) -> None:
    inv = cargar_inventario()
    if rel in inv["archivos"]:
        inv["archivos"][rel]["hash_md5"] = h
        inv["archivos"][rel]["version"] = ver
        inv["archivos"][rel]["ultima_modificacion"] = datetime.now(UTC).isoformat()
        INVENTARIO.write_text(json.dumps(inv, indent=2, ensure_ascii=False))
    else:
        inv["archivos"][rel] = {
            "hash_md5": h,
            "version": ver,
            "ultima_modificacion": datetime.now(UTC).isoformat(),
        }
        INVENTARIO.write_text(json.dumps(inv, indent=2, ensure_ascii=False))


def create_branch(rel, v_old, v_new, origin, reason):
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    name = f"change_{ts}_{rel.replace('/', '_')}.json"
    (BRANCHES / name).write_text(
        json.dumps(
            {
                "date": datetime.now(UTC).isoformat(),
                "agent_origin": origin,
                "reason": reason,
                "file": rel,
                "previous_version": v_old,
                "new_version": v_new,
                "status": "awaiting_approval",
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    return name


def test_file(file_path):
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "py_compile", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.returncode == 0, result.stderr[:200]
    except subprocess.TimeoutExpired:
        return False, "timeout"


def _probar_compilacion(pruebas_path: Path) -> tuple[bool, str]:
    ok, err = test_file(pruebas_path)
    return ok, err


def _rechazar_cambio(pruebas_path: Path, archivo: Path, rel: str, err: str) -> None:
    shutil.move(str(pruebas_path), str(SANDBOX_RECHAZADOS / archivo.name))
    log.warning(f"REJECTED {rel}: compilation failed - {err[:100]}")
    pushover(f"Change REJECTED in {rel}: {err[:100]}", "URA Sandbox")


def _esperar_aprobacion(pruebas_path: Path, archivo: Path, rel: str) -> None:
    shutil.move(str(pruebas_path), str(SANDBOX_ESPERA_APROBACION / archivo.name))
    log.warning(f"{rel} is CRITICAL — requires Ramon's approval")
    pushover(f"Pending approval: {rel} (critical file)", "URA Sandbox", 1)


def _aprobar_cambio(pruebas_path: Path, archivo: Path, rel: str) -> None:
    shutil.move(str(pruebas_path), str(SANDBOX_APROBADOS / archivo.name))
    log.info(f"Approved automatically: {rel}")


def _procesar_aprobados() -> None:
    for archivo in SANDBOX_APROBADOS.glob("*.py"):
        rel = archivo.name
        prod_path = PRODUCCION / rel

        if prod_path.exists():
            backup_path = BACKUP / f"{rel}.{datetime.now(UTC).strftime('%Y%m%d_%H%M')}"
            shutil.copy2(str(prod_path), str(backup_path))
            log.info(f"Backup: {rel} → backup_versiones")

        nuevo_hash = md5(archivo)
        shutil.move(str(archivo), str(prod_path))
        actualizar_inventario(rel, nuevo_hash, "auto_aprobado")
        inv = cargar_inventario()
        v_old = inv["archivos"].get(rel, {}).get("version", "unknown") if rel in inv.get("archivos", {}) else "unknown"
        create_branch(
            rel,
            v_old,
            "auto_aprobado",
            "agente_sandbox",
            "Automatic non-critical change",
        )
        log.info(f"Production updated: {rel}")
        pushover(f"Change applied in production: {rel}")


def main() -> None:
    log.info("Sandbox agent started (mixed mode)")
    pushover("Sandbox code agent started on GX10", "URA Sandbox")

    while True:
        pending_files = list(SANDBOX_PENDIENTES.glob("*.py"))
        for archivo in pending_files:
            rel = archivo.name
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

            pruebas_path = SANDBOX_EN_PRUEBAS / archivo.name
            shutil.move(str(archivo), str(pruebas_path))
            log.info(f"New change: {rel_path} → en_pruebas")

            ok, err = _probar_compilacion(pruebas_path)
            if not ok:
                _rechazar_cambio(pruebas_path, archivo, rel_path, err)
                continue

            if es_critico(rel_path):
                _esperar_aprobacion(pruebas_path, archivo, rel_path)
            else:
                _aprobar_cambio(pruebas_path, archivo, rel_path)

        _procesar_aprobados()
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
