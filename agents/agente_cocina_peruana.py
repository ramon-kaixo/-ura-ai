"""
AGENTE COCINA PERUANA - Recetas tradicionales del Perú
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

CATEGORIAS = {
    "entradas": "Entradas y ceviches",
    "segundos": "Platos de fondo principales",
    "sopas": "Sopas y caldos",
    "postres": "Postres peruanos",
}

RECETAS_PERUANA = {
    "entradas": [
        {
            "nombre": "Ceviche Clásico",
            "descripcion": "Pescado crudo marinado en limón, cebolla y ají",
            "ingredientes": [
                "corvina",
                "limón",
                "cebolla morada",
                "ají amarillo",
                "cilantro",
                "sal",
                "camote",
            ],
            "tiempo": "30 min",
            "dificultad": "media",
        },
        {
            "nombre": "Ceviche de Pulpo",
            "descripcion": "Pulpo marinado al estilo peruano",
            "ingredientes": ["pulpo", "limón", "cebolla", "ají amarillo", "cilantro"],
            "tiempo": "40 min",
            "dificultad": "media",
        },
        {
            "nombre": "Tiradito",
            "descripcion": "Finas láminas de pescado con salsa picante",
            "ingredientes": ["lenguado", "limón", "ají amarillo", "jitomate", "cebolla"],
            "tiempo": "25 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Anticucho",
            "descripcion": "Corazón de res a la parrilla con especias",
            "ingredientes": ["corazón res", "ají panca", "comino", "vinagre", "patatas"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Palta Rellena",
            "descripcion": "Palta rellena con atún y mayonesa",
            "ingredientes": ["palta", "atún", "mayonesa", "apio", "limón"],
            "tiempo": "20 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Causa Limeña",
            "descripcion": "Puré de papa amarilla con pollo o atún",
            "ingredientes": ["papa amarilla", "ají amarillo", "limón", "pollo", "palta"],
            "tiempo": "45 min",
            "dificultad": "media",
        },
    ],
    "segundos": [
        {
            "nombre": "Lomo Saltado",
            "descripcion": "Ternera saltada con cebolla, tomate y arroz",
            "ingredientes": [
                "lomo fino",
                "cebolla",
                "tomate",
                "ají amarillo",
                "salsa soja",
                "arroz",
                "patatas fritas",
            ],
            "tiempo": "30 min",
            "dificultad": "media",
        },
        {
            "nombre": "Aji de Gallina",
            "descripcion": "Pollo deshilachado en salsa cremosa de ají",
            "ingredientes": ["pollo", "ají amarillo", "nueces", "pan", "leche", "queso"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Seco de Res",
            "descripcion": "Guiso de ternera con cilantro y cerveza",
            "ingredientes": [
                "carne res",
                "cilantro",
                "cerveza",
                "cebolla",
                "ají amarillo",
                "arroz",
            ],
            "tiempo": "2h",
            "dificultad": "media",
        },
        {
            "nombre": "Pollo a la Brasa",
            "descripcion": "Pollo asado al estilo peruano con anticuchera",
            "ingredientes": ["pollo entero", "ají panca", "comino", "ajo", "cerveza", "patatas"],
            "tiempo": "1h 30min",
            "dificultad": "media",
        },
        {
            "nombre": "Tacú",
            "descripcion": "Pasta de harina de arroz con salsa de maní",
            "ingredientes": ["harina arroz", "maní", "cebolla", "aji", "carne"],
            "tiempo": "1h",
            "dificultad": "alta",
        },
        {
            "nombre": "Arroz con Mariscos",
            "descripcion": "Arroz con mix de mariscos al estilo peruano",
            "ingredientes": ["arroz", "mariscos", "cerveza", "ají amarillo", "cebolla", "cilantro"],
            "tiempo": "45 min",
            "dificultad": "media",
        },
        {
            "nombre": "Chicharrón de Cerdo",
            "descripcion": "Cerdo frito crujiente con mote",
            "ingredientes": ["pierna cerdo", "chicha de jora", "maíz mote", "salsa criolla"],
            "tiempo": "2h",
            "dificultad": "media",
        },
        {
            "nombre": "Cuy Chactado",
            "descripcion": "Cuy frito crujiente (Andean guinea pig)",
            "ingredientes": ["cuy", "ajo", "comino", "cerveza", "papa"],
            "tiempo": "1h",
            "dificultad": "alta",
        },
    ],
    "sopas": [
        {
            "nombre": "Parihuela",
            "descripcion": "Sopa de mariscos peruana estilo francés",
            "ingredientes": ["mariscos", "tomate", "cebolla", "ají amarillo", "hierbas", "pescado"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Caldo de Gallina",
            "descripcion": "Caldo espeso de gallina con fideos",
            "ingredientes": ["gallina", "fideos", "huevo", "pasas", "algarrobina"],
            "tiempo": "3h",
            "dificultad": "media",
        },
        {
            "nombre": "Sopa a la Minuta",
            "descripcion": "Sopa de carne con huevo escalfado",
            "ingredientes": ["carne molida", "huevo", "leche", "verduras", "fideos"],
            "tiempo": "30 min",
            "dificultad": "baja",
        },
        {
            "nombre": "Chupe de Camarones",
            "descripcion": "Sopa espesa de camarones con queso",
            "ingredientes": ["camarones", "papa", "huevo", "queso fresco", "ají amarillo"],
            "tiempo": "45 min",
            "dificultad": "media",
        },
    ],
    "postres": [
        {
            "nombre": "Suspiro Limeño",
            "descripcion": "Postre de leche quemada con merengue",
            "ingredientes": ["leche", "yemas", "azúcar", "vino oporto", "merengue"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Alfajores",
            "descripcion": "Galletas rellenas de manjar blanco",
            "ingredientes": ["harina", "mantequilla", "maicena", "dulce de leche", "coco"],
            "tiempo": "1h",
            "dificultad": "baja",
        },
        {
            "nombre": "Turrón de Doña Pepa",
            "descripcion": "Turrón dulce con miel y frutas",
            "ingredientes": ["harina", "miel", "anís", "frutas confitadas", "huevo"],
            "tiempo": "1h",
            "dificultad": "media",
        },
        {
            "nombre": "Picarones",
            "descripcion": "Rosquillas fritas con miel de chancaca",
            "ingredientes": ["camote", "harina", "anís", "chancaca", "canela"],
            "tiempo": "1h",
            "dificultad": "alta",
        },
        {
            "nombre": "Mazamorra Morada",
            "descripcion": "Pudin morado de maíz con frutas",
            "ingredientes": ["maíz morado", "piña", "naranja", "chancaca", "canela"],
            "tiempo": "2h",
            "dificultad": "media",
        },
    ],
}


def init_recetas_peruanas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for categoria, recetas in RECETAS_PERUANA.items():
        for receta in recetas:
            c.execute(
                """
                INSERT OR IGNORE INTO recetas_cocina
                (cocina, categoria, nombre, descripcion, ingredientes, elaboracion, tiempo_preparacion, dificultad, created_at)
                VALUES ('peruana', ?, ?, ?, ?, '', ?, ?, ?)
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

    query = "SELECT nombre, descripcion, ingredientes, tiempo_preparacion, dificultad FROM recetas_cocina WHERE cocina = 'peruana'"
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


