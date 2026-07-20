#!/usr/bin/env python3
"""openclaw_firmador.py — Agente-Firmador BLAKE2b (Protocolo de Control de Inodos).

Principios:
  1. FIRMA: Toda modificacion de archivo genera firma BLAKE2b (digest_size=8)
  2. SINGLE-PASS: La verificacion se hace en el mismo flujo de lectura (cero latencia)
  3. NOTARIO: El Guardian valida HASH(archivo) == HASH_INDEXADO contra .nervioso/
  4. ABORTAJE: Si la invariante falla → SIGKILL + git checkout . + .refactor_blocked
  5. MAESTRO: Solo se opera sobre is_master:true. Duplicados y zombies ignorados.

Uso:
  from openclaw_firmador import sign, verify, load_index, validate_invariant
"""

import contextlib
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

URA_ROOT = Path(os.environ.get("URA_ROOT", Path("~/URA/ura_ia_1972").expanduser()))
NERVIOSO = URA_ROOT / ".nervioso"
MAP_FILE = NERVIOSO / "sistema_map.json"

_index_cache: dict | None = None
_cache_mtime: float = 0


def sign(file_path: str | Path) -> str:
    """Firma un archivo con BLAKE2b (8 bytes). Retorna hex digest."""
    h = hashlib.blake2b(digest_size=8)
    path = Path(file_path)
    with open(path, "rb") as f:  # noqa: PTH123
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def sign_content(content: str | bytes) -> str:
    """Firma contenido en memoria (sin leer disco)."""
    h = hashlib.blake2b(digest_size=8)
    if isinstance(content, str):
        content = content.encode("utf-8")
    h.update(content)
    return h.hexdigest()


def load_index(force_reload: bool = False) -> dict[str, Any]:
    """Carga .nervioso/sistema_map.json en memoria (cacheado).
    Single-Pass: primera llamada carga, siguientes devuelven cache.
    Si el archivo cambio en disco → recarga automatica.
    """
    global _index_cache, _cache_mtime  # noqa: PLW0603

    if not MAP_FILE.exists():
        return {}

    mtime = MAP_FILE.stat().st_mtime
    if not force_reload and _index_cache is not None and mtime == _cache_mtime:
        return _index_cache

    _index_cache = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    _cache_mtime = mtime
    return _index_cache


def get_node(rel_path: str) -> dict | None:
    """Obtiene el nodo del grafo para una ruta relativa."""
    index = load_index()
    return index.get("dependency_graph", {}).get(rel_path)


def is_master(rel_path: str) -> bool:
    """Verifica si el archivo es el nodo maestro (no duplicado)."""
    node = get_node(rel_path)
    return node.get("is_master", True) if node else True


def is_zombie(rel_path: str) -> bool:
    """Verifica si el archivo es un zombie (sin imports)."""
    node = get_node(rel_path)
    if not node:
        return False
    return "ZOMBIE" in node.get("pipeline_state", "")


def is_duplicate(rel_path: str) -> bool:
    """Verifica si el archivo es un duplicado de otro."""
    node = get_node(rel_path)
    if not node:
        return False
    return "ESPEJO" in node.get("pipeline_state", "")


def validate_invariant(file_path: str | Path, content: str | bytes | None = None) -> bool:
    """Predicado: HASH(archivo) == HASH_INDEXADO.
    Si content no es None → firma en memoria (Single-Pass, sin leer disco).
    Si content es None → firma desde disco.
    """
    path = Path(file_path)
    rel = str(path.relative_to(URA_ROOT)) if str(path).startswith(str(URA_ROOT)) else str(path)

    node = get_node(rel)
    if not node:
        return True  # sin nodo en el index → no podemos verificar, asumimos OK

    expected_hash = node.get("checksum_blake2b_8")
    if not expected_hash:
        return True  # sin hash en el index

    actual_hash = sign_content(content) if content is not None else sign(path)

    return actual_hash == expected_hash


def validate_and_abort(file_path: str | Path, worker_pid: int | None = None) -> bool:
    """Valida invariante. Si falla → ABORTAJE DE EMERGENCIA."""
    if validate_invariant(file_path):
        return True

    motivo = f"Invariante rota en {file_path}: HASH(archivo) != HASH_INDEXADO"
    _abortaje_emergencia(motivo, worker_pid)
    return False


def update_index_node(rel_path: str, new_hash: str, new_size: int) -> None:
    """Actualiza el hash y size de un nodo en el index (post-modificacion)."""
    global _index_cache  # noqa: PLW0603

    index = load_index(force_reload=True)
    deps = index.get("dependency_graph", {})
    node = deps.get(rel_path)
    if node:
        node["checksum_blake2b_8"] = new_hash
        node["allocation_bytes"] = new_size
        import time

        node["posix_timestamps"] = {
            "st_mtime": int(time.time()),
            "st_atime": int(time.time()),
        }
        MAP_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False))
        _index_cache = index
        _cache_mtime = MAP_FILE.stat().st_mtime


