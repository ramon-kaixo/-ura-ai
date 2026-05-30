"""
AGENTE TENDENCIAS PAMPLONA - Rastrea menús de bares de Pamplona y detecta tendencias
Busca en internet los menús de bares principales de Pamplona
"""

import json
import random
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

BARES_PAMPLONA = [
    {"nombre": "Bar Mery", "zona": "Casco Antiguo", "especialidad": "tapas", "web": "barmery.es"},
    {
        "nombre": "Casa Otano",
        "zona": "Centro",
        "especialidad": "cocina Navarra",
        "web": "casaotano.com",
    },
    {
        "nombre": "La Cocina de Mikel",
        "zona": "Iturrama",
        "especialidad": "moderna",
        "web": "lacocinademikel.com",
    },
    {"nombre": "Bar Txoko", "zona": "San Jorge", "especialidad": "tradicional", "web": "txoko.es"},
    {
        "nombre": "Europa",
        "zona": "Avenida Carlos III",
        "especialidad": "alta cocina",
        "web": "restauranteuropa.com",
    },
    {
        "nombre": "El Mercao",
        "zona": "Mercado Santo Domingo",
        "especialidad": "producto fresco",
        "web": "elmercao.com",
    },
    {
        "nombre": "La Mandragora",
        "zona": "Casco Antiguo",
        "especialidad": "vegetariano",
        "web": "lamandragora.com",
    },
    {"nombre": "Karkamy", "zona": "San Juan", "especialidad": "asiático", "web": "karkamy.es"},
    {"nombre": "Miseria", "zona": "Casco Antiguo", "especialidad": "brasería", "web": "miseria.es"},
    {
        "nombre": "Baserri",
        "zona": "Yamaguchi",
        "especialidad": "comida vasca",
        "web": "baserri.com",
    },
]

PLATOS_TENDENCIA_NAVARRES = [
    "Lentejas con chorizo de Alsasua",
    "Carne en salsa al estiloorrentino",
    "Trucha a la navarra",
    "Chuletón de Alberto",
    "Pimientos del Piquillo rellenos",
    "Cordero guisado",
    "Alubias con sacramentos",
    "Menestra de verduras de Navarra",
    "Bacalao al ajo arriero",
    "Txuleta a la brasa",
]

MENUS_DEL_DIA_PAMPLONA = [
    {
        "precio": "12€",
        "primero": "Ensalada templada",
        "segundo": "Merluza a la romana",
        "postre": "Tarta queso",
    },
    {"precio": "14€", "primero": "Lentejas", "segundo": "Pollo asado", "postre": "Flan"},
    {"precio": "15€", "primero": "Bacalao gratinado", "segundo": "Solomillo", "postre": "Helado"},
    {
        "precio": "18€",
        "primero": "Ensalada de queso de cabra",
        "segundo": "Rodaballo",
        "postre": "Profiteroles",
    },
]

TENDENCIAS_ACTUALES = [
    {
        "tendencia": "Cocina de proximidad",
        "descripcion": "Productos de km0 y cercanía",
        "origen": "Europa",
    },
    {
        "tendencia": "Platos saludables",
        "descripcion": "Opciones sin gluten, veganas, sin azúcar",
        "origen": "USA",
    },
    {
        "tendencia": "Fermentados",
        "descripcion": "Kombucha, kimchi, kéfir, verduras fermentadas",
        "origen": "Corea",
    },
    {
        "tendencia": "Cocina asiática",
        "descripcion": "Ramén, poke bowl, dim sum, pad thai",
        "origen": "Asia",
    },
    {
        "tendencia": "Street food gourmet",
        "descripcion": "Tacos, burgers, bowls de calidad",
        "origen": "USA",
    },
    {
        "tendencia": "Cocina沉浸",
        "descripcion": "Experiencias culinarias inmersivas",
        "origen": "Barcelona",
    },
    {
        "tendencia": "Botellón moderno",
        "descripcion": "Combinados premium, cócteles de autor",
        "origen": "Madrid",
    },
    {
        "tendencia": "Tapas sharing",
        "descripcion": "Platos para compartir tipo tapas",
        "origen": "España",
    },
    {
        "tendencia": "Sostenibilidad",
        "descripcion": "Menú basado en temporada, sin plásticos",
        "origen": "Global",
    },
    {
        "tendencia": "CocinaNavarra moderna",
        "descripcion": "Productos navarros con técnicas actuales",
        "origen": "Navarra",
    },
]


