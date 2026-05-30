"""
VOCABULARIO GASTRONÓMICO - Descripciones bonitas para cartas y menús
Incluye adjetivos, formas de describir platos, técnicas culinarias
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

ADJETIVOS_COMIDA = {
    "textura": [
        "cremoso",
        "crujiente",
        "fundente",
        "al dente",
        "esponjoso",
        "sedoso",
        "espetante",
        "suave",
    ],
    "sabor": [
        "intenso",
        "delicado",
        "equilibrado",
        "potente",
        "suave",
        "vigorizante",
        "sabroso",
        "reconfortante",
    ],
    "elaboracion": [
        "artesanal",
        "casero",
        "artesanal",
        "de temporada",
        "de mercado",
        "a fuego lento",
    ],
    "calidad": [
        "premium",
        "de primera",
        "seleccionado",
        "premium",
        "de origen",
        "Km0",
        "ecológico",
    ],
    "presentacion": ["bonito", "decorado", "artístico", "minimalista", "tradicional", "gourmet"],
    "temperatura": ["humeante", "caliente", "tibio", "recién hecho", "fresco", "frío"],
}

TECNICAS_CULINARIAS = [
    ("a la brasa", "cocción sobre carbones vegetales"),
    ("al horno", "cocción en calor seco envolvente"),
    ("a la plancha", "cocción rápida sobre superficie metálica caliente"),
    ("en su punto", "cocción perfecta, ni crudo ni pasado"),
    ("escabechado", "cocción en vinagre con especias"),
    ("empanado", "recubierto de pan rallado antes de freír"),
    ("braseado", "cocción lenta en líquido"),
    ("ahumado", "cocción mediante humo de madera"),
    ("marinado", "cocción previa en adobo"),
    ("rehogado", "cocción rápida en aceite caliente"),
]

DESCRIPCIONES_POR_TIPO = {
    "legumbres": [
        "de la abuela, cocidas a fuego lento durante horas",
        "con el toque de nuestra casa que las hace únicas",
        "de temporada, cocinadas como mandan nuestros mayores",
        "cremosas por fuera, enteras por dentro",
    ],
    "carnes": [
        "de raza selecta, madurada {dias} días",
        "al punto exacto que tú pidas",
        "cortada a cuchillo por nuestro carnicero",
        "de cercanía, de ganaderías de Navarra",
    ],
    "pescados": [
        "del Cantábrico, capturado hoy mismo",
        "de mercado, lo más fresco que puedas encontrar",
        "a la espalda, con su propia salsa",
        "en su punto, se deshace en la boca",
    ],
    "verduras": [
        "de huerta, directas del mercado",
        "al vapor, conservando todas sus vitaminas",
        "de temporada, de la huerta navarra",
        "crujientes, recién cogidas",
    ],
    "arroz": [
        "seco, con el fondo tostado perfecto",
        "cremoso, como lo hacen en Valencia",
        "con azafrán de la Mancha",
        "de caldera, para compartir",
    ],
    "pasta": [
        "al dente, como en Italia",
        "fresca, hecha en casa cada día",
        "de sémola de trigo duro",
        "artesanal, según la tradición italiana",
    ],
    "postres": [
        "de casa, como los hacía tu abuela",
        "artesanal, hecho cada mañana",
        "sin conservantes, solo con ingredientes naturales",
        "para los más golosos",
    ],
}

INICIOS_CARTA = [
    "Os presentamos",
    "Hoy os recomendamos",
    "No te puedes perder",
    "La especialidad de la casa:",
    "Directo del mercado a tu mesa:",
    "Elaborado con cariño:",
    "El plato estrella:",
]


def init_vocabulario_gastronomico():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for categoria, adjetivos in ADJETIVOS_COMIDA.items():
        for adjetivo in adjetivos:
            c.execute(
                """
                INSERT OR IGNORE INTO biblioteca_vocabulario
                (categoria, termino, definicion, ejemplo, sinonimos, area, created_at)
                VALUES ('gastronomico', ?, ?, ?, ?, 'adjetivos', ?)
            """,
                (
                    adjetivo,
                    f"Adjetivo para describir comida - {categoria}",
                    f"Plato {adjetivo}",
                    "",
                    datetime.now().isoformat(),
                ),
            )

    for tecnica, descripcion in TECNICAS_CULINARIAS:
        c.execute(
            """
            INSERT OR IGNORE INTO biblioteca_vocabulario
            (categoria, termino, definicion, ejemplo, sinonimos, area, created_at)
            VALUES ('gastronomico', ?, ?, ?, ?, 'tecnicas', ?)
        """,
            (tecnica, descripcion, f"Preparado {tecnica}", "", datetime.now().isoformat()),
        )

    conn.commit()
    conn.close()


def describir_plato(nombre_plato, tipo=None, dias_maduracion=0):
    import random

    if tipo and tipo in DESCRIPCIONES_POR_TIPO:
        descripciones = DESCRIPCIONES_POR_TIPO[tipo]
        descripcion = random.choice(descripciones)
        descripcion = descripcion.format(dias=dias_maduracion)
    else:
        inicio = random.choice(INICIOS_CARTA)
        adj = random.choice([a for adjectives in ADJETIVOS_COMIDA.values() for a in adjectives])
        descripcion = f"{inicio} {nombre_plato}, {adj}"

    return descripcion


def generar_linea_carta(nombre_plato, precio=None, descripcion=None, tipo=None):
    if descripcion is None:
        descripcion = describir_plato(nombre_plato, tipo)

    linea = f"**{nombre_plato}**"
    if descripcion:
        linea += f"\n   {descripcion}"
    if precio:
        linea += f"\n   {precio} €"

    return linea


def crear_menu_del_dia(primeros, segundos, precios=None):
    import random

    menu = "═" * 40 + "\n"
    menu += "   🍽️  MENÚ DEL DÍA  🍽️\n"
    menu += "═" * 40 + "\n\n"

    menu += "📌 PRIMEROS\n"
    menu += "-" * 30 + "\n"
    for i, plato in enumerate(primeros):
        desc = random.choice(DESCRIPCIONES_POR_TIPO.get("legumbres", ["de temporada"]))
        if precios:
            menu += f"{i + 1}. {plato} - {desc}\n   {precios[0]} €\n\n"
        else:
            menu += f"{i + 1}. {plato} - {desc}\n\n"

    menu += "📌 SEGUNDOS\n"
    menu += "-" * 30 + "\n"
    for i, plato in enumerate(segundos):
        desc = random.choice(DESCRIPCIONES_POR_TIPO.get("carnes", ["de calidad"]))
        if precios and len(precios) > 1:
            menu += f"{i + 1}. {plato} - {desc}\n   {precios[1]} €\n\n"
        else:
            menu += f"{i + 1}. {plato} - {desc}\n\n"

    menu += "═" * 40 + "\n"
    menu += "🍷 Bebida + Pan + Café incluidos\n"
    menu += "═" * 40 + "\n"

    return menu


def enriquecer_receta(nombre, ingredientes=None):
    import random

    resultado = {"nombre": nombre, "titulo_carta": None, "descripcion": None, "palabras_clave": []}

    adjetivo = random.choice([a for adjectives in ADJETIVOS_COMIDA.values() for a in adjectives])
    inicio = random.choice(INICIOS_CARTA)

    resultado["titulo_carta"] = f"{nombre}"
    resultado["descripcion"] = f"{inicio} {nombre}, {adjetivo}"
    resultado["palabras_clave"] = [adjetivo, nombre.lower()]

    return resultado


class AgenteVocabularioGastronomico:
    """Wrapper para AgenteVocabularioGastronomico."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVocabularioGastronomico."""
        return "Puedo ayudarte con términos culinarios y descripciones de platos. ¿Qué palabra gastronómica necesitas definir?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVocabularioGastronomico."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVocabularioGastronomico."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVocabularioGastronomico."""
        return self.procesar(texto)


if __name__ == "__main__":
    init_vocabulario_gastronomico()

    print("=== VOCABULARIO GASTRONÓMICO ===\n")

    print("Ejemplos de líneas para carta:\n")
    print(generar_linea_carta("Lentejas con chorizo", tipo="legumbres"))
    print()
    print(generar_linea_carta("Solomillo al vino tinto", tipo="carnes"))
    print()
    print(generar_linea_carta("Bacalao a la espalda", tipo="pescados"))
    print()

    print("\nMenú del día ejemplo:\n")
    print(
        crear_menu_del_dia(
            ["Lentejas", "Ensalada César", "Arroz caldoso"],
            ["Merluza a la romana", "Pollo asado", "Filete con patatas"],
        )
    )
