"""Gestor de RAM inteligente para URA.

Tres responsabilidades:
  1) Leer la RAM disponible real en cada momento (free + inactive + speculative).
  2) Seleccionar el modelo de Ollama adecuado según esa métrica.
  3) Descargar el modelo con `ollama stop` tras un periodo de inactividad
     para devolver RAM al sistema. Se recarga automáticamente al próximo
     mensaje (coste: 2-4 s de primera respuesta).

No depende de psutil: usa `vm_stat` nativo de macOS + `sysctl vm.swapusage`.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Umbrales de selección de modelo (en GB disponibles)
MODEL_TINY = "qwen2.5:3b-instruct"
MODEL_SMALL = "llama3.2:3b"
MODEL_MEDIUM_14B = "qwen2.5:14b-instruct"
MODEL_MEDIUM_32B = "qwen2.5:32b-instruct"
MODEL_LARGE_70B = "llama3.1:70b"
MODEL_HUGE_72B = "qwen2.5:72b-instruct"

THRESHOLD_TINY_GB = 3.5  # por debajo: modelo tiny
THRESHOLD_SMALL_GB = 7.0  # por encima: modelo small
THRESHOLD_MEDIUM_14B_GB = 16.0  # por encima: modelo 14b
THRESHOLD_MEDIUM_32B_GB = 32.0  # por encima: modelo 32b
THRESHOLD_LARGE_70B_GB = 64.0  # por encima: modelo 70b
THRESHOLD_HUGE_72B_GB = 128.0  # por encima: modelo 72b

# Descarga por inactividad
IDLE_UNLOAD_SECONDS = 1800  # 30 min sin mensajes → ollama stop


@dataclass
class RamSnapshot:
    free_gb: float
    inactive_gb: float
    active_gb: float
    wired_gb: float
    compressor_gb: float
    swap_used_gb: float

    @property
    def available_gb(self) -> float:
        """RAM que el sistema puede entregar a un nuevo proceso sin penalización grave.
        Inactive es reclamable casi al instante; free es libre puro.
        """
        return self.free_gb + self.inactive_gb


def _run(cmd: list[str], timeout: int = 5) -> str:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        ).stdout
    except Exception as exc:
        logger.debug("cmd %s falló: %s", cmd, exc)
        return ""


def read_ram() -> RamSnapshot:
    """Lee vm_stat + swapusage y devuelve una snapshot en GB."""
    out = _run(["vm_stat"])
    page_size = 16384
    v = {"free": 0, "active": 0, "inactive": 0, "wired": 0, "compressor": 0, "speculative": 0}
    for line in out.splitlines():
        try:
            if "page size of" in line:
                # Pages free:  7091.  -> fallback si el vm_stat lo declara distinto
                page_size = int(line.split("page size of")[1].split("bytes")[0].strip())
            if line.startswith("Pages free:"):
                v["free"] = int(line.split()[2].rstrip("."))
            elif line.startswith("Pages active:"):
                v["active"] = int(line.split()[2].rstrip("."))
            elif line.startswith("Pages inactive:"):
                v["inactive"] = int(line.split()[2].rstrip("."))
            elif line.startswith("Pages speculative:"):
                v["speculative"] = int(line.split()[2].rstrip("."))
            elif line.startswith("Pages wired down:"):
                v["wired"] = int(line.split()[3].rstrip("."))
            elif "Pages occupied by compressor" in line:
                v["compressor"] = int(line.split()[4].rstrip("."))
        except (IndexError, ValueError):
            continue

    def to_gb(n):
        return n * page_size / (1024**3)

    swap_used = 0.0
    swap_out = _run(["sysctl", "vm.swapusage"])
    # vm.swapusage: total = 2048.00M  used = 721.00M  free = 1327.00M  (encrypted)
    for tok in swap_out.split():
        if tok.startswith("used"):
            pass
    # parser simple:
    try:
        idx = swap_out.find("used = ")
        if idx >= 0:
            seg = swap_out[idx + 7 :].split()[0]  # p.ej. 721.00M
            if seg.endswith("M"):
                swap_used = float(seg[:-1]) / 1024
            elif seg.endswith("G"):
                swap_used = float(seg[:-1])
            elif seg.endswith("K"):
                swap_used = float(seg[:-1]) / 1024 / 1024
    except (ValueError, IndexError):
        pass

    return RamSnapshot(
        free_gb=to_gb(v["free"] + v["speculative"]),
        inactive_gb=to_gb(v["inactive"]),
        active_gb=to_gb(v["active"]),
        wired_gb=to_gb(v["wired"]),
        compressor_gb=to_gb(v["compressor"]),
        swap_used_gb=swap_used,
    )


def pick_model_for_ram(snapshot: RamSnapshot | None = None) -> str:
    """Elige modelo según RAM disponible. No hay fallback a modelos de otras familias."""
    snap = snapshot or read_ram()
    available = snap.available_gb

    # Selección escalonada según RAM disponible
    if available >= THRESHOLD_HUGE_72B_GB:
        model = MODEL_HUGE_72B
    elif available >= THRESHOLD_LARGE_70B_GB:
        model = MODEL_LARGE_70B
    elif available >= THRESHOLD_MEDIUM_32B_GB:
        model = MODEL_MEDIUM_32B
    elif available >= THRESHOLD_MEDIUM_14B_GB:
        model = MODEL_MEDIUM_14B
    elif available >= THRESHOLD_SMALL_GB:
        model = MODEL_SMALL
    else:
        model = MODEL_TINY

    logger.info(
        "[ram_manager] disponible=%.2f GB (free=%.2f + inactive=%.2f), swap=%.2f GB → %s",
        available,
        snap.free_gb,
        snap.inactive_gb,
        snap.swap_used_gb,
        model,
    )
    return model


def current_loaded_model() -> str | None:
    """Devuelve el nombre del modelo cargado en Ollama, o None."""
    out = _run(["ollama", "ps"], timeout=5)
    for line in out.splitlines()[1:]:
        parts = line.split()
        if parts and parts[0] and not parts[0].startswith("NAME"):
            return parts[0]
    return None


def unload_model(model: str | None = None) -> bool:
    """`ollama stop <model>` — libera la RAM del modelo inmediatamente."""
    target = model or current_loaded_model()
    if not target:
        return False
    out = _run(["ollama", "stop", target], timeout=10)
    logger.info("[ram_manager] ollama stop %s → %s", target, (out or "ok").strip())
    return True


# ─────────────────────────────────────────────────────────────
# Rastreo de inactividad
# ─────────────────────────────────────────────────────────────
class ActivityTracker:
    """Mantiene el timestamp del último mensaje recibido."""

    def __init__(self):
        self._last = time.time()

    def touch(self) -> None:
        self._last = time.time()

    def idle_seconds(self) -> float:
        return time.time() - self._last


_TRACKER: ActivityTracker | None = None


def get_tracker() -> ActivityTracker:
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = ActivityTracker()
    return _TRACKER


def maybe_unload_if_idle(idle_threshold: int = IDLE_UNLOAD_SECONDS) -> bool:
    """Si llevamos > idle_threshold segundos sin mensaje, descargar modelo."""
    idle = get_tracker().idle_seconds()
    if idle < idle_threshold:
        return False
    loaded = current_loaded_model()
    if not loaded:
        return False
    logger.info("[ram_manager] %s cargado tras %.0fs de inactividad → descargar", loaded, idle)
    return unload_model(loaded)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    snap = read_ram()
    print(f"Free:        {snap.free_gb:.2f} GB")
    print(f"Inactive:    {snap.inactive_gb:.2f} GB  (reclaimable)")
    print(f"Active:      {snap.active_gb:.2f} GB")
    print(f"Wired:       {snap.wired_gb:.2f} GB")
    print(f"Compressor:  {snap.compressor_gb:.2f} GB")
    print(f"Swap used:   {snap.swap_used_gb:.2f} GB")
    print(f"DISPONIBLE:  {snap.available_gb:.2f} GB")
    print(f"\nModelo recomendado: {pick_model_for_ram(snap)}")
    loaded = current_loaded_model()
    print(f"Modelo cargado ahora: {loaded or '(ninguno)'}")
