"""
AGENTE BIBLIOTECA - Coordinador Central de Documentación
Coordina todos los agentes de biblioteca de documentos, vocabulario y medios.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

BIBLIOTECA_PATH = Path(__file__).parent.parent / "biblioteca"
DB_PATH = Path(__file__).parent.parent / "board.db"

FORMATO_AGENTS = {
    "word": "agente_documentos_word",
    "excel": "agente_documentos_excel",
    "pdf": "agente_documentos_pdf",
    "presentaciones": "agente_documentos_presentaciones",
    "texto": "agente_documentos_texto",
}

VOCABULARIO_AGENTS = {
    "tecnico": "agente_vocabulario_tecnico",
    "legal": "agente_vocabulario_legal",
    "bar": "agente_vocabulario_bar",
    "financiero": "agente_vocabulario_financiero",
}

MEDIA_AGENTS = {
    "fotos": "agente_galeria_fotos",
    "videos": "agente_galeria_videos",
}


def init_biblioteca_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS biblioteca_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            formato TEXT NOT NULL,
            nombre TEXT NOT NULL,
            ruta TEXT NOT NULL,
            etiquetas TEXT,
            resumen TEXT,
            palabras_clave TEXT,
            fecha_indexado TEXT NOT NULL,
            ultimo_acceso TEXT,
            veces_accedido INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS biblioteca_vocabulario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            termino TEXT NOT NULL,
            definicion TEXT NOT NULL,
            ejemplo TEXT,
            sinonimos TEXT,
            area TEXT,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS biblioteca_multimedia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            ruta TEXT NOT NULL,
            metadatos TEXT,
            etiquetas TEXT,
            fecha_indexado TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def escanear_biblioteca():
    resultados = {"formatos": {}, "vocabularios": {}, "media": {}}

    for formato, folder in FORMATO_AGENTS.items():
        path = BIBLIOTECA_PATH / folder
        if path.exists():
            archivos = list(path.glob("*"))
            resultados["formatos"][formato] = len(archivos)

    for vocab, folder in VOCABULARIO_AGENTS.items():
        path = BIBLIOTECA_PATH / folder
        if path.exists():
            archivos = list(path.glob("*"))
            resultados["vocabularios"][vocab] = len(archivos)

    for media, folder in MEDIA_AGENTS.items():
        path = BIBLIOTECA_PATH / folder
        if path.exists():
            archivos = list(path.glob("*"))
            resultados["media"][media] = len(archivos)

    return resultados


def buscar_documento(termino, formato=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query = """
        SELECT nombre, ruta, tipo, formato FROM biblioteca_documentos
        WHERE nombre LIKE ? OR etiquetas LIKE ? OR resumen LIKE ?
    """
    params = [f"%{termino}%", f"%{termino}%", f"%{termino}%"]

    if formato:
        query += " AND formato = ?"
        params.append(formato)

    c.execute(query, params)
    resultados = c.fetchall()
    conn.close()

    return [{"nombre": r[0], "ruta": r[1], "tipo": r[2], "formato": r[3]} for r in resultados]


def indexar_documento(ruta, tipo, formato, etiquetas="", resumen=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    nombre = Path(ruta).name

    c.execute(
        """
        INSERT INTO biblioteca_documentos (tipo, formato, nombre, ruta, etiquetas, resumen, fecha_indexado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (tipo, formato, nombre, str(ruta), etiquetas, resumen, datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()


def obtener_vocabulario(categoria=None, termino=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if categoria and termino:
        c.execute(
            """
            SELECT termino, definicion, ejemplo FROM biblioteca_vocabulario
            WHERE categoria = ? AND termino LIKE ?
        """,
            (categoria, f"%{termino}%"),
        )
    elif categoria:
        c.execute(
            "SELECT termino, definicion, ejemplo FROM biblioteca_vocabulario WHERE categoria = ?",
            (categoria,),
        )
    elif termino:
        c.execute(
            "SELECT termino, definicion, ejemplo, categoria FROM biblioteca_vocabulario WHERE termino LIKE ?",
            (f"%{termino}%",),
        )
    else:
        c.execute("SELECT termino, definicion, ejemplo, categoria FROM biblioteca_vocabulario")

    resultados = c.fetchall()
    conn.close()

    return resultados


def agregar_vocabulario(categoria, termino, definicion, ejemplo="", sinonimos=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO biblioteca_vocabulario (categoria, termino, definicion, ejemplo, sinonimos, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (categoria, termino, definicion, ejemplo, sinonimos, datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()


def buscar_multimedia(termino, tipo=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query = """
        SELECT nombre, ruta, tipo, etiquetas FROM biblioteca_multimedia
        WHERE nombre LIKE ? OR etiquetas LIKE ?
    """
    params = [f"%{termino}%", f"%{termino}%"]

    if tipo:
        query += " AND tipo = ?"
        params.append(tipo)

    c.execute(query, params)
    resultados = c.fetchall()
    conn.close()

    return [{"nombre": r[0], "ruta": r[1], "tipo": r[2], "etiquetas": r[3]} for r in resultados]


def status():
    init_biblioteca_db()
    scan = escanear_biblioteca()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM biblioteca_documentos")
    total_docs = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM biblioteca_vocabulario")
    total_vocab = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM biblioteca_multimedia")
    total_media = c.fetchone()[0]

    conn.close()

    return {
        "biblioteca_path": str(BIBLIOTECA_PATH),
        "carpetas": scan,
        "documentos_indexados": total_docs,
        "terminos_vocabulario": total_vocab,
        "multimedia_indexada": total_media,
    }


if __name__ == "__main__":
    print("=== BIBLIOTECA URA - Status ===")
    import json

    print(json.dumps(status(), indent=2))
