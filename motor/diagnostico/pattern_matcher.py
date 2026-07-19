import logging

log = logging.getLogger("ura.diagnostico.pattern")


def buscar_patrones(scan, qdrant, circuit_breaker, config) -> tuple:  # noqa: C901, PLR0912
    """Busca patrones de incidente en el resultado del escaneo."""
    incidentes = []
    for svc, estado in scan.servicios.items():
        if estado in ("inactive", "failed"):
            incidentes.append(
                {
                    "tipo": "ServiceFailure",
                    "subtipo": svc,
                    "resumen": f"{svc} {estado}",
                    "ts": scan.timestamp,
                },
            )
    if scan.recursos.get("ram_pct", 0) > 90:
        incidentes.append(
            {
                "tipo": "ResourcePressure",
                "subtipo": "ram",
                "resumen": f"RAM al {scan.recursos['ram_pct']}%",
                "ts": scan.timestamp,
            },
        )
    if scan.recursos.get("disk_pct", 0) > 85:
        incidentes.append(
            {
                "tipo": "ResourcePressure",
                "subtipo": "disco",
                "resumen": f"Disco al {scan.recursos['disk_pct']}%",
                "ts": scan.timestamp,
            },
        )
    load = scan.recursos.get("load_1m", 0)
    ncpu = scan.recursos.get("ncpu", 1)
    if ncpu > 0 and load / ncpu > 2.0:
        incidentes.append(
            {
                "tipo": "ResourcePressure",
                "subtipo": "cpu",
                "resumen": f"Load avg {load} > {ncpu * 2}x CPUs",
                "ts": scan.timestamp,
            },
        )
    dmesg = scan.hw_health.get("dmesg_errors", [])
    if dmesg:
        incidentes.append(
            {
                "tipo": "HardwareFailure",
                "subtipo": "dmesg",
                "resumen": f"Errores dmesg: {dmesg[:3]}",
                "ts": scan.timestamp,
                "hw_issues": dmesg,
            },
        )
    if scan.hw_health.get("journal_corrupt", 0) > 0:
        incidentes.append(
            {
                "tipo": "HardwareFailure",
                "subtipo": "journal",
                "resumen": f"Corrupción journal: {scan.hw_health['journal_corrupt']} entradas",
                "ts": scan.timestamp,
            },
        )
    if not scan.red.get("internet", True):
        incidentes.append(
            {
                "tipo": "NetworkTopologyFailure",
                "subtipo": "sin_internet",
                "resumen": "Sin salida a internet",
                "ts": scan.timestamp,
            },
        )
    if not scan.red.get("exit_node_online", True):
        incidentes.append(
            {
                "tipo": "NetworkTopologyFailure",
                "subtipo": "exit_node_offline",
                "resumen": "Exit node caído",
                "ts": scan.timestamp,
            },
        )
    if scan.contenedores_ko:
        incidentes.append(
            {
                "tipo": "ServiceFailure",
                "subtipo": "docker",
                "resumen": f"Contenedores no running: {scan.contenedores_ko}",
                "ts": scan.timestamp,
            },
        )
    if scan.duplicados:
        incidentes.append(
            {
                "tipo": "ConfigConflict",
                "subtipo": "procesos_duplicados",
                "resumen": f"Procesos duplicados: {scan.duplicados}",
                "ts": scan.timestamp,
            },
        )
    if not scan.hw_health.get("ok", True):
        incidentes.append(
            {
                "tipo": "HardwareFailure",
                "subtipo": "vm" if scan.hw_health.get("tipo") == "vm" else "fisico",
                "resumen": f"Issues HW: {scan.hw_health.get('issues', [])}",
                "ts": scan.timestamp,
                "hw_issues": scan.hw_health.get("issues", []),
            },
        )
    if scan.flapping:
        incidentes.append(
            {
                "tipo": "ServiceFailure",
                "subtipo": "flapping",
                "resumen": f"Servicios flapping: {scan.flapping}",
                "ts": scan.timestamp,
            },
        )
    if scan.diff_total > 0:
        incidentes.append(
            {
                "tipo": "ConfigConflict",
                "subtipo": "cambios_detectados",
                "resumen": f"Diff score: {scan.diff_total}",
                "ts": scan.timestamp,
                "anomalias": scan.anomalias,
            },
        )
    costes = _calcular_costes_historicos(incidentes)
    return incidentes, costes


def _calcular_costes_historicos(incidentes: list) -> dict:
    """Cuenta frecuencias de tipos/subtipos de incidentes."""
    costes = {}
    for inc in incidentes:
        t = inc.get("tipo", "Unknown")
        sub = inc.get("subtipo", "")
        clave = f"{t}.{sub}" if sub else t
        entry = costes.get(clave, {"veces": 0})
        entry["veces"] += 1
        costes[clave] = entry
    return costes
