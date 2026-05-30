"""
AGENTE SUPERVISOR - Monitoriza TODO lo que pasa en URA
"""

import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

import psutil

DB_PATH = Path(__file__).parent.parent / "board.db"


def supervisar_todo():
    """Hace supervisión completa del sistema"""
    supervisado = {
        "timestamp": datetime.now().isoformat(),
        "sistema": {},
        "servicios": {},
        "agentes": {},
        "tareas": {},
        "alertas": [],
    }

    # 1. Sistema
    cpu = psutil.cpu_percent(interval=1)
    memoria = psutil.virtual_memory()
    disco = psutil.disk_usage("/")

    supervisado["sistema"] = {
        "cpu": cpu,
        "memoria_pct": memoria.percent,
        "disco_pct": disco.percent,
        "procesos": len(psutil.pids()),
    }

    # 2. Servicios
    supervisado["servicios"] = verificar_servicios()

    # 3. Agentes activos
    supervisado["agentes"] = contar_agentes()

    # 4. Tareas
    supervisado["tareas"] = estado_tareas()

    # 5. Alertas
    supervisado["alertas"] = generar_alertas(supervisado)

    # Guardar en BD
    guardar_supervision(supervisado)

    return supervisado


def verificar_servicios():
    """Verifica servicios críticos"""
    servicios = {}

    # Autonomy loop
    result = subprocess.run(["pgrep", "-f", "autonomia_loop"], capture_output=True)
    servicios["autonomy_loop"] = "OK" if result.returncode == 0 else "PARADO"

    # Orchestrator
    result = subprocess.run(["pgrep", "-f", "orchestrator"], capture_output=True)
    servicios["orchestrator"] = "OK" if result.returncode == 0 else "PARADO"

    # Ollama
    result = subprocess.run(["pgrep", "-f", "ollama"], capture_output=True)
    servicios["ollama"] = "OK" if result.returncode == 0 else "PARADO"

    return servicios


def contar_agentes():
    """Cuenta agentes activos"""
    agentes_path = Path(__file__).parent.parent / "agents"

    total = len(list(agentes_path.glob("agente_*.py")))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("SELECT COUNT(*) FROM agentes_instalados WHERE estado='activo'")
        activos = c.fetchone()[0]
    except:
        activos = 0

    conn.close()

    return {"total": total, "activos": activos}


def estado_tareas():
    """Estado de tareas"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("SELECT COUNT(*), estado FROM tasks GROUP BY estado")
        tareas = {r[1]: r[0] for r in c.fetchall()}
    except:
        tareas = {}

    conn.close()
    return tareas


def generar_alertas(supervisado):
    """Genera alertas basadas en supervisión"""
    alertas = []

    # CPU alto
    if supervisado["sistema"]["cpu"] > 90:
        alertas.append(
            {
                "tipo": "CPU",
                "mensaje": f"CPU al {supervisado['sistema']['cpu']}%",
                "nivel": "critico",
            }
        )

    # Memoria alta
    if supervisado["sistema"]["memoria_pct"] > 90:
        alertas.append(
            {
                "tipo": "MEMORIA",
                "mensaje": f"Memoria al {supervisado['sistema']['memoria_pct']}%",
                "nivel": "critico",
            }
        )

    # Disco bajo
    if supervisado["sistema"]["disco_pct"] > 90:
        alertas.append(
            {
                "tipo": "DISCO",
                "mensaje": f"Disco al {supervisado['sistema']['disco_pct']}%",
                "nivel": "critico",
            }
        )

    # Servicios parados
    for servicio, estado in supervisado["servicios"].items():
        if estado == "PARADO":
            alertas.append(
                {"tipo": "SERVICIO", "mensaje": f"{servicio} PARADO", "nivel": "critico"}
            )

    # Guardar alertas
    if alertas:
        guardar_alertas(alertas)

    return alertas


def guardar_supervision(datos):
    """Guarda datos de supervisión"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS supervisiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            cpu REAL,
            memoria_pct REAL,
            disco_pct REAL,
            servicios TEXT,
            agentes_total INTEGER,
            alertas_count INTEGER
        )
    """)

    c.execute(
        """
        INSERT INTO supervisiones
        (timestamp, cpu, memoria_pct, disco_pct, servicios, agentes_total, alertas_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            datos["timestamp"],
            datos["sistema"]["cpu"],
            datos["sistema"]["memoria_pct"],
            datos["sistema"]["disco_pct"],
            str(datos["servicios"]),
            datos["agentes"]["total"],
            len(datos["alertas"]),
        ),
    )

    conn.commit()
    conn.close()


def guardar_alertas(alertas):
    """Guarda alertas"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS alertas_supervisor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            tipo TEXT,
            mensaje TEXT,
            nivel TEXT,
            leida INTEGER DEFAULT 0
        )
    """)

    for alerta in alertas:
        c.execute(
            """
            INSERT INTO alertas_supervisor (timestamp, tipo, mensaje, nivel)
            VALUES (?, ?, ?, ?)
        """,
            (datetime.now().isoformat(), alerta["tipo"], alerta["mensaje"], alerta["nivel"]),
        )

    conn.commit()
    conn.close()


def resumen_rapido():
    """Resumen rápido para CLI"""
    sup = supervisar_todo()

    lineas = [
        "╔═══════════════════════════════════════════╗",
        "║       URA - SUPERVISOR                    ║",
        "╠═══════════════════════════════════════════╣",
        f"║ CPU: {sup['sistema']['cpu']:.1f}%  RAM: {sup['sistema']['memoria_pct']:.1f}%  DISC: {sup['sistema']['disco_pct']:.1f}%     ║",
        "╠═══════════════════════════════════════════╣",
        "║ SERVICIOS:                                ║",
    ]

    for svc, estado in sup["servicios"].items():
        emoji = "✅" if estado == "OK" else "❌"
        lineas.append(f"║   {emoji} {svc}: {estado}                      ║")

    lineas.append("╠═══════════════════════════════════════════╣")
    lineas.append(
        f"║ AGENTES: {sup['agentes']['total']}  |  ALERTAS: {len(sup['alertas'])}                 ║"
    )
    lineas.append("╚═══════════════════════════════════════════╝")

    return "\n".join(lineas)


if __name__ == "__main__":
    print(resumen_rapido())
