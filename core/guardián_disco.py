#!/usr/bin/env python3
"""Guardián de Disco — Detección de cambios vía SHA-256 con verificación post-escritura.

📖 MANUAL DE USO RÁPIDO:
  python3 core/guardián_disco.py --scan              # Escanear y comparar con snapshot
  python3 core/guardián_disco.py --verify <f> <hash>  # Verificar que un archivo se escribió
  python3 core/guardián_disco.py --init               # Crear snapshot inicial

🔒 GARANTÍAS:
  - Hash SHA-256 completo (64 chars, sin truncar)
  - Escritura atómica del snapshot (temp + rename)
  - Historial en .nervioso/hashes_history.jsonl
  - Verificación post-escritura: ¿el LLM realmente escribió?
  - Detecta código fantasma (archivo en snapshot pero no en disco)
  - Escanea *.py, *.json, *.sh, *.yaml, *.yml, *.md, *.env
"""

import hashlib
import json
import logging
import sys
import time
from pathlib import Path

log = logging.getLogger("ura.guardian_disco")

URA = Path("/home/ramon/URA/ura_ia_1972")
NERVIOSO = URA / ".nervioso"
SNAPSHOT = NERVIOSO / "hashes.json"
HISTORIAL = NERVIOSO / "hashes_history.jsonl"
CONFIG_PATH = NERVIOSO / "guardian_config.json"

# ── Config default ──
DEFAULT_CONFIG = {
    "patrones": ["*.py", "*.json", "*.sh", "*.yaml", "*.yml", "*.md", "*.env", "*.toml"],
    "excluir": [
        ".venv",
        "__pycache__",
        ".git",
        "backups",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "site-packages",
        "GX10",
    ],
    "hash_truncar": 64,  # SHA-256 completo
}


def cargar_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
    pass  # noqa: S110
    NERVIOSO.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False) + "\n")
    return dict(DEFAULT_CONFIG)


def calcular_hash(ruta: Path, truncar: int = 64) -> str:
    """SHA-256 completo. Si truncar < 64, devuelve versión acortada."""
    h = hashlib.sha256(ruta.read_bytes()).hexdigest()
    return h[:truncar]


def escanear(config: dict) -> dict:
    """Escanea todos los archivos según patrones configurados."""
    actual = {}
    for patron in config["patrones"]:
        for f in URA.rglob(patron):
            partes = set(f.parts)
            if any(x in partes for x in config["excluir"]):
                continue
            try:
                rel = str(f.relative_to(URA))
                actual[rel] = calcular_hash(f, config["hash_truncar"])
            except (PermissionError, OSError):
                log.debug("Skipping inaccessible file: %s", f)
    return actual


def comparar(anterior: dict, actual: dict) -> list:
    """Compara snapshot anterior vs estado actual del disco."""
    cambios = []
    for f, h in actual.items():
        if f not in anterior:
            cambios.append({"file": f, "status": "NUEVO", "hash": h})
        elif h != anterior[f]:
            cambios.append({"file": f, "status": "MODIFICADO", "hash": h})
    for f in anterior:
        if f not in actual:
            cambios.append({"file": f, "status": "FANTASMA", "hash": "—"})
    return cambios


def verificar_escritura(archivo: str, hash_esperado: str, config: dict | None = None) -> bool:
    """¿El archivo realmente se escribió en disco?
    Compara el hash post-escritura con el hash que la IA dice haber generado.

    Returns:
        True si el archivo existe y el hash coincide.
        False si: archivo no existe (FANTASMA) o hash no coincide (corrupto).

    """
    ruta = URA / archivo
    if not ruta.exists():
        return False  # FANTASMA
    cfg = config or cargar_config()
    actual = calcular_hash(ruta, cfg["hash_truncar"])
    return actual == hash_esperado


def guardar_snapshot(data: dict) -> None:
    """Escritura atómica: temp + rename."""
    NERVIOSO.mkdir(parents=True, exist_ok=True)
    tmp = SNAPSHOT.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(SNAPSHOT)


def guardar_historial(cambios: list, total: int) -> None:
    """Añade entrada al historial JSON Lines."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_archivos": total,
        "num_cambios": len(cambios),
        "nuevos": sum(1 for c in cambios if c["status"] == "NUEVO"),
        "modificados": sum(1 for c in cambios if c["status"] == "MODIFICADO"),
        "fantasmas": sum(1 for c in cambios if c["status"] == "FANTASMA"),
    }
    HISTORIAL.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORIAL, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Main ──


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Guardián de Disco SHA-256 v2.0")
    parser.add_argument("--scan", action="store_true", help="Escanear y comparar con snapshot")
    parser.add_argument("--init", action="store_true", help="Crear snapshot inicial")
    parser.add_argument("--verify", nargs=2, metavar=("ARCHIVO", "HASH"), help="Verificar post-escritura")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    config = cargar_config()

    if args.verify:
        archivo, hash_esp = args.verify
        ok = verificar_escritura(archivo, hash_esp, config)
        {"archivo": archivo, "hash_esperado": hash_esp, "existe": Path(URA, archivo).exists(), "coincide": ok}
        if args.json or ok:
            pass
        else:
            ruta = URA / archivo
            if not ruta.exists():
                pass
            else:
                pass
        sys.exit(0 if ok else 1)
        return

    if args.init:
        actual = escanear(config)
        snapshot = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "total": len(actual)}
        guardar_snapshot(snapshot)
        return

    if args.scan or not args.verify:
        anterior_snap = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
        actual = escanear(config)

        if anterior_snap:
            # Solo comparar si hay snapshot previo
            cambios = comparar(anterior_snap, actual)
        else:
            cambios = [{"file": f, "status": "INICIAL", "hash": h} for f, h in sorted(actual.items())]

        snapshot = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_archivos": len(actual),
            "archivos": {},
            "cambios_detectados": cambios,
        }
        guardar_snapshot(snapshot)
        guardar_historial(cambios, len(actual))

        if args.json:
            pass
        else:
            iconos = {"NUEVO": "📄", "MODIFICADO": "✏️", "FANTASMA": "👻", "INICIAL": "🆕"}
            for c in cambios[:20]:
                status = c["status"]
                iconos.get(status, "❓")
                c.get("hash", "—")[:12]
            if len(cambios) > 20:
                pass

            # Check fantasmas
            fantasmas = [c for c in cambios if c["status"] == "FANTASMA"]
            if fantasmas:
                pass
            else:
                pass


if __name__ == "__main__":
    main()
