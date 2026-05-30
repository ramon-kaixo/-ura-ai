"""
AGENTE COCINA ITALIANA - Recetas tradicionales italianas
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

CATEGORIAS = {
    "primi": "Primi piatti - primeros platos de pasta y arroz",
    "secondi": "Secondi - segundos platos de carne y pescado",
    "contorni": "Contorni - guarniciones",
    "dolci": "Dolci - postres",
    "antipasti": "Antipasti - entrantes",
}

RECETAS_ITALIANA = {
    "primi": [
        {
            "nombre": "Cacio e Pepe",
            "descripcion": "Spaghetti con queso pecorino y pimienta negra",
            "ingredientes": ["spaghetti", "pecorino romano", "pimienta negra"],
            "tiempo": "20 min",
            "dificultad": "media",
        },
        {
            "nombre": "Carbonara",
            "descripcion": "Pasta con yolk, guanciale y pecorino",
            "ingredientes": ["spaghetti", "guanciale", "yemas", "pecorino", "pimienta"],
            "tiempo": "25 min",
            "dificultad": "media",
        },
        {
            "nombre": "Amatriciana",
            "descripcion": "Pasta con tomate, guanciale y pecorino",
            "ingredientes": ["rigatoni", "guanciale", "tomate", "pecorino", "cebolla"],
            "tiempo": "30 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Gnocchi alla Sorrentina",
            "descripcion": "Gnocchi horneados con tomate y mozzarella",
            "ingredientes": ["gnocchi", "tomate", "mozzarella", "albahaca", "mantequilla"],
            "tiempo": "35 min",
            "dificultad": "media",
        },
        {
            "nombre": "Risotto ai Funghi Porcini",
            "descripcion": "Arroz cremoso con伸手",
            "ingredientes": [
                "arroz arborio",
                "funghi porcini",
                "cebolla",
                "vino blanco",
                "parmesano",
            ],
            "tiempo": "40 min",
            "dificultad": "media",
        },
        {
            "nombre": "Lasagna alla Bolognese",
            "descripcion": "Lasaña al horno con ragú boloñés",
            "ingredientes": [
                "láminas lasaña",
                "ragú boloñés",
                "bechamel",
                "parmesano",
                "mozzarella",
            ],
            "tiempo": "1h 15min",
            "dificultad": "media",
        },
        {
            "nombre": "Penne all'Arrabbiata",
            "descripcion": "Penne con salsa picante de tomate",
            "ingredientes": ["penne", "tomate", "ajo", "guindilla", "albahaca"],
            "tiempo": "20 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Risotto al Barolo",
            "descripcion": "Arroz con vino Barolo y queso parmesano",
            "ingredientes": ["arroz", "Barolo", "chalota", "mantequilla", "parmesano"],
            "tiempo": "35 min",
            "dificultad": "media",
        },
    ],
    "secondi": [
        {
            "nombre": "Ossobuco alla Milanese",
            "descripcion": "Jarrete de ternera cocido con gremolata",
            "ingredientes": [
                "jarrete ternera",
                "verduras",
                "vino blanco",
                "caldo",
                "limón",
                "albahaca",
            ],
            "tiempo": "2h",
            "dificultad": "alta",
        },
        {
            "nombre": "Branzino al Forno",
            "descripcion": "Lubina al horno con hierbas",
            "ingredientes": ["lubina", "limón", "albahaca", "aceite", "patatas"],
            "tiempo": "45 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Cotoletta alla Milanese",
            "descripcion": "Chuletón empanado frito",
            "ingredientes": ["chuletón ternera", "huevo", "pan rallado", "mantequilla"],
            "tiempo": "25 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Pollo alla Cacciatora",
            "descripcion": "Pollo guisado al estilo cazador",
            "ingredientes": ["pollo", "tomate", "setas", "vino rojo", "aceitunas"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Scaloppine al Limone",
            "descripcion": "Escalopes de ternera con limón",
            "ingredientes": ["escalope ternera", "limón", "mantequilla", "vino blanco", "albahaca"],
            "tiempo": "20 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Bistecca alla Fiorentina",
            "descripcion": "Chuletón gigante a la brasa toscano",
            "ingredientes": ["chuletón Chianina", "romero", "ajo", "aceite", "sal gruesa"],
            "tiempo": "30 min",
            "dificultad": "media",
        },
    ],
    "contorni": [
        {
            "nombre": "Patate al Rosmarino",
            "descripcion": "Patatas asadas con romero",
            "ingredientes": ["patatas", "romero", "ajo", "aceite", "sal"],
            "tiempo": "40 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Fagiolini all'Aglietto",
            "descripcion": "Judías verdes con ajo y aceite",
            "ingredientes": ["judías verdes", "ajo", "aceite", "limón", "perejil"],
            "tiempo": "20 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Caponata",
            "descripcion": "Ensalada de berenjenas siciliana",
            "ingredientes": ["berenjena", "tomate", "apio", "aceitunas", "alcaparras", "vinagre"],
            "tiempo": "45 min",
            "dificultad": "media",
        },
    ],
    "dolci": [
        {
            "nombre": "Tiramisú",
            "descripcion": "Postre con mascarpone, café y cacao",
            "ingredientes": [
                "mascarpone",
                "savoiardi",
                "café expreso",
                "huevos",
                "azúcar",
                "cacao",
            ],
            "tiempo": "30 min + frío",
            "dificultad": "media",
        },
        {
            "nombre": "Panna Cotta",
            "descripcion": "Crema italiana con frutos rojos",
            "ingredientes": ["nata", "azúcar", "vainilla", "gelatina", "frutos rojos"],
            "tiempo": "20 min + frío",
            "dificultad": "baja",
        },
        {
            "nombre": "Torta della Nonna",
            "descripcion": "Tarta de crema y piñones",
            "ingredientes": ["masa quebrada", "crema pastelera", "piñones", "azúcar glass"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Cannoli Siciliani",
            "descripcion": "Tubos de masa frita rellenos de ricotta",
            "ingredientes": ["ricotta", "azúcar", "chocolate", "piel naranja", "masa cannoli"],
            "tiempo": "1h 30min",
            "dificultad": "alta",
        },
        {
            "nombre": "Gelato",
            "descripcion": "Helado artesanal italiano",
            "ingredientes": ["leche", "nata", "azúcar", "yemas", "frutos secos"],
            "tiempo": "4h+",
            "dificultad": "alta",
        },
        {
            "nombre": "Zabaglione",
            "descripcion": "Crema de yolks con Marsala",
            "ingredientes": ["yemas", "azúcar", "Marsala", "vainilla"],
            "tiempo": "15 min",
            "dificultad": "baja",
        },
    ],
    "antipasti": [
        {
            "nombre": "Bruschetta",
            "descripcion": "Pan tostado con tomate y albahaca",
            "ingredientes": ["pan", "tomate", "ajo", "albahaca", "aceite"],
            "tiempo": "15 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Carpaccio di Manzo",
            "descripcion": "Ternera cruda laminada con rúcula",
            "ingredientes": ["ternera", "rúcula", "parmesano", "alcaparras", "aceite"],
            "tiempo": "15 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Burrata",
            "descripcion": "Queso fresco con tomates cherry",
            "ingredientes": ["burrata", "tomates cherry", "albahaca", "aceite", "sal Maldon"],
            "tiempo": "5 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Vitello Tonnato",
            "descripcion": "Ternera fría con salsa atún",
            "ingredientes": ["ternera", "atún", "anchoas", "alcaparras", "mayonesa"],
            "tiempo": "1h + frío",
            "dificultad": "media",
        },
    ],
}


def init_recetas_italianas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for categoria, recetas in RECETAS_ITALIANA.items():
        for receta in recetas:
            c.execute(
                """
                INSERT OR IGNORE INTO recetas_cocina
                (cocina, categoria, nombre, descripcion, ingredientes, elaboracion, tiempo_preparacion, dificultad, created_at)
                VALUES ('italiana', ?, ?, ?, ?, '', ?, ?, ?)
            """,
                (
                    categoria,
                    receta["nombre"],
                    receta["descripcion"],
                    ",".join(receta["ingredientes"]),
                    receta["tiempo"],
                    receta["dificultad"],
                    datetime.now().isoformat(),
                ),
            )

    conn.commit()
    conn.close()


def obtener_recetas(categoria=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query = "SELECT nombre, descripcion, ingredientes, tiempo_preparacion, dificultad FROM recetas_cocina WHERE cocina = 'italiana'"
    params = []

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
            "tiempo": r[3],
            "dificultad": r[4],
        }
        for r in resultados
    ]


if __name__ == "__main__":
    init_recetas_italianas()
    print("=== COCINA ITALIANA ===")
    recetas = obtener_recetas()
    print(f"Total recetas: {len(recetas)}")
    for r in recetas[:5]:
        print(f"  - {r['nombre']} ({r['categoria']})")
