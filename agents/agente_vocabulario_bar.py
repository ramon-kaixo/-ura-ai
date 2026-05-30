"""
AGENTE VOCABULARIO BAR - Términos de hostelería/restaurante
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

TERMINOS_BAR = [
    (
        "tapa",
        "Pequeña porción de comida servida con la bebida, tradición española",
        "Unos pintxos en San Sebastián",
        "bocadillo, ración",
    ),
    (
        "ración",
        "Porción completa de un plato para compartir",
        "Una ración de patatas bravas",
        "tapa, plato",
    ),
    (
        "cubata",
        "Bebida preparada con aguardiente o ron y refresco",
        "Un cubata de ron con cola",
        "combinado, copa",
    ),
    ("copa", "Bebida alcoholicaguardiente o ron y refresco", "Una copa de whisky", "vaso, cubata"),
    ("barra", "Mostrador donde se sirven las bebidas", "Ponerse en la barra", "mostrador"),
    ("cuenta", "Registro de lo consumido para pagar", "La cuenta, por favor", "factura, ticket"),
    ("propina", "Cantidad extra voluntaria para el personal", "Dejar la propina", "servicio"),
    ("terraza", "Área exterior del local para sentarse", "Poner la terraza", "velador, veladores"),
    ("emplatado", "Forma de presentar la comida en el plato", "Bonito emplatado", "presentación"),
    ("carta", "Lista de platos y precios del restaurante", "Traer la carta", "menú"),
    (
        "carta de vinos",
        "Lista de vinos disponibles",
        "La carta de vinos tiene rioja",
        "vinos, bodega",
    ),
    ("tique", "Documento que detalla lo consumido", "El tique no tiene IVA", "cuenta, factura"),
    (
        "factura",
        "Documento fiscal oficial de la compra",
        "Necesito factura para la empresa",
        "tique, recibo",
    ),
    (
        "albarán",
        "Documento de entrega de mercancía",
        "Recibir el albarán del proveedor",
        "nota de entrega",
    ),
    ("playlist", "Lista de reproducción musical", "Cambiar la playlist", "música, fondo musical"),
    ("caja", "Dinero en efectivo del local", "Hacer la caja al cerrar", "efectivo, tesorería"),
    ("cuadradocaja", "Reconciliación del dinero en caja", "El cuadradocaja cuadra", "caja, arqueo"),
    (
        "proveedor",
        "Empresa que suministra productos",
        "Llamar al proveedor de bebida",
        "suministrador",
    ),
    (
        "merchandising",
        "Promoción de productos en el local",
        "Tener merchandising de marcas",
        "promoción",
    ),
    (
        "happyhour",
        "Horas con descuentos en bebidas",
        "La happy hour es de 6 a 8",
        "descuento, oferta",
    ),
]


def init_vocabulario_bar():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for termino, definicion, ejemplo, sinonimos in TERMINOS_BAR:
        c.execute(
            """
            INSERT OR IGNORE INTO biblioteca_vocabulario (categoria, termino, definicion, ejemplo, sinonimos, created_at)
            VALUES ('bar', ?, ?, ?, ?, ?)
        """,
            (termino, definicion, ejemplo, sinonimos, datetime.now().isoformat()),
        )

    conn.commit()
    conn.close()


def buscar_termino(termino):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT termino, definicion, ejemplo, sinonimos FROM biblioteca_vocabulario
        WHERE categoria = 'bar' AND termino LIKE ?
    """,
        (f"%{termino}%",),
    )

    resultados = c.fetchall()
    conn.close()

    if resultados:
        return [
            {"termino": r[0], "definicion": r[1], "ejemplo": r[2], "sinonimos": r[3]}
            for r in resultados
        ]

    return [{"error": f"No encontrado: {termino}"}]


def agregar_termino(termino, definicion, ejemplo="", sinonimos=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO biblioteca_vocabulario (categoria, termino, definicion, ejemplo, sinonimos, created_at)
        VALUES ('bar', ?, ?, ?, ?, ?)
    """,
        (termino, definicion, ejemplo, sinonimos, datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()

    return {"success": True, "termino": termino}


def listar_todos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT termino, definicion FROM biblioteca_vocabulario WHERE categoria = 'bar'")

    resultados = c.fetchall()
    conn.close()

    return [{"termino": r[0], "definicion": r[1]} for r in resultados]


class AgenteVocabularioBar:
    """Wrapper para AgenteVocabularioBar."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVocabularioBar."""
        return "Puedo explicar términos de hostelería y cocina profesional. ¿Qué término necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVocabularioBar."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVocabularioBar."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVocabularioBar."""
        return self.procesar(texto)


if __name__ == "__main__":
    init_vocabulario_bar()
    print("=== Vocabulario Bar ===")
    terminos = listar_todos()
    print(f"Total términos: {len(terminos)}")
    for t in terminos:
        print(f"  - {t['termino']}: {t['definicion'][:50]}...")