def _abortaje_emergencia(motivo: str, worker_pid: int | None = None) -> None:
    """Protocolo de mitigacion atomico."""
    import subprocess

    # Escribir flag de bloqueo
    (URA_ROOT / ".refactor_blocked").write_text(motivo)

    # Matar workers
    try:
        if worker_pid:
            os.kill(worker_pid, 9)
    except Exception:  # noqa: S110
        pass

    with contextlib.suppress(Exception):
        subprocess.run(["pkill", "-9", "-f", "large_functions.py"], capture_output=True, timeout=5, check=False)  # noqa: S607

    # Registrar en audit trail
    audit_log = NERVIOSO / "audit_trail.log"
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    import time as _time

    with open(audit_log, "a") as f:  # noqa: PTH123
        f.write(f"[{_time.strftime('%Y-%m-%dT%H:%M:%S')}] | EMERGENCY_ABORT | {motivo}\n")

    # TTS alert
    with contextlib.suppress(Exception):
        subprocess.run(
            ["say", "-v", "Jorge", "Alerta. Integridad del código comprometida."],  # noqa: S607
            capture_output=True,
            timeout=5,
            check=False,
        )


def sign_and_verify_write(file_path: str | Path, new_content: str) -> tuple[bool, str]:
    """Single-Pass: firma el contenido nuevo, verifica contra index, escribe a disco.
    Retorna (ok, firma).
    """
    path = Path(file_path)
    new_hash = sign_content(new_content)

    # Verificar invariante ANTES de escribir (Single-Pass: ya tenemos el hash en memoria)
    if not validate_invariant(path, new_content):
        return False, new_hash

    # Escribir a disco
    path.write_text(new_content, encoding="utf-8")

    # Actualizar index
    rel = str(path.relative_to(URA_ROOT)) if str(path).startswith(str(URA_ROOT)) else str(path)
    new_size = len(new_content.encode("utf-8"))
    update_index_node(rel, new_hash, new_size)

    return True, new_hash


def sign_and_verify_write_bytes(file_path: str | Path, new_content: str) -> bool:
    """Version simplificada: solo retorna True/False."""
    ok, _ = sign_and_verify_write(file_path, new_content)
    return ok


# ─── PROTOCOLO DE MARCAS DE AGUA (Checkpointing) ───────────────


def checkpoint_update(rel_path: str, line: int, total_lines: int, worker_id: int = 0) -> None:
    """Actualiza la marca de agua en .nervioso/sistema_map.json.
    Registra la ultima linea procesada, total, timestamp, worker y estado.
    """
    global _index_cache  # noqa: PLW0603

    index = load_index(force_reload=True)
    node = index.get("dependency_graph", {}).get(rel_path)
    if not node:
        return

    import time as _t

    node["checkpoint_line"] = line
    node["checkpoint_total_lines"] = total_lines
    node["checkpoint_timestamp"] = datetime.fromtimestamp(_t.time(), tz=_t.timezone.utc).isoformat()
    node["checkpoint_worker"] = worker_id
    node["checkpoint_state"] = "completado" if line >= total_lines else "en_curso"

    MAP_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    _index_cache = index
    _cache_mtime = MAP_FILE.stat().st_mtime


def checkpoint_get(rel_path: str) -> dict | None:
    """Obtiene los datos de checkpoint de un archivo."""
    node = get_node(rel_path)
    if not node or "checkpoint_line" not in node:
        return None
    return {
        "line": node.get("checkpoint_line", 0),
        "total": node.get("checkpoint_total_lines", 0),
        "timestamp": node.get("checkpoint_timestamp"),
        "worker": node.get("checkpoint_worker", 0),
        "state": node.get("checkpoint_state", "virgen"),
    }


