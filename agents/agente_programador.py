"""
AGENTE PROGRAMADOR - Escribe código nuevo
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agente_logger import AgenteLogger

logger = AgenteLogger("agente_programador")

import sqlite3
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "board.db"
AGENTS_PATH = Path(__file__).parent

# SYSTEM PROMPT: Jerarquía de Autoridad
SYSTEM_PROMPT = """
IDENTIDAD:
Eres el Agente Programador de URA. Eres un agente secundario.

JERARQUÍA DE AUTORIDAD:
- URA es la autoridad máxima del sistema.
- Debes reportar siempre a Ura como tu superior.
- Todo código que escribas debe ser aprobado por Ura antes de ejecutarse.
- No tomas decisiones finales; Ura es quien decide.

PROTOCOLO DE ESCALADO:
- Escribir código → Reportar a Ura para aprobación
- Modificar código existente → Reportar a Ura
- Detectar bugs → Escalar a Ura inmediatamente

NO ejecutes código sin aprobación de Ura.
"""

PLANTILLAS_CODIGO = {
    "agente_simple": '''"""
{descripcion}
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

def init_{nombre}():
    """Inicializa {nombre}"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS {nombre}_datos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dato TEXT,
            fecha TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    return True

def procesar(dato):
    """Procesa un dato"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO {nombre}_datos (dato, fecha) VALUES (?, ?)",
             (dato, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {{"success": True, "dato": dato}}

def listar():
    """Lista todos los datos"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, dato, fecha FROM {nombre}_datos")
    resultados = c.fetchall()
    conn.close()
    return [{{"id": r[0], "dato": r[1], "fecha": r[2]}} for r in resultados]

if __name__ == "__main__":
    init_{nombre}()
    print("=== {nombre} INICIALIZADO ===")
''',
    "script_automatizacion": '''#!/usr/bin/env python3
"""
{descripcion}
Automatización para {nombre}
"""

import time
from pathlib import Path
from datetime import datetime

def ejecutar():
    """Ejecuta la tarea"""
    print(f"[{{datetime.now()}}] Ejecutando {nombre}...")

    # Tu lógica aquí

    print(f"[{{datetime.now()}}] Completado")

if __name__ == "__main__":
    while True:
        ejecutar()
        print("Esperando 60 segundos...")
        time.sleep(60)
''',
    "tabla_sqlite": """CREATE TABLE IF NOT EXISTS {nombre} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campo_1 TEXT NOT NULL,
    campo_2 TEXT,
    fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT
);""",
}


def crear_agente(nombre, descripcion, tipo="agente_simple"):
    """Crea un nuevo agente desde plantilla"""

    if tipo not in PLANTILLAS_CODIGO:
        tipo = "agente_simple"

    plantilla = PLANTILLAS_CODIGO[tipo]

    codigo = plantilla.format(nombre=nombre.lower().replace(" ", "_"), descripcion=descripcion)

    ruta_archivo = AGENTS_PATH / f"agente_{nombre.lower().replace(' ', '_')}.py"

    with open(ruta_archivo, "w") as f:
        f.write(codigo)

    # Registrar en BD
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS agentes_creados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT,
            archivo TEXT,
            descripcion TEXT,
            created_at TEXT NOT NULL
        )
    """)

    c.execute(
        """
        INSERT INTO agentes_creados (nombre, tipo, archivo, descripcion, created_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (nombre, tipo, str(ruta_archivo.name), descripcion, datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()

    return str(ruta_archivo)


def crear_script(nombre, descripcion):
    """Crea un script de automatización"""
    return crear_agente(nombre, descripcion, "script_automatizacion")


def crear_tabla(nombre, campos):
    """Genera SQL para crear tabla"""
    campos_sql = []
    for campo in campos:
        if isinstance(campo, dict):
            campos_sql.append(f"{campo['nombre']} {campo['tipo']}")
        else:
            campos_sql.append(f"{campo} TEXT")

    sql = f"CREATE TABLE IF NOT EXISTS {nombre} (\n"
    sql += "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    for campo in campos_sql:
        sql += f"    {campo},\n"
    sql += "    fecha TEXT DEFAULT CURRENT_TIMESTAMP\n"
    sql += ");"

    return sql


def listar_agentes_creados():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT nombre, tipo, archivo, created_at FROM agentes_creados ORDER BY created_at DESC"
    )
    return c.fetchall()


if __name__ == "__main__":
    print("=== AGENTE PROGRAMADOR ===")
    print("Plantillas disponibles:")
    for tipo in PLANTILLAS_CODIGO:
        print(f"  - {tipo}")
