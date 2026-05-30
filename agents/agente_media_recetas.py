"""
AGENTE GESTOR DE MEDIA RECETAS
Gestiona fotos, vídeos y fuentes de recetas
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"
RECETAS_MEDIA_PATH = Path(__file__).parent.parent / "biblioteca" / "recetas"

FUENTES_CONFIABLES = {
    "spain": {
        "nombre": "Directo al Paladar",
        "url": "https://www.directoalpaladar.com",
        "tipo": "web",
        "confianza": "alta",
    },
    "spain_2": {
        "nombre": "Recetas de Escándalo",
        "url": "https://www.recetasdeescandalo.com",
        "tipo": "web",
        "confianza": "alta",
    },
    "spain_3": {
        "nombre": "Canal Cocina",
        "url": "https://www.canalcocina.es",
        "tipo": "web",
        "confianza": "alta",
    },
    "italy": {
        "nombre": "Giallo Zafferano",
        "url": "https://www.giallozafferano.com",
        "tipo": "web",
        "confianza": "alta",
    },
    "italy_2": {
        "nombre": "Cooknsolo",
        "url": "https://www.cooknsolo.it",
        "tipo": "web",
        "confianza": "alta",
    },
    "latin": {
        "nombre": "Laylita",
        "url": "https://www.laylita.com",
        "tipo": "web",
        "confianza": "alta",
    },
    "peru": {
        "nombre": "Recetas Grilleras",
        "url": "https://recetasgrilleras.com",
        "tipo": "web",
        "confianza": "alta",
    },
    "mexico": {
        "nombre": "Directo al Paladar México",
        "url": "https://www.directoalpaladar.mx",
        "tipo": "web",
        "confianza": "alta",
    },
    "youtube_esp": {
        "nombre": "YouTube Cocina",
        "url": "youtube.com",
        "tipo": "video",
        "confianza": "alta",
    },
}


def init_media_recetas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS recetas_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receta_nombre TEXT NOT NULL,
            cocina TEXT NOT NULL,
            tipo_media TEXT NOT NULL,
            url TEXT,
            fuente TEXT,
            descripcion TEXT,
            local_path TEXT,
            fecha_agregado TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS recetas_variantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receta_base TEXT NOT NULL,
            cocina TEXT NOT NULL,
            variante_nombre TEXT NOT NULL,
            ingredientes TEXT NOT NULL,
            elaboracion TEXT,
            notas TEXT,
            dificultad TEXT,
            tiempo TEXT,
            fuente TEXT,
            fecha_creacion TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def agregar_foto_receta(receta_nombre, cocina, url, fuente, descripcion="", local_path=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO recetas_media (receta_nombre, cocina, tipo_media, url, fuente, descripcion, local_path, fecha_agregado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            receta_nombre,
            cocina,
            "foto",
            url,
            fuente,
            descripcion,
            local_path,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def agregar_video_receta(receta_nombre, cocina, url, fuente, descripcion=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO recetas_media (receta_nombre, cocina, tipo_media, url, fuente, descripcion, fecha_agregado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (receta_nombre, cocina, "video", url, fuente, descripcion, datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()


def obtener_media_receta(receta_nombre):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT tipo_media, url, fuente, descripcion, local_path
        FROM recetas_media WHERE receta_nombre = ?
    """,
        (receta_nombre,),
    )

    resultados = c.fetchall()
    conn.close()

    media = {"fotos": [], "videos": []}
    for r in resultados:
        item = {"url": r[1], "fuente": r[2], "descripcion": r[3], "local": r[4]}
        if r[0] == "foto":
            media["fotos"].append(item)
        else:
            media["videos"].append(item)

    return media


def buscar_videos_receta(nombre_plato):
    busquedas_youtube = [
        f"site:youtube.com {nombre_plato} receta",
        f"site:youtube.com {nombre_plato} como hacer",
        f"site:youtube.com {nombre_plato} tutorial",
    ]

    return {
        "busquedas_sugeridas": busquedas_youtube,
        "nota": "Buscar en YouTube con estas consultas para encontrar vídeos de calidad",
        "canales_confiables": [
            "Canalcocina",
            "Karlos Arguiñano",
            "Jamie Oliver (español)",
            "Mexicanisimo",
            "Recetas de Juanqui",
        ],
    }


def listar_fuentes():
    return FUENTES_CONFIABLES


def sincronizar_photos_recetas():
    fotos_local = {}

    for subdir in ["fotos", "española", "italiana", "peruana", "mexicana"]:
        path = RECETAS_MEDIA_PATH / subdir
        if path.exists():
            fotos = list(path.glob("*.*"))
            fotos_local[subdir] = [str(f) for f in fotos]

    return fotos_local


class AgenteMediaRecetas:
    """Wrapper para AgenteMediaRecetas."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteMediaRecetas."""
        return "Puedo buscar fotos y vídeos de recetas para inspirarte. ¿Qué plato quieres ver?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteMediaRecetas."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteMediaRecetas."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteMediaRecetas."""
        return self.procesar(texto)


if __name__ == "__main__":
    init_media_recetas()

    print("=== MEDIA RECETAS ===\n")
    print("📚 Fuentes confiables:")
    for _key, fuente in FUENTES_CONFIABLES.items():
        print(f"  • {fuente['nombre']} ({fuente['confianza']})")

    print("\n📁 Fotos locales:")
    print(sincronizar_photos_recetas())

    print("\n🎥 Búsqueda de vídeos:")
    print(buscar_videos_receta("paella"))
