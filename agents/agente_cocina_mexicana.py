"""
AGENTE COCINA MEXICANA - Recetas tradicionales de México
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

CATEGORIAS = {
    "antojitos": "Antojitos - snacks y entrantes",
    "guisados": "Guisados - platos principales",
    "antojitos": "Tacos, tostadas y antojitos",
    "sopas": "Sopas y caldos",
    "postres": "Postres mexicanos",
}

RECETAS_MEXICANA = {
    "antojitos": [
        {
            "nombre": "Tacos al Pastor",
            "descripcion": "Tacos con carne adobada, piña y cilantro",
            "ingredientes": [
                "carné cerdo",
                "adobo",
                "piña",
                "cebolla",
                "cilantro",
                "tortilla maíz",
            ],
            "tiempo": "2h",
            "dificultad": "media",
        },
        {
            "nombre": "Tacos de Carnitas",
            "descripcion": "Tacos con carne de cerdo deshilachada",
            "ingredientes": ["pierna cerdo", "naranja", "ajo", "canela", "tortilla"],
            "tiempo": "3h",
            "dificultad": "media",
        },
        {
            "nombre": "Quesadilla",
            "descripcion": "Tortilla con queso derretido y guisado",
            "ingredientes": ["tortilla harina", "queso Oaxaca", "champiñones", "flor calabaza"],
            "tiempo": "20 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Tostada de Ceviche",
            "descripcion": "Tostada con ceviche de pescado",
            "ingredientes": [
                "pescado blanco",
                "limón",
                "tomate",
                "cebolla",
                "chile serrano",
                "aguacate",
            ],
            "tiempo": "30 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Guacamole",
            "descripcion": "Puré de aguacate con tomate, cebolla y cilantro",
            "ingredientes": [
                "aguacate",
                "tomate",
                "cebolla morada",
                "cilantro",
                "limón",
                "chile serrano",
            ],
            "tiempo": "15 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Sopes",
            "descripcion": "Bases de tortilla con frijoles y guisados",
            "ingredientes": ["masa maíz", "frijoles", "carne", "lechoriza", "queso", "crema"],
            "tiempo": "40 min",
            "dificultad": "media",
        },
        {
            "nombre": "Pozole Rojo",
            "descripcion": "Sopa de maíz pozolero con carne",
            "ingredientes": ["maíz pozolero", "carné cerdo", "chile guajillo", "ajo", "oregano"],
            "tiempo": "3h",
            "dificultad": "media",
        },
        {
            "nombre": "Enchiladas Rojas",
            "descripcion": "Tortillas bañadas en salsa roja con pollo",
            "ingredientes": ["tortilla", "pollo", "salsa roja", "queso", "crema", "cebolla"],
            "tiempo": "45 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Enmoladas",
            "descripcion": "Enchiladas con salsa de mole",
            "ingredientes": ["tortilla", "pollo", "mole poblano", "queso", "crema"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Chiles Rellenos",
            "descripcion": "Chiles poblanos rellenos de queso y carne",
            "ingredientes": ["chile poblano", "queso", "carne molida", "huevo", "salsa tomate"],
            "tiempo": "1h",
            "dificultad": "media",
        },
    ],
    "guisados": [
        {
            "nombre": "Mole Poblano",
            "descripcion": "Salsa complex con chiles, chocolate y especias",
            "ingredientes": [
                "chile mulato",
                "chile ancho",
                "chocolate",
                "almendras",
                "pasas",
                "especias",
                "pavo",
            ],
            "tiempo": "4h",
            "dificultad": "alta",
        },
        {
            "nombre": "Mole Negro Oaxaqueño",
            "descripcion": "Mole oscuro oaxaqueño con舞会",
            "ingredientes": [
                "chile negro",
                "chile pasilla",
                " chocolate negro",
                "semillas",
                "pan",
                "pavo",
            ],
            "tiempo": "5h",
            "dificultad": "alta",
        },
        {
            "nombre": "Cochinita Pibil",
            "descripcion": "Cerdo marinado en achiote y cocido lento",
            "ingredientes": [
                "carné cerdo",
                "achiote",
                "naranja agria",
                "cebolla morada",
                "chile habanero",
            ],
            "tiempo": "4h",
            "dificultad": "media",
        },
        {
            "nombre": "Pollo en Salsa Verde",
            "descripcion": "Pollo en salsa de tomatillos y chiles",
            "ingredientes": ["pollo", "tomatillos", "serranos", "cebolla", "ajo", "cilantro"],
            "tiempo": "45 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Carne en su Jugo",
            "descripcion": "Carne de res en caldo con frijoles",
            "ingredientes": ["carné res", "frijoles", "tocino", "cebolla", "ajo", "chile serrano"],
            "tiempo": "2h",
            "dificultad": "media",
        },
    ],
    "sopas": [
        {
            "nombre": "Pozole",
            "descripcion": "Sopa tradicional de maíz con carne",
            "ingredientes": [
                "maíz pozolero",
                "carné cerdo",
                "chile",
                "rábanos",
                "orégano",
                "limón",
            ],
            "tiempo": "3h",
            "dificultad": "media",
        },
        {
            "nombre": "Sopa de Mariscos",
            "descripcion": "Caldo mixto de mariscos con略",
            "ingredientes": [
                "camarones",
                "pulpo",
                "calamar",
                "tomate",
                "cebolla",
                "chile",
                "epazote",
            ],
            "tiempo": "45 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Caldo de Res",
            "descripcion": "Sopa de ternera con verduras",
            "ingredientes": ["carné res", "elote", "calabaza", "chayote", "garbanzos"],
            "tiempo": "2h",
            "dificultad": "baja",
        },
        {
            "nombre": "Menudo",
            "descripcion": "Sopa de panza con chile y garbanzos",
            "ingredientes": ["panza res", "garbanzos", "chile morita", "cebolla", "orégano"],
            "tiempo": "4h",
            "dificultad": "alta",
        },
    ],
    "postres": [
        {
            "nombre": "Flan Napolitano",
            "descripcion": "Flan de vainilla con caramelo",
            "ingredientes": ["leche", "huevos", "azúcar", "vainilla", "caramelo"],
            "tiempo": "1h 30min",
            "dificultad": "baja",
        },
        {
            "nombre": "Churros con Chocolate",
            "descripcion": "Masa frita con chocolate caliente",
            "ingredientes": ["harina", "mantequilla", "agua", "azúcar", "chocolate"],
            "tiempo": "45 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Arroz con Leche",
            "descripcion": "Arroz dulce con leche y canela",
            "ingredientes": ["arroz", "leche", "azúcar", "canela", "pasas"],
            "tiempo": "1h",
            "dificultad": "baja",
        },
        {
            "nombre": "Gelatina de Flores",
            "descripcion": "Gelatina de Jamaica con crema",
            "ingredientes": ["flor jamaica", "azúcar", "gelatina", "crema"],
            "tiempo": "4h",
            "dificultad": "baja",
        },
        {
            "nombre": "Capirotada",
            "descripcion": "Postre de pan con piloncillo y queso",
            "ingredientes": ["pan", "piloncillo", "queso", "cacahuates", "pasas", "canela"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Paletas de Mango",
            "descripcion": "Helados naturales de mango con chile",
            "ingredientes": ["mango", "chile piquín", "limón", "azúcar"],
            "tiempo": "4h",
            "dificultad": "baja",
        },
    ],
}


def init_recetas_mexicanas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for categoria, recetas in RECETAS_MEXICANA.items():
        for receta in recetas:
            c.execute(
                """
                INSERT OR IGNORE INTO recetas_cocina
                (cocina, categoria, nombre, descripcion, ingredientes, elaboracion, tiempo_preparacion, dificultad, created_at)
                VALUES ('mexicana', ?, ?, ?, ?, '', ?, ?, ?)
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

    query = "SELECT nombre, descripcion, ingredientes, tiempo_preparacion, dificultad FROM recetas_cocina WHERE cocina = 'mexicana'"
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
    init_recetas_mexicanas()
    print("=== COCINA MEXICANA ===")
    recetas = obtener_recetas()
    print(f"Total recetas: {len(recetas)}")
