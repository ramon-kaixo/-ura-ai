"""
AGENTE REVISOR - Revisa código y detecta errores
"""

import ast
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"
AGENTS_PATH = Path(__file__).parent.parent / "agents"

ERRORES_COMUNES = {
    "sin_except": " Usa try-except para manejar errores",
    "sin_docstring": " Falta docstring en función",
    "import_absoluto": " Usa imports desde la raíz del proyecto",
    "rutas_hardcoded": " Evita rutas hardcodeadas, usa Path()",
    "sql_injection": " Usa parámetros en consultas SQL",
    "sin_log": " Añade logging para trazabilidad",
}


def revisar_archivo(ruta_archivo):
    """Revisa un archivo Python en busca de errores"""
    try:
        with open(ruta_archivo) as f:
            contenido = f.read()

        errores = []
        warnings = []

        # Verificar sintaxis
        try:
            ast.parse(contenido)
        except SyntaxError as e:
            errores.append(f"❌ Error de sintaxis línea {e.lineno}: {e.msg}")

        # Buscar errores comunes
        if "except:" in contenido and "except Exception" not in contenido:
            warnings.append("⚠️ except vacío - usar except Exception:")

        if "print(" in contenido and "log(" not in contenido.lower():
            warnings.append("💡 Considera usar logging en lugar de print")

        if "except:" in contenido and "except Exception as e:" not in contenido:
            warnings.append("⚠️ Captura excepciones específicas")

        # Buscar imports problemáticos
        if "import sys" in contenido and "sys.path" not in contenido:
            warnings.append("💡 Usa sys.path.insert(0, ...) para imports locales")

        # Verificar docstrings
        funciones = re.findall(r"def (\w+)\(", contenido)
        for func in funciones[:5]:  # Solo las primeras 5
            patron = f'def {func}\\([^)]*\\):[^"]*("""|\'\'\')'
            if not re.search(patron, contenido, re.DOTALL):
                warnings.append(f"📝 Función '{func}' podría necesitar docstring")

        return {
            "archivo": str(ruta_archivo),
            "errores": errores,
            "warnings": warnings,
            "lineas": len(contenido.splitlines()),
            "estado": "OK" if not errores else "ERROR" if errores else "WARNING",
        }

    except Exception as e:
        return {
            "archivo": str(ruta_archivo),
            "errores": [f"❌ No se pudo revisar: {str(e)}"],
            "warnings": [],
            "estado": "ERROR",
        }


def revisar_proyecto():
    """Revisa todos los agentes del proyecto"""
    agentes = []

    for archivo in AGENTS_PATH.glob("agente_*.py"):
        resultado = revisar_archivo(archivo)
        agentes.append(resultado)

    return agentes


def revisar_tabla(nombre_tabla):
    """Verifica estructura de una tabla en la BD"""
    if not nombre_tabla.replace("_", "").isalnum():
        raise ValueError(f"Nombre de tabla invalido: {nombre_tabla}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute(f"PRAGMA table_info({nombre_tabla})")
        columnas = c.fetchall()
        c.execute(f"SELECT COUNT(*) FROM {nombre_tabla}")
        registros = c.fetchone()[0]

        conn.close()

        return {
            "tabla": nombre_tabla,
            "columnas": [col[1] for col in columnas],
            "num_columnas": len(columnas),
            "registros": registros,
        }
    except Exception as e:
        conn.close()
        return {"tabla": nombre_tabla, "error": str(e)}


def listar_tablas_bd():
    """Lista todas las tablas de la BD"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tablas = [r[0] for r in c.fetchall() if not r[0].startswith("sqlite")]
    conn.close()
    return tablas


def diagnostico_completo():
    """Hace diagnóstico completo del proyecto"""
    diagnostico = {
        "fecha": datetime.now().isoformat(),
        "agentes": {},
        "tablas": {},
        "problemas": [],
    }

    # Revisar agentes
    agentes = revisar_proyecto()
    for agente in agentes:
        diagnostico["agentes"][agente["archivo"]] = {
            "lineas": agente.get("lineas", 0),
            "estado": agente.get("estado", "UNKNOWN"),
            "errores": len(agente.get("errores", [])),
        }
        if agente.get("errores"):
            diagnostico["problemas"].extend(agente["errores"])

    # Ver tablas
    tablas = listar_tablas_bd()
    for tabla in tablas[:10]:  # Solo primeras 10
        info = revisar_tabla(tabla)
        diagnostico["tablas"][tabla] = info

    # Guardar en BD
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS diagnosticos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            resultado TEXT,
            problemas INTEGER
        )
    """)

    c.execute(
        """
        INSERT INTO diagnosticos (fecha, resultado, problemas)
        VALUES (?, ?, ?)
    """,
        (datetime.now().isoformat(), "OK", len(diagnostico["problemas"])),
    )

    conn.commit()
    conn.close()

    return diagnostico


if __name__ == "__main__":
    print("=== AGENTE REVISOR ===")
    print("Haciendo diagnóstico...")

    diag = diagnostico_completo()
    print(f"Agentes revisados: {len(diag['agentes'])}")
    print(f"Tablas verificadas: {len(diag['tablas'])}")
    print(f"Problemas encontrados: {len(diag['problemas'])}")

    if diag["problemas"]:
        print("\n⚠️ Problemas:")
        for p in diag["problemas"][:5]:
            print(f"  {p}")