class AgenteCocinaPeruana:
    """Agente para cocina peruana."""

    def __init__(self):
        """Inicializar agente."""
        self.nombre = "Agente Cocina Peruana"
        init_recetas_peruanas()

    def procesar(self, texto: str) -> str:
        """Procesar consulta para cocina peruana."""
        texto_lower = texto.lower()

        # Buscar categoría
        categoria = None
        if "entrada" in texto_lower or "ceviche" in texto_lower:
            categoria = "entradas"
        elif "segundo" in texto_lower or "plato" in texto_lower:
            categoria = "segundos"
        elif "sopa" in texto_lower or "caldo" in texto_lower:
            categoria = "sopas"
        elif "postre" in texto_lower:
            categoria = "postres"

        recetas = obtener_recetas(categoria)

        if recetas:
            resultado = f"Recetas de cocina peruana ({categoria if categoria else 'todas'}):\n"
            for r in recetas[:5]:  # Mostrar máximo 5
                resultado += f"- {r['nombre']}: {r['descripcion']}\n"
            return resultado
        else:
            return "No se encontraron recetas de cocina peruana."

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para cocina peruana."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para cocina peruana."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para cocina peruana."""
        return self.procesar(texto)


if __name__ == "__main__":
    init_recetas_peruanas()
    print("=== COCINA PERUANA ===")
    recetas = obtener_recetas()
    print(f"Total recetas: {len(recetas)}")
