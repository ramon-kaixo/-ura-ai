"""
AGENTE ORQUESTADOR DE RECETAS - Coordina todas las cocinas y tendencias
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

COCINAS_DISPONIBLES = {
    "española": {
        "archivo": "agente_cocina_espanola",
        "categorias": [
            "esterilizados_pasta",
            "arroz",
            "ensaladas",
            "potajes",
            "guisos",
            "segundos",
        ],
    },
    "italiana": {
        "archivo": "agente_cocina_italiana",
        "categorias": ["primi", "secondi", "contorni", "dolci", "antipasti"],
    },
    "peruana": {
        "archivo": "agente_cocina_peruana",
        "categorias": ["entradas", "segundos", "sopas", "postres"],
    },
    "mexicana": {
        "archivo": "agente_cocina_mexicana",
        "categorias": ["antojitos", "guisados", "sopas", "postres"],
    },
}


def init_orquestador_recetas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS orquesta_recetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cocina TEXT NOT NULL,
            categoria TEXT,
            receta_id INTEGER,
            nombre TEXT,
            en_menu INTEGER DEFAULT 0,
            veces_servida INTEGER DEFAULT 0,
            fecha_creacion TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS menús_carta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_menu TEXT NOT NULL,
            tipo TEXT,
            platos TEXT,
            precio TEXT,
            fecha_creacion TEXT NOT NULL,
            fecha_modificacion TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tendencias_gastronomicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tendencia TEXT NOT NULL,
            origen TEXT,
            descripcion TEXT,
            fecha_deteccion TEXT NOT NULL,
            activa INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()


def obtener_receta_por_cocina(cocina, categoria=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query = """
        SELECT nombre, descripcion, ingredientes, elaboracion, tiempo_preparacion, dificultad, categoria
        FROM recetas_cocina WHERE cocina = ?
    """
    params = [cocina]

    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)

    c.execute(query, params)
    resultados = c.fetchall()
    conn.close()

    return [
        {
            "nombre": r[0],
            "descripcion": r[1],
            "ingredientes": r[2].split(",") if r[2] else [],
            "elaboracion": r[3],
            "tiempo": r[4],
            "dificultad": r[5],
            "categoria": r[6],
        }
        for r in resultados
    ]


def buscar_en_todas_cocinas(termino):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT nombre, descripcion, ingredientes, cocina, categoria
        FROM recetas_cocina
        WHERE nombre LIKE ? OR descripcion LIKE ? OR ingredientes LIKE ?
    """,
        (f"%{termino}%", f"%{termino}%", f"%{termino}%"),
    )

    resultados = c.fetchall()
    conn.close()

    return [
        {
            "nombre": r[0],
            "descripcion": r[1],
            "ingredientes": r[2].split(",") if r[2] else [],
            "cocina": r[3],
            "categoria": r[4],
        }
        for r in resultados
    ]


