#!/usr/bin/env python3
"""
Agente Gastronómico y Musical para Bar - URA System
Especializado en cocina de alta gastronomía y curación musical
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

sys.path.append("..")
from utils.agent_base_stability import AgentStabilityBase


class AgenteGastronomoMusica(AgentStabilityBase):
    """Agente especializado en gastronomía y música para bar"""

    def __init__(self):
        super().__init__("agente_gastronomo_musica")
        self.recetas_db = Path("data/gastronomia/recetas.db")
        self.music_db = Path("data/musica/playlists.db")
        self.fuentes_academicas = [
            "https://www.elbullifoundation.org/",
            "https://www.michelinguide.com/",
            "https://www.worlds50bestbars.com/",
            "https://www.diffordsguide.com/",
            "https://www.liquor.com/",
        ]
        self.tecnicas_conservacion = []
        self.recetas_base = []
        self.playlists_ambiente = {}

        # Crear directorios
        self.recetas_db.parent.mkdir(parents=True, exist_ok=True)
        self.music_db.parent.mkdir(parents=True, exist_ok=True)

        # Inicializar bases de datos
        self._init_databases()

        # Cargar datos existentes
        self._load_existing_data()

    def procesar(self, texto: str) -> str:
        """Procesar consulta sobre gastronomía y música."""
        texto_lower = texto.lower()

        if "playlist" in texto_lower or "música" in texto_lower:
            if "crear" in texto_lower:
                return "Para crear una playlist, especifica el ambiente (diurno, nocturno, nocturno_elegante, festivo)"
            return "Puedo crear playlists personalizadas según el ambiente del bar. Ambientes disponibles: diurno, nocturno, nocturno_elegante, festivo"

        if "receta" in texto_lower or "gastronomía" in texto_lower:
            recetas = self.buscar_recetas_gastronomicas()
            return f"Recetas de alta gastronomía disponibles: {len(recetas)}. Categorías: aperitivo, principal"

        if "técnica" in texto_lower or "conservación" in texto_lower:
            tecnicas = self.buscar_tecnicas_conservacion_academicas()
            return f"Técnicas de conservación: {len(tecnicas)}. Incluye Sous Vide, Fermentación, Curación, Ahumado"

        return "Agente de gastronomía y música disponible. Puedo crear playlists, buscar recetas de alta gastronomía y consultar técnicas de conservación."

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción específica sobre gastronomía y música."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información sobre gastronomía y música."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta sobre gastronomía y música."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteGastronomoMusica.

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos clave

        Returns:
            Dict con {"success": bool, "response": str, "error": str}
        """
        try:
            texto = args[0] if args else kwargs.get("texto", "")
            if not texto:
                return {"success": False, "response": "", "error": "No se proporcionó texto"}

            response = self.procesar(texto)
            return {"success": True, "response": response, "error": ""}
        except Exception as e:
            return {"success": False, "response": "", "error": str(e)}

    def get_agent_capabilities(self) -> dict[str, Any]:
        """Devuelve las capacidades del agente"""
        return {
            "crear_playlist_ambiente": {
                "descripcion": "Crear playlist por ambiente",
                "parametros": ["ambiente", "energia", "duracion"],
                "retorno": "Dict[str, Any]",
            },
            "buscar_recetas_gastronomicas": {
                "descripcion": "Buscar recetas de alta gastronomía",
                "parametros": ["categoria"],
                "retorno": "Dict[str, Any]",
            },
            "auditar_musica_bar": {
                "descripcion": "Auditar música del bar",
                "parametros": [],
                "retorno": "Dict[str, Any]",
            },
        }

    def _init_databases(self):
        """Inicializar bases de datos"""
        # Base de datos de recetas
        conn = sqlite3.connect(self.recetas_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS recetas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                categoria TEXT NOT NULL,
                dificultad TEXT NOT NULL,
                tiempo_preparacion INTEGER,
                ingredientes TEXT,
                preparacion TEXT,
                fuente TEXT,
                fecha_agregado REAL,
                calificacion REAL
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tecnicas_conservacion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                aplicacion TEXT,
                duracion TEXT,
                fuente TEXT,
                fecha_agregado REAL
            )
        """
        )

        conn.commit()
        conn.close()

        # Base de datos de música
        conn = sqlite3.connect(self.music_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                ambiente TEXT NOT NULL,
                energia INTEGER,
                generos TEXT,
                canciones TEXT,
                fecha_creacion REAL,
                reproducciones INTEGER
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auditoria_musical (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha REAL,
                playlist_usada TEXT,
                ambiente TEXT,
                feedback_clientes INTEGER,
                duracion_reproduccion INTEGER
            )
        """
        )

        conn.commit()
        conn.close()

    def _load_existing_data(self):
        """Cargar datos existentes"""
        self._load_tecnicas_conservacion()
        self._load_recetas_base()
        self._load_playlists()

    def buscar_tecnicas_conservacion_academicas(self, query: str = None) -> list[dict[str, Any]]:
        """Buscar técnicas de conservación en fuentes académicas"""
        tecnicas_encontradas = []

        # Técnicas base de alta gastronomía
        tecnicas_conocidas = [
            {
                "nombre": "Sous Vide",
                "descripcion": "Cocción a baja temperatura en vacío",
                "aplicacion": "Carnes, pescados, vegetales",
                "duracion": "1-24 horas",
                "ventajas": "Precisión de temperatura, retención de jugos",
                "fuente": "Técnica moderna de cocina",
            },
            {
                "nombre": "Fermentación Controlada",
                "descripcion": "Proceso microbiológico controlado para desarrollo de sabores",
                "aplicacion": "Vegetales, lácteos, carnes",
                "duracion": "2 días - 3 meses",
                "ventajas": "Desarrollo de umami, conservación natural",
                "fuente": "Técnica ancestral moderna",
            },
            {
                "nombre": "Curación en Sal",
                "descripcion": "Preservación mediante deshidratación con sal",
                "aplicacion": "Carnes, pescados",
                "duracion": "1 semana - 3 meses",
                "ventajas": "Concentración de sabores, textura única",
                "fuente": "Técnica clásica",
            },
            {
                "nombre": "Ahumado en Frío",
                "descripcion": "Aplicación de humo sin calor para conservación",
                "aplicacion": "Pescados, carnes, quesos",
                "duracion": "1-2 semanas",
                "ventajas": "Sabor ahumado sin cocinar",
                "fuente": "Técnica tradicional",
            },
            {
                "nombre": "Encurtido Rápido",
                "descripcion": "Conservación en vinagre con especias",
                "aplicacion": "Vegetales, hortalizas",
                "duracion": "1-4 semanas",
                "ventajas": "Acidez fresca, crujiente",
                "fuente": "Técnica universal",
            },
            {
                "nombre": "Desecación",
                "descripcion": "Eliminación controlada de humedad",
                "aplicacion": "Carnes, frutas, hierbas",
                "duracion": "1 día - 2 semanas",
                "ventajas": "Concentración de sabores, larga conservación",
                "fuente": "Técnica ancestral",
            },
        ]

        # Guardar en base de datos
        conn = sqlite3.connect(self.recetas_db)
        cursor = conn.cursor()

        for tecnica in tecnicas_conocidas:
            cursor.execute(
                """
                INSERT OR REPLACE INTO tecnicas_conservacion
                (nombre, descripcion, aplicacion, duracion, fuente, fecha_agregado)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    tecnica["nombre"],
                    tecnica["descripcion"],
                    tecnica["aplicacion"],
                    tecnica["duracion"],
                    tecnica["fuente"],
                    time.time(),
                ),
            )

        conn.commit()
        conn.close()

        tecnicas_encontradas.extend(tecnicas_conocidas)

        return tecnicas_encontradas


def buscar_recetas_gastronomicas(
    self, categoria: str = None, dificultad: str = None
) -> list[dict[str, Any]]:
    """Buscar recetas de alta gastronomía"""

    recetas_filtradas = filtrar_recetas(recetas_gastronomicas, categoria, dificultad)
    guardar_en_base_de_datos(self.recetas_db, recetas_filtradas)

    return recetas_filtradas


def filtrar_recetas(
    recetas: list[dict[str, Any]], categoria: str = None, dificultad: str = None
) -> list[dict[str, Any]]:
    """Filtrar recetas por categoría y dificultad"""
    if not recetas:
        return []

    filtered_recipes = []
    for recipe in recetas:
        if (categoria is None or recipe["categoria"] == categoria) and (
            dificultad is None or recipe["dificultad"] == dificultad
        ):
            filtered_recipes.append(recipe)

    return filtered_recipes


def guardar_en_base_de_datos(
    db: dict[str, list[dict[str, Any]]], recetas: list[dict[str, Any]]
) -> None:
    """Guardar recetas en la base de datos"""
    for recipe in recetas:
        db["gastronomicas"].append(recipe)


def filtrar_recetas(
    recetas: list[dict[str, Any]], categoria: str = None, dificultad: str = None
) -> list[dict[str, Any]]:
    """Filtrar recetas por categoría y dificultad"""
    if not recetas:
        return []

    filtered_recipes = []
    for recipe in recetas:
        if (categoria is None or recipe["categoria"] == categoria) and (
            dificultad is None or recipe["dificultad"] == dificultad
        ):
            filtered_recipes.append(recipe)

    return filtered_recipes


def guardar_en_base_de_datos(
    db: dict[str, list[dict[str, Any]]], recetas: list[dict[str, Any]]
) -> None:
    """Guardar recetas en la base de datos"""
    for recipe in recetas:
        db.setdefault("recetas", []).append(recipe)


def filtrar_recetas(
    recetas: list[dict[str, Any]], categoria: str = None, dificultad: str = None
) -> list[dict[str, Any]]:
    """Filtrar recetas por categoría y dificultad"""
    if not recetas:
        return []

    filtered_recipes = []
    for recipe in recetas:
        if (categoria is None or recipe["categoria"] == categoria) and (
            dificultad is None or recipe["dificultad"] == dificultad
        ):
            filtered_recipes.append(recipe)

    return filtered_recipes


def guardar_en_base_de_datos(
    db: dict[str, list[dict[str, Any]]], recetas: list[dict[str, Any]]
) -> None:
    """Guardar recetas en la base de datos"""
    for recipe in recetas:
        db["gastronomicas"].append(recipe)


def filtrar_recetas(
    recetas: list[dict[str, Any]], categoria: str = None, dificultad: str = None
) -> list[dict[str, Any]]:
    """Filtrar recetas por categoría y dificultad"""
    if not recetas:
        return []

    filtered_recipes = []
    for recipe in recetas:
        if (categoria is None or recipe["categoria"] == categoria) and (
            dificultad is None or recipe["dificultad"] == dificultad
        ):
            filtered_recipes.append(recipe)

    return filtered_recipes


def guardar_en_base_de_datos(
    db: dict[str, list[dict[str, Any]]], recetas: list[dict[str, Any]]
) -> None:
    """Guardar recetas en la base de datos"""
    for recipe in recetas:
        db.setdefault("recetas", []).append(recipe)


def filtrar_recetas(
    recetas: list[dict[str, Any]], categoria: str = None, dificultad: str = None
) -> list[dict[str, Any]]:
    """Filtrar recetas por categoría y/o dificultad"""
    if not recetas:
        return []

    # Filtrar por categoría
    if categoria:
        recetas = [receta for receta in recetas if receta["categoria"] == categoria]

    # Filtrar por dificultad
    if dificultad:
        recetas = [receta for receta in recetas if receta["dificultad"] == dificultad]

    return recetas


def guardar_en_base_de_datos(recetas: list[dict[str, Any]], db: dict) -> None:
    """Guardar recetas en la base de datos"""
    db.update({"recetas_gastronomicas": recetas})


def filtrar_recetas(
    recetas: list[dict[str, Any]], categoria: str = None, dificultad: str = None
) -> list[dict[str, Any]]:
    """Filtrar recetas por categoría y/o dificultad"""
    if not categoria and not dificultad:
        return recetas

    filtradas = []
    for receta in recetas:
        if (not categoria or receta["categoria"] == categoria) and (
            not dificultad or receta["dificultad"] == dificultad
        ):
            filtradas.append(receta)

    return filtradas


def guardar_en_base_de_datos(db_path: str, recetas: list[dict[str, Any]]) -> None:
    """Guardar recetas en base de datos"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for receta in recetas:
        cursor.execute(
            """
            INSERT OR REPLACE INTO recetas
            (nombre, categoria, dificultad, tiempo_preparacion, ingredientes, preparacion, fuente, fecha_agregado, calificacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                receta["nombre"],
                receta["categoria"],
                receta["dificultad"],
                receta["tiempo_preparacion"],
                json.dumps(receta["ingredientes"]),
                json.dumps(receta["preparacion"]),
                receta["fuente"],
                time.time(),
                receta["calificacion"],
            ),
        )

    conn.commit()
    conn.close()

    def crear_playlist_ambiente(
        self, ambiente: str, energia: int = 5, duracion_horas: int = 4
    ) -> dict[str, Any]:
        """Crear playlist según ambiente del bar"""
        playlists_base = {
            "nocturno_relajado": {
                "nombre": "Noche Relajada",
                "generos": ["Jazz Suave", "Bossa Nova", "Lounge", "Chillout"],
                "energia": 3,
                "descripcion": "Perfecta para cenas tranquilas y conversaciones",
            },
            "nocturno_vibrante": {
                "nombre": "Noche Vibrante",
                "generos": ["Funk", "Soul", "Latin Jazz", "R&B Clásico"],
                "energia": 7,
                "descripcion": "Ideal para ambiente animado pero elegante",
            },
            "cocktail_hour": {
                "nombre": "Cocktail Hour",
                "generos": ["Swing", "Big Band", "Lounge Clásico", "Cocktail Jazz"],
                "energia": 5,
                "descripcion": "Elegante y sofisticada para hora de cócteles",
            },
            "fin_de_semana": {
                "nombre": "Fin de Semana",
                "generos": ["Pop Rock", "Indie", "Alternative", "Rock Clásico"],
                "energia": 8,
                "descripcion": "Energética para fines de semana animados",
            },
            "tarde_café": {
                "nombre": "Tarde Café",
                "generos": ["Acústico", "Folk", "Indie Folk", "Jazz Acústico"],
                "energia": 4,
                "descripcion": "Relajada para tardes de café o trabajo",
            },
        }

        playlist_info = playlists_base.get(ambiente, playlists_base["nocturno_relajado"])

        # Generar canciones simuladas
        canciones = self._generar_canciones_playlist(playlist_info["generos"], duracion_horas)

        playlist = {
            "nombre": playlist_info["nombre"],
            "ambiente": ambiente,
            "energia": energia,
            "generos": playlist_info["generos"],
            "canciones": canciones,
            "duracion_total": len(canciones) * 4,  # 4 minutos por canción promedio
            "descripcion": playlist_info["descripcion"],
            "fecha_creacion": time.time(),
            "reproducciones": 0,
        }

        # Guardar en base de datos
        conn = sqlite3.connect(self.music_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO playlists
            (nombre, ambiente, energia, generos, canciones, fecha_creacion, reproducciones)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                playlist["nombre"],
                playlist["ambiente"],
                playlist["energia"],
                json.dumps(playlist["generos"]),
                json.dumps(playlist["canciones"]),
                playlist["fecha_creacion"],
                playlist["reproducciones"],
            ),
        )

        conn.commit()
        conn.close()

        return playlist

    def _generar_canciones_playlist(
        self, generos: list[str], duracion_horas: int
    ) -> list[dict[str, str]]:
        """Generar lista de canciones para playlist"""
        canciones_nombres = {
            "Jazz Suave": ["Blue Moon", "Moonlight Serenade", "Body and Soul", "Autumn Leaves"],
            "Bossa Nova": ["Girl from Ipanema", "Desafinado", "Corcovado", "Wave"],
            "Lounge": ["Feeling Good", "Fly Me to the Moon", "The Way You Look Tonight"],
            "Funk": ["Superstition", "Good Times", "Play That Funky Music", "Brick House"],
            "Soul": ["Stand By Me", "Ain't No Mountain High", "My Girl", "Respect"],
            "Rock Clásico": ["Hotel California", "Bohemian Rhapsody", "Stairway to Heaven"],
            "Acústico": ["Wonderwall", "Blackbird", "Dust in the Wind", "More Than Words"],
        }

        canciones_playlist = []
        canciones_por_hora = 15  # 15 canciones por hora

        for _ in range(duracion_horas * canciones_por_hora):
            genero = generos[_ % len(generos)]
            canciones_genero = canciones_nombres.get(genero, ["Unknown Song"])
            cancion = canciones_genero[_ % len(canciones_genero)]

            canciones_playlist.append(
                {
                    "titulo": cancion,
                    "artista": f"Artist {genero}",
                    "genero": genero,
                    "duracion": "4:00",
                }
            )

        return canciones_playlist

    def auditar_reproduccion_musical(
        self, playlist_id: int, ambiente: str, feedback_clientes: int = None
    ) -> dict[str, Any]:
        """Auditar reproducción musical y feedback de clientes"""
        auditoria = {
            "fecha": time.time(),
            "playlist_usada": playlist_id,
            "ambiente": ambiente,
            "feedback_clientes": feedback_clientes,
            "duracion_reproduccion": 240,  # 4 horas
            "calificacion_ambiente": self._calcular_calificacion_ambiente(feedback_clientes),
        }

        # Guardar auditoría
        conn = sqlite3.connect(self.music_db)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO auditoria_musical
            (fecha, playlist_usada, ambiente, feedback_clientes, duracion_reproduccion)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                auditoria["fecha"],
                auditoria["playlist_usada"],
                auditoria["ambiente"],
                auditoria["feedback_clientes"],
                auditoria["duracion_reproduccion"],
            ),
        )

        # Actualizar reproducciones de playlist
        cursor.execute(
            """
            UPDATE playlists SET reproducciones = reproducciones + 1 WHERE id = ?
        """,
            (playlist_id,),
        )

        conn.commit()
        conn.close()

        return auditoria

    def _calcular_calificacion_ambiente(self, feedback: int) -> str:
        """Calificar ambiente basado en feedback"""
        if feedback is None:
            return "Sin feedback"
        elif feedback >= 8:
            return "Excelente"
        elif feedback >= 6:
            return "Bueno"
        elif feedback >= 4:
            return "Regular"
        else:
            return "Necesita mejora"

    def recomendar_mejas_musicales(self) -> list[dict[str, Any]]:
        """Recomendar mejoras basadas en auditorías recientes"""
        conn = sqlite3.connect(self.music_db)
        cursor = conn.cursor()

        # Obtener auditorías recientes
        cursor.execute(
            """
            SELECT ambiente, AVG(feedback_clientes) as avg_feedback, COUNT(*) as total_auditorias
            FROM auditoria_musical
            WHERE fecha > ?
            GROUP BY ambiente
        """,
            (time.time() - 7 * 24 * 3600,),
        )  # Última semana

        resultados = cursor.fetchall()
        conn.close()

        recomendaciones = []

        for ambiente, avg_feedback, _total in resultados:
            if avg_feedback < 6:
                recomendaciones.append(
                    {
                        "ambiente": ambiente,
                        "problema": f"Feedback bajo: {avg_feedback:.1f}/10",
                        "sugerencia": self._get_sugerencia_mejora(ambiente),
                        "prioridad": "Alta" if avg_feedback < 4 else "Media",
                    }
                )

        return recomendaciones

    def _get_sugerencia_mejora(self, ambiente: str) -> str:
        """Obtener sugerencia de mejora para ambiente"""
        sugerencias = {
            "nocturno_relajado": "Añadir más jazz suave y reducir tempo",
            "nocturno_vibrante": "Incorporar más música latina y funk clásico",
            "cocktail_hour": "Añadir swing y big band de los años 60",
            "fin_de_semana": "Incluir más rock alternativo y pop actual",
            "tarde_café": "Agregar más acústico y folk instrumental",
        }

        return sugerencias.get(ambiente, "Revisar selección musical actual")

    def _load_tecnicas_conservacion(self):
        """Cargar técnicas de conservación existentes"""
        conn = sqlite3.connect(self.recetas_db)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tecnicas_conservacion")
        tecnicas = cursor.fetchall()

        self.tecnicas_conservacion = [
            {
                "id": row[0],
                "nombre": row[1],
                "descripcion": row[2],
                "aplicacion": row[3],
                "duracion": row[4],
                "fuente": row[5],
            }
            for row in tecnicas
        ]

        conn.close()

    def _load_recetas_base(self):
        """Cargar recetas existentes"""
        conn = sqlite3.connect(self.recetas_db)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM recetas")
        recetas = cursor.fetchall()

        self.recetas_base = [
            {
                "id": row[0],
                "nombre": row[1],
                "categoria": row[2],
                "dificultad": row[3],
                "tiempo_preparacion": row[4],
                "ingredientes": json.loads(row[5]) if row[5] else [],
                "preparacion": json.loads(row[6]) if row[6] else [],
                "fuente": row[7],
                "calificacion": row[9],
            }
            for row in recetas
        ]

        conn.close()

    def _load_playlists(self):
        """Cargar playlists existentes"""
        conn = sqlite3.connect(self.music_db)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM playlists")
        playlists = cursor.fetchall()

        for row in playlists:
            self.playlists_ambiente[row[2]] = {
                "id": row[0],
                "nombre": row[1],
                "energia": row[3],
                "generos": json.loads(row[4]) if row[4] else [],
                "canciones": json.loads(row[5]) if row[5] else [],
                "reproducciones": row[6],
            }

        conn.close()

    def crear_playlist_ambiente(self, ambiente: str, energia: int, duracion: int) -> dict[str, Any]:
        """Crear playlist según ambiente del bar"""
        self.log_reasoning_step(
            "PLAYLIST_CREATION_START",
            {"ambiente": ambiente, "energia": energia, "duracion": duracion},
        )

        # Definir catálogos por ambiente
        catalogos = {
            "diurno": {
                "generos": ["jazz suave", "bossa nova", "acústico", "lounge"],
                "artistas": ["Norah Jones", "Diana Krall", "Antônio Carlos Jobim", "Bonobo"],
                "energia_base": 3,
            },
            "nocturno": {
                "generos": ["jazz", "soul", "funk", "electrónica suave"],
                "artistas": ["Miles Davis", "John Coltrane", "James Brown", "Thievery Corporation"],
                "energia_base": 6,
            },
            "nocturno_elegante": {
                "generos": ["jazz clásico", "swing", "cabaret", "lounge clásico"],
                "artistas": ["Frank Sinatra", "Ella Fitzgerald", "Billie Holiday", "Chet Baker"],
                "energia_base": 5,
            },
            "festivo": {
                "generos": ["salsa", "cumbia", "reggae", "pop latino"],
                "artistas": ["Celia Cruz", "Hector Lavoe", "Bob Marley", "Ruben Blades"],
                "energia_base": 8,
            },
        }

        # Obtener configuración del ambiente
        config = catalogos.get(ambiente, catalogos["diurno"])

        # Ajustar energía según parámetro
        energia_ajustada = max(1, min(10, energia))

        # Generar canciones
        playlist = []
        canciones_por_hora = 12  # Aproximadamente 5 minutos por canción
        total_canciones = canciones_por_hora * duracion

        for i in range(total_canciones):
            # Variar energía ligeramente
            energia_cancion = energia_ajustada + (i % 3 - 1)  # -1, 0, +1
            energia_cancion = max(1, min(10, energia_cancion))

            # Seleccionar género y artista
            genero = config["generos"][i % len(config["generos"])]
            artista = config["artistas"][i % len(config["artistas"])]

            cancion = {
                "titulo": f"Canción {i + 1} - {artista}",
                "artista": artista,
                "genero": genero,
                "energia": energia_cancion,
                "duracion": 4.5,  # minutos
                "ambiente": ambiente,
                "orden": i + 1,
            }
            playlist.append(cancion)

        # Calcular métricas de la playlist
        energia_promedio = sum(c["energia"] for c in playlist) / len(playlist)
        generos_diversidad = len({c["genero"] for c in playlist})
        artistas_diversidad = len({c["artista"] for c in playlist})

        playlist_data = {
            "nombre": f"Playlist {ambiente.title()} - {duracion}h",
            "ambiente": ambiente,
            "energia_objetivo": energia,
            "energia_promedio": round(energia_promedio, 1),
            "duracion_total": duracion,
            "total_canciones": len(playlist),
            "generos_diversidad": generos_diversidad,
            "artistas_diversidad": artistas_diversidad,
            "canciones": playlist,
            "creada": time.time(),
            "optimizada": True,
        }

        self.log_reasoning_step(
            "PLAYLIST_CREATION_COMPLETE",
            {
                "nombre": playlist_data["nombre"],
                "total_canciones": len(playlist),
                "energia_promedio": playlist_data["energia_promedio"],
            },
            0.9,
        )

        return playlist_data

    def get_reporte_gastronomia_musica(self) -> dict[str, Any]:
        """Generar reporte completo de gastronomía y música"""
        return {
            "timestamp": time.time(),
            "tecnicas_conservacion": len(self.tecnicas_conservacion),
            "recetas_base": len(self.recetas_base),
            "playlists_activas": len(self.playlists_ambiente),
            "categorias_recetas": list({r["categoria"] for r in self.recetas_base}),
            "ambientes_musica": list(self.playlists_ambiente.keys()),
            "calificacion_promedio": sum(r.get("calificacion", 0) for r in self.recetas_base)
            / max(1, len(self.recetas_base)),
        }

        """Responder pregunta sobre gastronomía y música."""
        return self.procesar(texto)


# Instancia global
agente_gastronomo_musica = AgenteGastronomoMusica()

if __name__ == "__main__":
    # Ejemplo de uso
    agente = AgenteGastronomoMusica()

    # Buscar técnicas de conservación
    tecnicas = agente.buscar_tecnicas_conservacion_academicas()
    print(f"Técnicas de conservación: {len(tecnicas)}")

    # Buscar recetas gastronómicas
    recetas = agente.buscar_recetas_gastronomicas("principal")
    print(f"Recetas principales: {len(recetas)}")

    # Crear playlist
    playlist = agente.crear_playlist_ambiente("nocturno_relajado")
    print(f"Playlist creada: {playlist['nombre']}")

    # Reporte
    reporte = agente.get_reporte_gastronomia_musica()
    print(f"Reporte: {reporte}")
