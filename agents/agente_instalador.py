"""
AGENTE INSTALADOR - Instala y desinstala componentes de URA
"""

import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"
URA_PATH = Path(__file__).parent.parent
AGENTS_PATH = URA_PATH / "agents"
LAUNCHAGENTS_PATH = Path.home() / "Library" / "LaunchAgents"


def instalar_agente(nombre_archivo):
    """Instala un agente en URA"""
    ruta_origen = AGENTS_PATH / nombre_archivo

    if not ruta_origen.exists():
        return {"error": f"No existe: {nombre_archivo}"}

    # Verificar que es un archivo Python válido
    try:
        with open(ruta_origen) as f:
            contenido = f.read()

        if "def " not in contenido:
            return {"error": "No parece un módulo Python válido"}

        # Registrar en BD
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS agentes_instalados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                archivo TEXT,
                estado TEXT DEFAULT 'activo',
                installed_at TEXT NOT NULL
            )
        """)

        c.execute(
            """
            INSERT OR REPLACE INTO agentes_instalados (nombre, archivo, installed_at)
            VALUES (?, ?, ?)
        """,
            (
                nombre_archivo.replace("agente_", "").replace(".py", ""),
                nombre_archivo,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        return {"success": True, "agente": nombre_archivo}

    except Exception as e:
        return {"error": str(e)}


def desinstalar_agente(nombre):
    """Desinstala un agente (lo marca como inactivo)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        UPDATE agentes_instalados
        SET estado='inactivo'
        WHERE nombre LIKE ?
    """,
        (f"%{nombre}%",),
    )

    conn.commit()
    conn.close()

    return {"success": True, "desactivado": nombre}


def instalar_launchagent(nombre_servicio, comando):
    """Instala un LaunchAgent"""
    PLIST_CONTENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.{nombre_servicio}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{comando}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>"""

    plist_path = LAUNCHAGENTS_PATH / f"com.ura.{nombre_servicio}.plist"

    with open(plist_path, "w") as f:
        f.write(PLIST_CONTENT)

    # Activar
    subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)

    return {"success": True, "servicio": str(plist_path)}


def listar_agentes_instalados():
    """Lista agentes instalados"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute(
            "SELECT nombre, archivo, estado, installed_at FROM agentes_instalados ORDER BY installed_at DESC"
        )
        agentes = c.fetchall()
        conn.close()
        return [{"nombre": r[0], "archivo": r[1], "estado": r[2], "fecha": r[3]} for r in agentes]
    except:
        conn.close()
        return []


def listar_servicios():
    """Lista servicios activos"""
    servicios = []

    for plist in LAUNCHAGENTS_PATH.glob("com.ura.*.plist"):
        servicios.append(plist.name)

    return servicios


def backup_ura():
    """Hace backup de URA"""
    backup_dir = URA_PATH / "backups" / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Copiar agentes
    agentes_backup = backup_dir / "agents"
    shutil.copytree(AGENTS_PATH, agentes_backup)

    # Copiar BD
    shutil.copy2(DB_PATH, backup_dir / "board.db")

    return {"success": True, "backup": str(backup_dir)}


def restaurar_backup(fecha):
    """Restaura un backup"""
    backup_path = URA_PATH / "backups" / f"backup_{fecha}"

    if not backup_path.exists():
        return {"error": f"No existe backup: {fecha}"}

    # Restaurar BD
    shutil.copy2(backup_path / "board.db", DB_PATH)

    return {"success": True, "restaurado": fecha}


if __name__ == "__main__":
    print("=== AGENTE INSTALADOR ===")
    print("\n📦 Agentes instalados:")
    for a in listar_agentes_instalados()[:5]:
        print(f"  - {a['nombre']} ({a['estado']})")

    print("\n🔧 Servicios:")
    for s in listar_servicios():
        print(f"  - {s}")