def crear_menu(cocinas_seleccionadas, tipo="carta"):
    platos = {}

    for cocina in cocinas_seleccionadas:
        recetas = obtener_receta_por_cocina(cocina)
        if recetas:
            platos[cocina] = recetas[:3]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO menús_carta (nombre_menu, tipo, platos, fecha_creacion)
        VALUES (?, ?, ?, ?)
    """,
        (
            f"Menú {tipo} {datetime.now().strftime('%Y%m%d')}",
            tipo,
            json.dumps(platos, ensure_ascii=False),
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()

    return platos


def generar_linea_carta(nombre, descripcion, precio=None):
    from agents.agente_vocabulario_gastronomico import describir_plato

    desc = describir_plato(nombre)

    linea = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    linea += f"🍽️ {nombre}\n"
    linea += f"   {desc}\n"
    if precio:
        linea += f"   💰 {precio} €\n"
    linea += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    return linea


def exportar_menu_para_impresion(cocinas, titulo="CARTA"):
    resultado = []
    resultado.append("═" * 40)
    resultado.append(f"   {titulo}")
    resultado.append("═" * 40)

    for cocina in cocinas:
        resultado.append(f"\n📌 COCINA {cocina.upper()}")
        resultado.append("-" * 30)

        recetas = obtener_receta_por_cocina(cocina)
        for receta in recetas[:5]:
            resultado.append(f"\n• {receta['nombre']}")
            resultado.append(f"  {receta['descripcion']}")

    return "\n".join(resultado)


def mostrar_receta_completa(nombre):
    import os
    import sys

    agent_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, agent_dir)

    from agente_media_recetas import obtener_media_receta
    from recetas_con_media import obtener_receta_completa

    receta = obtener_receta_completa(nombre)

    if not receta:
        return {"error": f"Receta '{nombre}' no encontrada"}

    output = []
    output.append("═" * 60)
    output.append(f"🍽️ {receta['base'].upper()}")
    output.append(f"   Cocina: {receta['cocina']}")
    output.append("═" * 60)

    for i, variante in enumerate(receta["variantes"], 1):
        output.append(f"\n📌 VARIANTE {i}: {variante['nombre']}")
        output.append("-" * 40)
        output.append(f"⏱️ Tiempo: {variante.get('tiempo', 'N/A')}")
        output.append(f"📊 Dificultad: {variante.get('dificultad', 'N/A')}")
        output.append(f"📚 Fuente: {variante.get('fuente', 'N/A')}")
        output.append("\n📝 INGREDIENTES:")
        for ing in variante["ingredientes"].split(", "):
            output.append(f"   • {ing}")
        output.append("\n👨‍🍳 ELABORACIÓN:")
        for paso in variante["elaboracion"].split(". "):
            if paso.strip():
                output.append(f"   {paso.strip()}")
        if variante.get("notas"):
            output.append("\n💡 NOTAS:")
            output.append(f"   {variante['notas']}")

        media = obtener_media_receta(variante["nombre"])
        if media["fotos"]:
            output.append(f"\n📷 FOTOS ({len(media['fotos'])}):")
            for foto in media["fotos"]:
                output.append(f"   • {foto['descripcion']}")
                output.append(f"     Fuente: {foto['fuente']}")
        if media["videos"]:
            output.append(f"\n🎥 VÍDEOS ({len(media['videos'])}):")
            for video in media["videos"]:
                output.append(f"   • {video['descripcion']}")
                output.append(f"     {video['url']}")

    output.append("\n" + "═" * 60)
    return "\n".join(output)


def stats_recetas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    stats = {}

    for cocina in ["española", "italiana", "peruana", "mexicana"]:
        c.execute("SELECT COUNT(*) FROM recetas_cocina WHERE cocina = ?", (cocina,))
        stats[cocina] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM menús_carta")
    stats["menus_creados"] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM tendencias_gastronomicas WHERE activa = 1")
    stats["tendencias_activas"] = c.fetchone()[0]

    conn.close()
    return stats


def agregar_tendencia(tendencia, origen="", descripcion=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO tendencias_gastronomicas (tendencia, origen, descripcion, fecha_deteccion)
        VALUES (?, ?, ?, ?)
    """,
        (tendencia, origen, descripcion, datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()

    return {"success": True, "tendencia": tendencia}


def listar_tendencias():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT tendencia, origen, descripcion, fecha_deteccion
        FROM tendencias_gastronomicas WHERE activa = 1
        ORDER BY fecha_deteccion DESC
    """)

    resultados = c.fetchall()
    conn.close()

    return [
        {"tendencia": r[0], "origen": r[1], "descripcion": r[2], "fecha": r[3]} for r in resultados
    ]


if __name__ == "__main__":
    init_orquestador_recetas()

    print("=== ORQUESTADOR DE RECETAS ===\n")
    print("📊 Estadísticas:")
    print(stats_recetas())

    print("\n📋 Cocinas disponibles:")
    for cocina, info in COCINAS_DISPONIBLES.items():
        print(f"  - {cocina}: {len(info['categorias'])} categorías")

    print("\n🍽️ Ejemplo - generar carta:")
    print(generar_linea_carta("Lentejas con chorizo", "de temporada", "12.50"))
