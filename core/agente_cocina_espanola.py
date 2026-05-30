"""
AGENTE COCINA ESPAÑOLA - Recetas tradicionales de España
Incluye categorías: esterilizados/pasta, arroz, ensaladas, potajes, guisos, segundos
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AgenteCocinaEspanola:
    """Agente de cocina española con recetas tradicionales."""

    CATEGORIAS = {
        "esterilizados_pasta": "Platos de pasta y platos cocidos/en conserva",
        "arroz": "Arroces españoles",
        "ensaladas": "Ensaladas frías",
        "potajes": "Guisos de legumbres",
        "guisos": "Guisos y estofados",
        "segundos": "Carnes y pescados principales",
    }

    RECETAS_ESPANOLA = {
        "esterilizados_pasta": [
            {
                "nombre": "Macarrones a la boloñesa",
                "descripcion": "Pasta italiana con ragú de carne de ternera al estilo boloñés",
                "ingredientes": [
                    "macarrones",
                    "carne picada ternera",
                    "tomate",
                    "cebolla",
                    "zanahoria",
                    "vino tinto",
                    "parmesano",
                ],
                "elaboracion": "Sofríe cebolla, añade carne, incorpora tomate y vino. Cocina a fuego lento 2h. Sirve con pasta al dente.",
                "tiempo": "45 min",
                "dificultad": "media",
            },
            {
                "nombre": "Canelones",
                "descripcion": "Pasta fresca rellena de carne, gratinados con bechamel",
                "ingredientes": [
                    "láminas canelón",
                    "carne picada",
                    "tomate",
                    "cebolla",
                    "bechamel",
                    "queso mozzarella",
                ],
                "elaboracion": "Prepara ragú, rellena láminas, cubre con bechamel y queso. Hornea 20 min a 180°C.",
                "tiempo": "1h",
                "dificultad": "media",
            },
            {
                "nombre": "Pasta a la carbonara",
                "descripcion": "Spaghetti con salsa de yolk de huevo, guanciale y pecorino",
                "ingredientes": [
                    "spaghetti",
                    "yemas huevo",
                    "guanciale",
                    "pecorino romano",
                    "pimienta negra",
                ],
                "elaboracion": "Cocina pasta, dora guanciale, mezcla yolks con queso. Emulsiona con pasta caliente.",
                "tiempo": "25 min",
                "dificultad": "baja",
            },
            {
                "nombre": "Lasaña de carne",
                "descripcion": "Capas de pasta, ragú, bechamel y queso gratinado",
                "ingredientes": [
                    "láminas lasaña",
                    "carne picada",
                    "tomate",
                    "bechamel",
                    "mozzarella",
                    "parmesano",
                ],
                "elaboracion": "Prepara ragú, alterna capas con bechamel. Gratina 25 min a 200°C.",
                "tiempo": "1h 15min",
                "dificultad": "media",
            },
            {
                "nombre": "Espaguetis a la norma",
                "descripcion": "Pasta con salsa de tomate, berenjena frita y ricotta",
                "ingredientes": ["espaguetis", "tomate", "berenjena", "ricotta", "albahaca", "ajo"],
                "elaboracion": "Prepara salsa tomate, fríe berenjenas, sirve pasta con ricotta por encima.",
                "tiempo": "30 min",
                "dificultad": "baja",
            },
        ],
        "arroz": [
            {
                "nombre": "Paella Valenciana",
                "descripcion": "Arroz con pollo, conejo, judías verdes y garrofón",
                "ingredientes": [
                    "arroz senia",
                    "pollo",
                    "conejo",
                    "judías verdes",
                    "garrofón",
                    "tomate",
                    "azafrán",
                    "romero",
                ],
                "elaboracion": "Sofreír carnes, añadir verduras, tomate, caldo. Añadir arroz y azafrán. Cocer 18 min. Reposar 5 min.",
                "tiempo": "1h 15min",
                "dificultad": "media",
            },
            {
                "nombre": "Arroz Negro",
                "descripcion": "Arroz con tinta de calamar, mariscos",
                "ingredientes": [
                    "arroz",
                    "calamar",
                    "tinta calamar",
                    "fumet",
                    "pimiento rojo",
                    "cebolla",
                ],
                "elaboracion": "Preparar sofrito, añadir arroz, tinta y caldo. Cocer 18 min. Decorar con alioli.",
                "tiempo": "45 min",
                "dificultad": "media",
            },
            {
                "nombre": "Arroz Caldoso con Marisco",
                "descripcion": "Arroz caldoso con gambas, mejillones y almejas",
                "ingredientes": [
                    "arroz",
                    "gambas",
                    "mejillones",
                    "almejas",
                    "fumet",
                    "pimiento",
                    "cebolla",
                    "ajo",
                ],
                "elaboracion": "Preparar fumet, sofreír base, añadir arroz y mariscos. Cocer 20 min.",
                "tiempo": "50 min",
                "dificultad": "media",
            },
            {
                "nombre": "Arroz con Bogavante",
                "descripcion": "Arroz de alta cocina con bogavante",
                "ingredientes": [
                    "arroz",
                    "bogavante",
                    "fumet",
                    "tomate",
                    "cebolla",
                    "pimiento",
                    "cognac",
                ],
                "elaboracion": "Cocer bogavante, separar carne. Usar coral para color. Cocer arroz en fumet con bogavante.",
                "tiempo": "1h 30min",
                "dificultad": "alta",
            },
            {
                "nombre": "Paella de Mariscos",
                "descripcion": "Arroz con mix de mariscos del Mediterráneo",
                "ingredientes": [
                    "arroz",
                    "gambas",
                    "mejillones",
                    "sepia",
                    "calamares",
                    "tomate",
                    "azafrán",
                    "fumet",
                ],
                "elaboracion": "Sofreír mariscos, añadir tomate, arroz y caldo. 18 min de cocción.",
                "tiempo": "1h",
                "dificultad": "media",
            },
        ],
        "ensaladas": [
            {
                "nombre": "Ensaladilla Rusa",
                "descripcion": "Ensalada fría con patatas, zanahorias, guisantes y atún",
                "ingredientes": [
                    "patata",
                    "zanahoria",
                    "guisantes",
                    "huevo",
                    "atún",
                    "mayonesa",
                    "aceitunas",
                ],
                "elaboracion": "Cocer verduras, cortar todo en dados pequeños. Mezclar con mayonesa y atún. Enfriar.",
                "tiempo": "40 min",
                "dificultad": "baja",
            },
            {
                "nombre": "Ensalada de Bacalao",
                "descripcion": "Ensalada fresca con bacalao desmigado y naranja",
                "ingredientes": [
                    "bacalao desalado",
                    "naranja",
                    "aceitunas negras",
                    "cebolla morada",
                    "aceite oliva",
                    "vinagre",
                ],
                "elaboracion": "Desmigar bacalao, cortar cítricos, emulsionar aliño. Mezclar.",
                "tiempo": "20 min",
                "dificultad": "baja",
            },
            {
                "nombre": "Ensalada César",
                "descripcion": "Ensalada americana con lechuga romana, pollo, crutones y salsa César",
                "ingredientes": [
                    "lechuga romana",
                    "pollo",
                    "parmesano",
                    "crutones",
                    "salsa César",
                    "anchoas",
                ],
                "elaboracion": "Brasear pollo, montar plato con lechuga, añadir pollo, crutones y salsa.",
                "tiempo": "25 min",
                "dificultad": "baja",
            },
            {
                "nombre": "Ensalada de Perdiz",
                "descripcion": "Ensalada sofisticada con perdiz escabechada",
                "ingredientes": [
                    "perdiz",
                    "escabeche",
                    "lechugas variadas",
                    "naranja",
                    "granada",
                    "nueces",
                ],
                "elaboracion": "Deshuesar perdiz, laminar. Montar ensalada con frutos secos y cítricos.",
                "tiempo": "30 min",
                "dificultad": "media",
            },
        ],
        "potajes": [
            {
                "nombre": "Potaje de Garbanzos",
                "descripcion": "Guiso de garbanzos con espinacas y bacalao",
                "ingredientes": [
                    "garbanzos",
                    "espinacas",
                    "bacalao",
                    "huevo duro",
                    "pan",
                    "ajo",
                    "comino",
                ],
                "elaboracion": "Cocer garbanzos, añadir espinacas y bacalao. Añadir majado de ajo y comino.",
                "tiempo": "1h 30min",
                "dificultad": "media",
            },
            {
                "nombre": "Lentejas Estofadas",
                "descripcion": "Lentejas castellanas con chorizo y verduras",
                "ingredientes": [
                    "lentejas castellanas",
                    "chorizo",
                    "morcilla",
                    "cebolla",
                    "zanahoria",
                    "pimiento",
                    "laurel",
                ],
                "elaboracion": "Rehogar verduras, añadir carnes y lentejas. Cocer lento 1.5h.",
                "tiempo": "1h 45min",
                "dificultad": "baja",
            },
            {
                "nombre": "Judías Blancas con Chorizo",
                "descripcion": "Judías de la abuela con chorizo y tocino",
                "ingredientes": [
                    "judías blancas",
                    "chorizo",
                    "tocino",
                    "cebolla",
                    "ajo",
                    "pimiento",
                    "tomate",
                ],
                "elaboracion": "Remojar judías 12h, cocer con sofrito y chorizo 2h a fuego lento.",
                "tiempo": "3h",
                "dificultad": "media",
            },
            {
                "nombre": "Potaje de Verduras",
                "descripcion": "Guiso ligero de verduras de temporada",
                "ingredientes": [
                    "garbanzos",
                    "calabaza",
                    "berenjena",
                    "pimiento",
                    "cebolla",
                    "espinacas",
                ],
                "elaboracion": "Cocer garbanzos, añadir verduras en sofrito. Cocer 30 min.",
                "tiempo": "1h 30min",
                "dificultad": "baja",
            },
        ],
        "guisos": [
            {
                "nombre": "Cochinillo asado",
                "descripcion": "Lechazo manchego al horno con hierbas",
                "ingredientes": ["cochinillo", "ajo", "romero", "tomillo", "aceite", "sal gruesa"],
                "elaboracion": "Adobar 24h, asar 3h a horno bajo 150°C. Gratinar al final.",
                "tiempo": "4h",
                "dificultad": "alta",
            },
            {
                "nombre": "Callos a la Madrileña",
                "descripcion": "Guiso de callos con garbanzos y morcilla",
                "ingredientes": [
                    "callos",
                    "garbanzos",
                    "morcilla",
                    "jamón",
                    "chorizo",
                    "tomate",
                    "nervios",
                ],
                "elaboracion": "Limpiar callos, hervir 3h con huesos. Guisar con sofrito y garbanzos.",
                "tiempo": "4h",
                "dificultad": "alta",
            },
            {
                "nombre": "Rabo de Toro Estofado",
                "descripcion": "Rabo de toro cocido lentamente en vino Rioja",
                "ingredientes": [
                    "rabo toro",
                    "vino Rioja",
                    "cebolla",
                    "zanahoria",
                    "apio",
                    "tomate",
                    "laurel",
                ],
                "elaboracion": "Marinar 24h, dorar carne, sofreír verduras, añadir vino. Estofar 3h.",
                "tiempo": "4h+",
                "dificultad": "alta",
            },
            {
                "nombre": "Guiso de Carne a la Miel",
                "descripcion": "Ternera guisada con miel y especias",
                "ingredientes": ["ternera", "miel", "romero", "ajo", "vino blanco", "cebolla"],
                "elaboracion": "Dorar carne, añadir sofrito, miel y vino. Cocer lento 2h.",
                "tiempo": "2h 30min",
                "dificultad": "media",
            },
            {
                "nombre": "Fabada Asturiana",
                "descripcion": "Guiso de fabes con lacón, chorizo y compango",
                "ingredientes": ["fabes", "lacón", "chorizo", "morcilla", "compango"],
                "elaboracion": "Cocer fabes overnight con compango. Sobar al final para espesar.",
                "tiempo": "12h",
                "dificultad": "alta",
            },
        ],
        "segundos": [
            {
                "nombre": "Merluza a la Romana",
                "descripcion": "Merluza rebozada en harina y huevo, frita",
                "ingredientes": ["merluza", "harina", "huevo", "aceite", "sal", "limón"],
                "elaboracion": "Cortar merluza en rodajas, empanar con harina y huevo. Freír 180°C.",
                "tiempo": "20 min",
                "dificultad": "baja",
            },
            {
                "nombre": "Solomillo al Whisky",
                "descripcion": "Solomillo de cerdo con salsa de whisky y nata",
                "ingredientes": [
                    "solomillo cerdo",
                    "whisky",
                    "nata",
                    "cebolla",
                    "champiñones",
                    "mantequilla",
                ],
                "elaboracion": "Sellar solomillo, hacer salsa con whisky flameado y nata. Servir cortado.",
                "tiempo": "35 min",
                "dificultad": "media",
            },
            {
                "nombre": "Rodaballo a la Parrilla",
                "descripcion": "Rodaballo fresco a la brasa con alioli",
                "ingredientes": ["rodaballo", "aceite", "ajo", "limón", "perejil"],
                "elaboracion": "Limpiar rodaballo, salar, asar a la brasa 15 min por lado.",
                "tiempo": "40 min",
                "dificultad": "media",
            },
            {
                "nombre": "Pollo al Limón",
                "descripcion": "Pollo asado con limón y hierbas provenzales",
                "ingredientes": [
                    "pollo",
                    "limón",
                    "ajo",
                    "romero",
                    "tomillo",
                    "aceite",
                    "vino blanco",
                ],
                "elaboracion": "Adobar pollo con limón y hierbas. Asar 1h a 180°C.",
                "tiempo": "1h 15min",
                "dificultad": "baja",
            },
            {
                "nombre": "Ternera a la Plancha",
                "descripcion": "Entrecot de ternera a la plancha con hierbas",
                "ingredientes": ["entrecot ternera", "romero", "ajo", "aceite", "sal Maldon"],
                "elaboracion": "Sellar a fuego alto 3 min por lado. Reposar 5 min. Cortar y servir.",
                "tiempo": "15 min",
                "dificultad": "baja",
            },
        ],
    }

    def __init__(self, db_path: str | None = None):
        """Inicializar agente de cocina española."""
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        logger.info(f"Inicializando AgenteCocinaEspañola con db_path={db_path}")
        self._init_db()

    def _init_db(self):
        """Inicializar tabla de recetas."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS recetas_cocina (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cocina TEXT NOT NULL,
                categoria TEXT NOT NULL,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                ingredientes TEXT,
                elaboracion TEXT,
                tiempo_preparacion TEXT,
                dificultad TEXT,
                created_at TEXT NOT NULL
            )
        """
        )

        for categoria, recetas in self.RECETAS_ESPANOLA.items():
            for receta in recetas:
                c.execute(
                    """
                    INSERT OR IGNORE INTO recetas_cocina
                    (cocina, categoria, nombre, descripcion, ingredientes, elaboracion, tiempo_preparacion, dificultad, created_at)
                    VALUES ('española', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        categoria,
                        receta["nombre"],
                        receta["descripcion"],
                        ",".join(receta["ingredientes"]),
                        receta["elaboracion"],
                        receta["tiempo"],
                        receta["dificultad"],
                        datetime.now().isoformat(),
                    ),
                )

        conn.commit()
        conn.close()

    def obtener_recetas(self, categoria: str = None, dificultad: str = None) -> list[dict]:
        """Obtener recetas filtrando por categoría y/o dificultad."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        query = "SELECT nombre, descripcion, ingredientes, elaboracion, tiempo_preparacion, dificultad FROM recetas_cocina WHERE cocina = 'española'"
        params = []

        if categoria:
            query += " AND categoria = ?"
            params.append(categoria)

        if dificultad:
            query += " AND dificultad = ?"
            params.append(dificultad)

        c.execute(query, params)
        resultados = c.fetchall()
        conn.close()

        return [
            {
                "nombre": r[0],
                "descripcion": r[1],
                "ingredientes": r[2].split(","),
                "elaboracion": r[3],
                "tiempo": r[4],
                "dificultad": r[5],
            }
            for r in resultados
        ]

    def buscar_receta(self, termino: str) -> list[dict]:
        """Buscar recetas por término."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT nombre, descripcion, categoria FROM recetas_cocina
            WHERE cocina = 'española' AND (nombre LIKE ? OR descripcion LIKE ?)
        """,
            (f"%{termino}%", f"%{termino}%"),
        )

        resultados = c.fetchall()
        conn.close()

        return [{"nombre": r[0], "descripcion": r[1], "categoria": r[2]} for r in resultados]

    def listar_categorias(self) -> dict:
        """Listar categorías disponibles."""
        return self.CATEGORIAS

    def procesar(self, texto: str) -> str:
        """Procesar consulta sobre cocina española."""
        texto_lower = texto.lower()

        # Buscar receta por término
        if "receta" in texto_lower or "buscar" in texto_lower:
            termino = texto_lower.replace("receta", "").replace("buscar", "").strip()
            if termino:
                recetas = self.buscar_receta(termino)
                if recetas:
                    return f"Recetas encontradas para '{termino}':\n" + "\n".join(
                        [f"- {r['nombre']}: {r['descripcion']}" for r in recetas]
                    )
                return f"No se encontraron recetas para '{termino}'"

        # Listar categorías
        if "categoría" in texto_lower or "categorias" in texto_lower:
            categorias = self.listar_categorias()
            return "Categorías de cocina española:\n" + "\n".join(
                [f"- {cat}: {desc}" for cat, desc in categorias.items()]
            )

        # Obtener recetas por dificultad
        if "fácil" in texto_lower or "baja" in texto_lower:
            recetas = self.obtener_recetas(dificultad="baja")
            return "Recetas fáciles:\n" + "\n".join(
                [f"- {r['nombre']}: {r['tiempo']}" for r in recetas]
            )

        if "difícil" in texto_lower or "alta" in texto_lower:
            recetas = self.obtener_recetas(dificultad="alta")
            return "Recetas difíciles:\n" + "\n".join(
                [f"- {r['nombre']}: {r['tiempo']}" for r in recetas]
            )

        # Por defecto, buscar recetas por categoría
        for categoria in self.CATEGORIAS:
            if categoria.replace("_", " ") in texto_lower:
                recetas = self.obtener_recetas(categoria=categoria)
                return f"Recetas de {categoria.replace('_', ' ')}:\n" + "\n".join(
                    [f"- {r['nombre']}: {r['tiempo']}" for r in recetas[:5]]
                )

        return "Agente de cocina española disponible. Puedo buscar recetas, listar categorías o filtrar por dificultad."

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción específica sobre cocina española."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información sobre cocina española."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta sobre cocina española."""
        return self.procesar(texto)


if __name__ == "__main__":
    agente = AgenteCocinaEspañola()

    print("=== COCINA ESPAÑOLA ===")
    print("\nCategorías disponibles:")
    for cat, _desc in agente.listar_categorias().items():
        recetas = agente.obtener_recetas(categoria=cat)
        print(f"\n📁 {cat}: {len(recetas)} recetas")
        for r in recetas[:2]:
            print(f"   - {r['nombre']}")