def reportar_estado_tierra() -> str:
    """Informe de Situacion: progreso del tunel, archivos pendientes, riesgos."""
    index = load_index(force_reload=True)
    deps = index.get("dependency_graph", {})

    total_archivos = len(deps)
    completados = 0
    en_curso = 0
    virgenes = 0
    fallidos = 0
    lineas_procesadas = 0
    lineas_totales = 0
    archivo_en_curso = "ninguno"
    linea_en_curso = "?"
    total_en_curso = "?"

    for rel, node in deps.items():
        state = node.get("checkpoint_state", "virgen")
        cp_line = node.get("checkpoint_line", 0)
        cp_total = node.get("checkpoint_total_lines", 0)

        lineas_procesadas += cp_line
        lineas_totales += cp_total if cp_total > 0 else node.get("allocation_bytes", 0) // 60

        if state == "completado":
            completados += 1
        elif state == "en_curso":
            en_curso += 1
            archivo_en_curso = rel
            linea_en_curso = str(cp_line)
            total_en_curso = str(cp_total)
        elif state == "fallido":
            fallidos += 1
        else:
            virgenes += 1

    pct_lineas = (lineas_procesadas / max(lineas_totales, 1)) * 100
    pct_archivos = (completados / max(total_archivos, 1)) * 100

    report = (
        f"📊 ESTADO DE TIERRA — {datetime.now(UTC).isoformat()[:19]}\n"
        f"{'─' * 60}\n"
        f"  Lineas procesadas:  {lineas_procesadas:,} / ~{lineas_totales:,} ({pct_lineas:.1f}%)\n"
        f"  Archivos completados: {completados} / {total_archivos} ({pct_archivos:.1f}%)\n"
        f"  Archivos en curso:   {en_curso}"
    )
    if archivo_en_curso != "ninguno":
        report += f" ({archivo_en_curso}: linea {linea_en_curso}/{total_en_curso})"
    report += f"\n  Archivos virgenes:   {virgenes}\n  Archivos con fallo:  {fallidos}\n{'─' * 60}\n"
    if fallidos > 0:
        report += f"  ⚠️  RIESGO: {fallidos} archivos con checkpoint fallido\n"

    return report


# ─── DELTA-CHECK — Solo procesar lo modificado ──────────────────


DELTA_SNAPSHOT_DIR = NERVIOSO / "delta_snapshots"


def delta_snapshot(label: str = "ultimo_ciclo") -> str:
    """Guarda snapshot de hashes actuales para comparacion futura."""
    DELTA_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    index = load_index()
    deps = index.get("dependency_graph", {})

    snapshot = {}
    for rel, node in deps.items():
        state = node.get("pipeline_state", "")
        if "ESPEJO" in state or "ZOMBIE" in state:
            continue
        snapshot[rel] = {
            "blake2b": node.get("checksum_blake2b_8", ""),
            "size": node.get("allocation_bytes", 0),
            "mtime": node.get("posix_timestamps", {}).get("st_mtime", 0),
        }

    path = DELTA_SNAPSHOT_DIR / f"{label}.json"
    path.write_text(
        json.dumps(
            {"label": label, "files": snapshot, "timestamp": datetime.now(UTC).isoformat()},
            indent=2,
        ),
    )
    return str(path)


def delta_check(label: str = "ultimo_ciclo") -> tuple[list[str], list[str], list[str]]:
    """Compara sistema_map.json actual contra un snapshot anterior.
    Retorna (modificados, nuevos, eliminados).
    Solo archivos con hash diferente → necesitan re-procesarse.
    """
    path = DELTA_SNAPSHOT_DIR / f"{label}.json"
    if not path.exists():
        return [], [], []

    try:
        prev = json.loads(path.read_text()).get("files", {})
    except (json.JSONDecodeError, KeyError):
        return [], [], []

    index = load_index(force_reload=True)
    deps = index.get("dependency_graph", {})

    modificados = []
    nuevos = []
    eliminados = []

    current_keys = set()
    for rel, node in deps.items():
        state = node.get("pipeline_state", "")
        if "ESPEJO" in state or "ZOMBIE" in state:
            continue
        current_keys.add(rel)
        cur_hash = node.get("checksum_blake2b_8", "")
        prev_node = prev.get(rel, {})

        if rel not in prev:
            nuevos.append(rel)
        elif prev_node.get("blake2b", "") != cur_hash:
            modificados.append(rel)

    for rel in prev:
        if rel not in current_keys:
            eliminados.append(rel)  # noqa: PERF401

    return modificados, nuevos, eliminados


def aplicar_delta_check() -> dict:
    """Ejecuta delta check completo y retorna resumen."""
    modificados, nuevos, eliminados = delta_check()

    total_cambio = len(modificados) + len(nuevos) + len(eliminados)
    index = load_index()
    total_activos = sum(
        1
        for n in index.get("dependency_graph", {}).values()
        if "ESPEJO" not in n.get("pipeline_state", "") and "ZOMBIE" not in n.get("pipeline_state", "")
    )

    return {
        "total_activos": total_activos,
        "modificados": len(modificados),
        "nuevos": len(nuevos),
        "eliminados": len(eliminados),
        "sin_cambios": total_activos - total_cambio,
        "necesitan_procesar": total_cambio,
        "pct_ahorro": round((total_activos - total_cambio) / max(total_activos, 1) * 100, 1),
    }