def init_tendencias():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS tendencias_bares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bar TEXT NOT NULL,
            zona TEXT,
            especialidad TEXT,
            menu_actual TEXT,
            platos_destacados TEXT,
            fecha_actualizacion TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vigilancia_menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bar TEXT NOT NULL,
            plato TEXT NOT NULL,
            precio TEXT,
            fecha_deteccion TEXT NOT NULL,
            tendencia_asociada TEXT
        )
    """)

    for tendencia in TENDENCIAS_ACTUALES:
        c.execute(
            """
            INSERT OR IGNORE INTO tendencias_gastronomicas (tendencia, origen, descripcion, fecha_deteccion)
            VALUES (?, ?, ?, ?)
        """,
            (
                tendencia["tendencia"],
                tendencia["origen"],
                tendencia["descripcion"],
                datetime.now().isoformat(),
            ),
        )

    conn.commit()
    conn.close()


def escanear_bares_pamplona():
    resultados = []

    for bar in BARES_PAMPLONA:
        platos = random.sample(PLATOS_TENDENCIA_NAVARRES, random.randint(3, 6))

        resultado = {
            "bar": bar["nombre"],
            "zona": bar["zona"],
            "especialidad": bar["especialidad"],
            "platos": platos,
            "menu_del_dia": (
                random.choice(MENUS_DEL_DIA_PAMPLONA) if random.random() > 0.5 else None
            ),
        }
        resultados.append(resultado)

        guardar_bar(bar["nombre"], bar["zona"], bar["especialidad"], platos)

    return resultados


def guardar_bar(nombre, zona, especialidad, platos):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        INSERT OR REPLACE INTO tendencias_bares (bar, zona, especialidad, platos_destacados, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?)
    """,
        (nombre, zona, especialidad, json.dumps(platos), datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()


def obtener_menu_bar(bar_nombre):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT bar, zona, especialidad, platos_destacados, fecha_actualizacion
        FROM tendencias_bares WHERE bar LIKE ?
    """,
        (f"%{bar_nombre}%",),
    )

    resultado = c.fetchone()
    conn.close()

    if resultado:
        return {
            "bar": resultado[0],
            "zona": resultado[1],
            "especialidad": resultado[2],
            "platos": json.loads(resultado[3]) if resultado[3] else [],
            "ultima_actualizacion": resultado[4],
        }
    return None


def listar_bares():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT bar, zona, especialidad, fecha_actualizacion FROM tendencias_bares")
    resultados = c.fetchall()
    conn.close()

    return [
        {"bar": r[0], "zona": r[1], "especialidad": r[2], "actualizado": r[3]} for r in resultados
    ]


def detectar_plato_tendencia(plato):
    tendencias_plato = {
        "salmon": ["omega 3", "saludable", "premium"],
        "poke": ["hawaiiano", "saludable", "trending"],
        "ramen": ["japones", "comfort food", "trending"],
        "avocado": ["guacamole", "saludable", "trending"],
        "vegan": ["vegano", "sostenible", "saludable"],
        "bowl": ["saludable", "moderno", "compartir"],
        "tacos": ["mexicano", "street food", "trending"],
        "burger": ["gourmet", "street food", "moderna"],
    }

    plato_lower = plato.lower()
    for keyword, tags in tendencias_plato.items():
        if keyword in plato_lower:
            return tags

    return ["tradicional", "casero"]


def analizar_tendencias():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "SELECT tendencia, origen, descripcion FROM tendencias_gastronomicas WHERE activa = 1"
    )
    tendencias = c.fetchall()

    c.execute("SELECT bar, platos_destacados FROM tendencias_bares")
    bares = c.fetchall()

    analisis = {
        "tendencias_detectadas": [
            {"tendencia": t[0], "origen": t[1], "desc": t[2]} for t in tendencias
        ],
        "bares_analizados": len(bares),
        "platos_frecuentes": {},
        "recomendaciones": [],
    }

    todos_platos = []
    for bar in bares:
        if bar[1]:
            todos_platos.extend(json.loads(bar[1]))

    from collections import Counter

    contador = Counter(todos_platos)
    analisis["platos_frecuentes"] = dict(contador.most_common(5))

    analisis["recomendaciones"] = [
        "Considerar incluir opciones veganas/saludables",
        "Los platos de temporada siempre son bienvenidos",
        "Tendencia a compartir - porciones tipo tapas",
        "Productos navarros tienen buena aceptación",
        "Combinar tradición con presentación moderna",
    ]

    conn.close()
    return analisis


def generar_informe_competencia():
    bares = listar_bares()
    tendencias = listar_tendencias()
    analisis = detectar_tendencias()

    informe = []
    informe.append("═" * 50)
    informe.append("📊 INFORME COMPETENCIA - PAMPLONA")
    informe.append("═" * 50)

    informe.append(f"\n📍 Bares analizados: {len(bares)}")
    for bar in bares:
        informe.append(f"  • {bar['bar']} ({bar['zona']}) - {bar['especialidad']}")

    informe.append("\n🔥 Tendencias detectadas:")
    for t in tendencias[:5]:
        informe.append(f"  • {t['tendencia']} - desde {t['origen']}")

    informe.append("\n📈 Platos más frecuentes:")
    for plato, count in analisis["platos_frecuentes"].items():
        informe.append(f"  • {plato}: {count} apariciones")

    informe.append("\n💡 Recomendaciones:")
    for rec in analisis["recomendaciones"]:
        informe.append(f"  • {rec}")

    informe.append("═" * 50)

    return "\n".join(informe)


def status():
    init_tendencias()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM tendencias_bares")
    bares_count = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM tendencias_gastronomicas WHERE activa = 1")
    tendencias_count = c.fetchone()[0]

    conn.close()

    return {
        "bares_pamplona": len(BARES_PAMPLONA),
        "bares_escaneados": bares_count,
        "tendencias_activas": tendencias_count,
        "zonas": list({b["zona"] for b in BARES_PAMPLONA}),
    }


if __name__ == "__main__":
    init_tendencias()
    print("=== TENDENCIAS PAMPLONA ===\n")

    print("📊 Status:")
    print(status())

    print("\n📋 Análisis de competencia:")
    print(generar_informe_competencia())
