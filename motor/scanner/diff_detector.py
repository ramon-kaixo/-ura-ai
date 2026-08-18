import logging

log = logging.getLogger("ura.scanner.diff")


def compute_diff(actual: dict, prev: dict) -> tuple:
    """Compara dos snapshots y devuelve (diff_count, anomalias)."""
    count = 0
    anomalias = []
    for key in prev:
        if key not in actual:
            continue
        if isinstance(prev[key], dict) and isinstance(actual[key], dict):
            for subkey in set(list(prev[key].keys()) + list(actual[key].keys())):
                v_old = prev[key].get(subkey)
                v_new = actual[key].get(subkey)
                if v_old != v_new:
                    count += 1
                    if _es_critico(key, subkey, v_old, v_new):
                        anomalias.append(f"{key}.{subkey}: {v_old} -> {v_new}")
    return count, anomalias


def _es_critico(cat: str, sub: str, old, new) -> bool:
    """Determina si un cambio es crítico (servicio caído, recurso alto, HW fail)."""
    if cat == "servicios" and new in ("inactive", "failed", "unknown"):
        return True
    if cat == "recursos":
        if sub in ("ram_pct", "disk_pct") and isinstance(new, (int, float)) and new > 90:
            return True
        if sub == "zombies" and isinstance(new, int) and new > 0:
            return True
    return bool(cat == "hw_health" and sub == "ok" and new is False)
