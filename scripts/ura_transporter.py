#!/usr/bin/env python3
"""
URA Transporter — Localiza y transporta programas/agentes/pantallas desde la Bóveda.
Uso:
    python3 ura_transporter.py --list
    python3 ura_transporter.py --find "agente"
    python3 ura_transporter.py --copy <id> --to <ruta>
    python3 ura_transporter.py --move <id> --to <ruta>
    python3 ura_transporter.py --send <id> --to <host>
    python3 ura_transporter.py --dry-run
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("REPO_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
INVENTORY_PATH = REPO_ROOT / "config" / "network_inventory.json"
REGISTRY_URL = "http://127.0.0.1:5100/agents"


# ---------------------------------------------------------------------------
def load_inventory():
    try:
        import requests

        r = requests.get(REGISTRY_URL, timeout=3)
        if r.ok:
            data = r.json()
            if data:
                return data
            else:
                print("ℹ️  Registry activo pero sin agentes registrados.")
                return []
    except Exception:
        pass
    if INVENTORY_PATH.exists():
        with open(INVENTORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("agents", [])
    return []


LOCK_FILE = "/tmp/ura_transporter.lock"


def save_inventory(agents):
    import fcntl

    with open(LOCK_FILE, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
    existing = {}
    if INVENTORY_PATH.exists():
        with open(INVENTORY_PATH, encoding="utf-8") as f:
            existing = json.load(f)
    existing["agents"] = agents
    with open(INVENTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


# ---------------------------------------------------------------------------
def find_items(inventory, query):
    return [
        item
        for item in inventory
        if query.lower() in str(item.get("id", "")).lower()
        or query.lower() in str(item.get("name", "")).lower()
    ]


# ---------------------------------------------------------------------------
def copy_item(item, destination, dry_run=False):
    source = item.get("path") or item.get("source")
    if not source:
        print(f"🔴 '{item.get('id')}' no tiene ruta de origen.")
        return False
    source_path = Path(source)
    dest_path = Path(destination) / source_path.name
    if not source_path.exists():
        print(f"🔴 Origen no encontrado: {source_path}")
        return False
    if dry_run:
        print(f"🔍 [DRY-RUN] Copiaría: {source_path} → {dest_path}")
        return True
    shutil.copy2(source_path, dest_path)
    print(f"✅ Copiado: {source_path} → {dest_path}")
    return True


def move_item(item, destination, dry_run=False):
    if copy_item(item, destination, dry_run):
        source = Path(item.get("path", ""))
        if not dry_run and source.exists():
            source.unlink()
            print(f"✅ Original eliminado: {source}")
            item["path"] = str(Path(destination) / source.name)
        return True
    return False


# ---------------------------------------------------------------------------
def send_via_scp(item, host, destination="~/inbox_ura/", dry_run=False):
    source = item.get("path") or item.get("source")
    if not source:
        print(f"🔴 '{item.get('id')}' no tiene ruta de origen.")
        return False
    source_path = Path(source)
    if not source_path.exists():
        print(f"🔴 Origen no encontrado: {source_path}")
        return False
    dest = f"{host}:{destination}"
    if dry_run:
        print(f"🔍 [DRY-RUN] Enviaría: {source_path} → {dest}")
        return True
    result = subprocess.run(["scp", str(source_path), dest], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Enviado: {source_path} → {dest}")
        return True
    else:
        print(f"🔴 Error SCP: {result.stderr}")
        return False


# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="URA Transporter")
    parser.add_argument("--list", action="store_true", help="Listar elementos")
    parser.add_argument("--find", type=str, help="Buscar por nombre o ID")
    parser.add_argument("--copy", type=str, help="Copiar elemento por ID")
    parser.add_argument("--move", type=str, help="Mover elemento por ID")
    parser.add_argument("--send", type=str, help="Enviar vía SCP")
    parser.add_argument("--to", type=str, help="Ruta destino (carpeta o host)")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin ejecutar")
    args = parser.parse_args()

    inventory = load_inventory()
    # Auto-registro de heartbeat del Transporter
    try:
        import requests as req
        import datetime

        req.post(
            "http://127.0.0.1:5100/agents",
            json={
                "id": "transporter",
                "type": "utilidad",
                "ip": "127.0.0.1",
                "port": 0,
                "last_seen": datetime.datetime.utcnow().isoformat(),
            },
            timeout=3,
        )
    except Exception:
        pass
    dry_run = args.dry_run

    if args.list:
        print("\n📋 Elementos registrados:")
        print("=" * 60)
        if not inventory:
            print("  (No hay elementos registrados)")
        for item in inventory:
            print(
                f"  ID: {item.get('id')} | Tipo: {item.get('type', '?')} | Ruta: {item.get('path', '?')}"
            )
        print("=" * 60)
        return

    if args.find:
        results = find_items(inventory, args.find)
        if results:
            print(f"\n🔍 Resultados para '{args.find}':")
            for item in results:
                print(
                    f"  ID: {item.get('id')} | Tipo: {item.get('type', '?')} | Ruta: {item.get('path', '?')}"
                )
        else:
            print(f"🔍 Sin resultados para '{args.find}'.")
        return

    target_id = args.copy or args.move or args.send
    if not target_id:
        print("🔴 Especifica --copy, --move o --send.")
        sys.exit(1)

    item = next((i for i in inventory if i.get("id") == target_id), None)
    if not item:
        print(f"🔴 ID '{target_id}' no encontrado.")
        sys.exit(1)

    if not args.to:
        print("🔴 Falta --to <ruta>")
        sys.exit(1)

    if args.copy:
        copy_item(item, args.to, dry_run)
        if not dry_run:
            save_inventory(inventory)
    elif args.move:
        move_item(item, args.to, dry_run)
        if not dry_run:
            save_inventory(inventory)
    elif args.send:
        send_via_scp(item, args.to, dry_run=dry_run)


if __name__ == "__main__":
    main()
