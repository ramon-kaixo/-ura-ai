import json, logging
from pathlib import Path

log = logging.getLogger("ura.diagnostico.pattern")

def buscar_patrones(scan, qdrant, circuit_breaker, config) -> tuple:
    incidentes = []
    costes = {}
    for svc, estado in scan.servicios.items():
        if estado in ("inactive", "failed"):
            incidentes.append({
                "tipo": "ServiceFailure",
                "subtipo": svc,
                "resumen": f"{svc} {estado}",
                "ts": scan.timestamp,
            })
    if scan.recursos.get("ram_pct", 0) > 90:
        incidentes.append({
            "tipo": "ResourcePressure",
            "subtipo": "ram",
            "resumen": f"RAM al {scan.recursos['ram_pct']}%",
            "ts": scan.timestamp,
        })
    if scan.recursos.get("disk_pct", 0) > 85:
        incidentes.append({
            "tipo": "ResourcePressure",
            "subtipo": "disco",
            "resumen": f"Disco al {scan.recursos['disk_pct']}%",
            "ts": scan.timestamp,
        })
    if not scan.red.get("internet", True):
        incidentes.append({
            "tipo": "NetworkTopologyFailure",
            "subtipo": "sin_internet",
            "resumen": "Sin salida a internet",
            "ts": scan.timestamp,
        })
    if not scan.red.get("exit_node_online", True) and not scan.red.get("internet", True):
        incidentes.append({
            "tipo": "NetworkTopologyFailure",
            "subtipo": "exit_node_offline",
            "resumen": "Exit node caído + sin internet",
            "ts": scan.timestamp,
        })
    if scan.duplicados:
        incidentes.append({
            "tipo": "ConfigConflict",
            "subtipo": "procesos_duplicados",
            "resumen": f"Procesos duplicados: {scan.duplicados}",
            "ts": scan.timestamp,
        })
    if not scan.hw_health.get("ok", True):
        incidentes.append({
            "tipo": "HardwareFailure",
            "subtipo": "vm" if scan.hw_health.get("tipo") == "vm" else "fisico",
            "resumen": f"Issues HW: {scan.hw_health.get('issues', [])}",
            "ts": scan.timestamp,
            "hw_issues": scan.hw_health.get("issues", []),
        })
    costes = _calcular_costes_historicos(incidentes)
    return incidentes, costes

def _calcular_costes_historicos(incidentes: list) -> dict:
    costes = {}
    for inc in incidentes:
        t = inc.get("tipo", "Unknown")
        sub = inc.get("subtipo", "")
        clave = f"{t}.{sub}" if sub else t
        costes[clave] = costes.get(clave, {"media_h": 0, "veces": 0, "total_h": 0})
        costes[clave]["veces"] += 1
    for k in costes:
        costes[k]["media_h"] = round(costes[k]["total_h"] / costes[k]["veces"], 1) if costes[k]["veces"] else 0
    return costes
