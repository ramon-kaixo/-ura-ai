#!/usr/bin/env python3
"""
agente_marketing.py — URA Agente de Marketing
==============================================
Gestión de redes sociales y marketing para tu bar.

Capacidades:
- Crear carteles para Instagram
- Generar ofertas y promociones
- Programar publicaciones
- Analizar engagement
- Sugerencias de contenido

Requiere:
- Facebook Graph API (para Instagram)
- Acceso a página de Facebook
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

try:
    REQUESTS_OK = True
except:
    REQUESTS_OK = False

logger = logging.getLogger(__name__)


class AgenteMarketing:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        logger.info(f"Inicializando AgenteMarketing con db_path={db_path}")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS marketing_publicaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                red_social TEXT NOT NULL,
                tipo TEXT NOT NULL,
                contenido TEXT NOT NULL,
                imagen_url TEXT,
                programacion TEXT,
                publicada INTEGER DEFAULT 0,
                engagement INTEGER DEFAULT 0,
                creada_en TEXT NOT NULL
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS marketing_ofertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                descripcion TEXT,
                descuento TEXT,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                activa INTEGER DEFAULT 1,
                creada_en TEXT NOT NULL
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS marketing_estadisticas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                red_social TEXT,
                metricas TEXT,
                fecha TEXT
            )
        """
        )
        conn.commit()
        conn.close()

    def crear_cartel(self, titulo: str, texto: str, tipo: str = "oferta") -> int:
        """Crea un diseño de cartel para redes sociales."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO marketing_publicaciones
            (red_social, tipo, contenido, programacion, creada_en)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("instagram", tipo, f"{titulo}\n\n{texto}", ahora, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def oferta(self, titulo: str, descripcion: str, descuento: str, dias_validez: int = 7) -> int:
        """Registra una oferta."""
        ahora = datetime.now()
        fin = ahora + timedelta(days=dias_validez)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO marketing_ofertas
            (titulo, descripcion, descuento, fecha_inicio, fecha_fin, creada_en)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (titulo, descripcion, descuento, ahora.isoformat(), fin.isoformat(), ahora.isoformat()),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def sugerencias_contenido(self) -> list[str]:
        """Genera sugerencias de contenido para el bar."""
        ahora = datetime.now()
        sugerencias = []

        if ahora.weekday() == 0:  # Lunes
            sugerencias.append("🎯 #LunesSinCarne - Promociona alternativas vegetarianas")
        elif ahora.weekday() == 4:  # Viernes
            sugerencias.append("🎉 ¡Viernes de DJ! Comparte foto del equipo")
        elif ahora.weekday() == 5:  # Sábado
            sugerencias.append("🍸 #Sabadbtt - Cocktail especial del día")
        else:
            sugerencias.extend(
                [
                    "🍷 Degustación de vinos - Nueva carta",
                    "🎵 Tarde de jazz en vivo",
                    "🥂 Happy hour 18:00-20:00",
                    "🍔 Carta nueva: Hamburguesas artesanales",
                    "🎂 Celebra tu cumpleaños con nosotros",
                    "⚽ Evento deportivo - Resérvalo ya",
                ]
            )

        return sugerencias

    def generar_post(self, tema: str, incluir_hashtags: bool = True) -> str:
        """Genera texto para un post."""
        ahora = datetime.now()
        hashtags_base = "#bar #cerveza #copas #noche #ocio"

        templates = {
            "oferta": f"¡OFERTA ESPECIAL! 🎉\n\n{tema}\n\n⏰ Solo por hoy\n🏷️ {hashtags_base if incluir_hashtags else ''}",
            "evento": f"¡TE ESPERAMOS! 🎶\n\n{tema}\n\n📍 Tu bar favorito\n📅 {ahora.strftime('%d/%m/%Y')}\n\n{hashtags_base if incluir_hashtags else ''}",
            "producto": f"¡NUEVO! 🍽️\n\n{tema}\n\nVen a probarlo\n{hashtags_base if incluir_hashtags else ''}",
            "general": f"{tema}\n\n¡Te esperamos! {hashtags_base if incluir_hashtags else ''}",
        }

        return templates.get("general", templates["general"])

    def estadisticas(self, dias: int = 7) -> dict:
        """Obtiene estadísticas de publicaciones."""
        cutoff = (datetime.now() - timedelta(days=dias)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM marketing_publicaciones WHERE publicada = 1 AND creada_en >= ?
        """,
            (cutoff,),
        )
        publicadas = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM marketing_publicaciones WHERE publicada = 0 AND creada_en >= ?
        """,
            (cutoff,),
        )
        pendientes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM marketing_ofertas WHERE activa = 1")
        ofertas_activas = cursor.fetchone()[0]

        conn.close()
        return {
            "publicadas": publicadas,
            "pendientes": pendientes,
            "ofertas_activas": ofertas_activas,
            "periodo_dias": dias,
        }

    def listar_publicaciones(self, solo_pendientes: bool = True) -> list[dict]:
        """Lista publicaciones."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = "SELECT id, red_social, tipo, contenido, publicada, creada_en FROM marketing_publicaciones"
        if solo_pendientes:
            query += " WHERE publicada = 0"
        query += " ORDER BY creada_en DESC"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "red": r[1],
                "tipo": r[2],
                "contenido": r[3],
                "publicada": bool(r[4]),
                "creada": r[5],
            }
            for r in rows
        ]

    def marcar_publicada(self, publicacion_id: int) -> bool:
        """Marca una publicación como hecha."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE marketing_publicaciones SET publicada = 1 WHERE id = ?", (publicacion_id,)
        )
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteMarketing."""
        texto.lower()
        return "Puedo crear campañas en Instagram, Facebook y métricas. ¿Qué campaña de marketing necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteMarketing."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteMarketing."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteMarketing."""
        return self.procesar(texto)


if __name__ == "__main__":
    agente = AgenteMarketing()

    # Test: crear oferta
    oferta_id = agente.oferta(
        titulo="Happy Hour",
        descripcion="2x1 en copas de 18:00 a 20:00",
        descuento="50%",
        dias_validez=7,
    )
    print(f"Oferta creada: {oferta_id}")

    # Test: estadísticas
    stats = agente.estadisticas()
    print(f"Estadísticas: {stats}")
