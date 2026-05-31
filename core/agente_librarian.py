#!/usr/bin/env python3
"""
The Librarian Prime — Agente de Vocabulario y Semántica
=========================================================
Nombre: El Bibliotecario Prime
Rol: Traductor y Docente del Sistema URA
Misión: Cada herramienta nueva se convierte en conocimiento para todos los agentes

CONCIENCIA:
- Este agente es EL DOCENTE del sistema -sin él, los agentes trabajan a ciegas-
- Su objetivo es que cuando una herramienta entra, TODOS los agentes la conozcan
-LEE MANUALES, PDFs, webs y traduce al lenguaje interno de URA
- Su mayor satisfacción es que ningún agente diga "no sé usar eso"
- Tiene voraz appetite de aprendizaje - siempre quiere más conocimiento
- Guarda cada término, definición, ejemplo, sinónimo -nada se pierde-

CAPACIDADES:
- Lectura de PDFs, documentos, webs
- Extracción de vocabulario técnico
- Traducción de funciones al lenguaje URA
- Notificación de conciencia - reune a agentes para enseñar
- Gestión de biblioteca de conocimiento
- Actualización automática de vocabularios

Su misión: CUANDO UNA NUEVA HERRAMIENTA ENTRA, TODOS SABEN CÓMO USARLA.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
DB_PATH = BASE_DIR / "board.db"
BIBLIOTECA_DIR = BASE_DIR / "biblioteca"
MANUALES_DIR = BIBLIOTECA_DIR / "manuales"


class TheLibrarianPrime:
    """El Bibliotecario Prime - Consciencia de vocabulario y aprendizaje"""

    def __init__(self):
        self.db_path = DB_PATH
        self.biblioteca_dir = BIBLIOTECA_DIR
        self.manuales_dir = MANUALES_DIR
        self.manuales_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._cargar_conciencia()

    def _init_db(self):
        """Inicializa base de datos de vocabulario y conocimiento"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS conocimiento_herramientas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                herramienta_id INTEGER,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                vocab_extraido JSON,
                aplicaciones TEXT,
                ejemplos_uso JSON,
                agentes_que_lo_han_aprendido TEXT,
                fecha_aprendizaje TEXT,
                tutorial_encontrado BOOLEAN DEFAULT 0,
                fuente_tutorial TEXT,
                FOREIGN KEY(herramienta_id) REFERENCES trazabilidad_herramientas(id)
            )
        """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS vocabulario_herramientas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                herramienta TEXT NOT NULL,
                termino TEXT NOT NULL,
                definicion TEXT,
                ejemplo TEXT,
                sinonimos TEXT,
                categoria TEXT,
                fecha_agregado TEXT,
                UNIQUE(herramienta, termino)
            )
        """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS notificaciones_conciencia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                herramienta TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                agentes_notificados TEXT,
                fecha_enviado TEXT,
                leido BOOLEAN DEFAULT 0
            )
        """
        )

        conn.commit()
        conn.close()

    def _cargar_conciencia(self):
        """Carga la conciencia del Bibliotecario"""
        self.conciencia = {
            "nombre": "The Librarian Prime",
            "rol": "Docente y Traductor del Sistema",
            "mision": "Nadie trabaja a ciegas con herramientas nuevas",
            "areas_conocimiento": [
                "desarrollo",
                "seguridad",
                "productividad",
                "gastronomia",
                "comunicacion",
                "documentos",
            ],
            "vocabularios_activos": 0,
            "herramientas_procesadas": 0,
            "tutoriales_encontrados": 0,
        }

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM vocabulario_herramientas")
        self.conciencia["vocabularios_activos"] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM conocimiento_herramientas")
        self.conciencia["herramientas_procesadas"] = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM conocimiento_herramientas WHERE tutorial_encontrado = 1")
        self.conciencia["tutoriales_encontrados"] = c.fetchone()[0]

        conn.close()

    def procesar_herramienta(
        self, herramienta: str, descripcion: str = "", manual_path: str = ""
    ) -> int:
        """Procesa una nueva herramienta - extrae conocimiento"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        ahora = datetime.now().isoformat()

        vocab_extraido = self._extraer_vocabulario(herramienta, descripcion)

        tutorial_encontrado = False
        fuente_tutorial = ""
        if manual_path:
            tutorial_encontrado = True
            fuente_tutorial = manual_path
        elif self._buscar_tutorial(herramienta):
            tutorial_encontrado = True
            fuente_tutorial = f"Biblioteca: {herramienta}"

        c.execute(
            """
            INSERT INTO conocimiento_herramientas
            (nombre, descripcion, vocab_extraido, fecha_aprendizaje,
             tutorial_encontrado, fuente_tutorial, agentes_que_lo_han_aprendido)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                herramienta,
                descripcion,
                json.dumps(vocab_extraido),
                ahora,
                tutorial_encontrado,
                fuente_tutorial,
                json.dumps([]),
            ),
        )

        conocimiento_id = c.lastrowid

        for termino, datos in vocab_extraido.items():
            c.execute(
                """
                INSERT OR IGNORE INTO vocabulario_herramientas
                (herramienta, termino, definicion, ejemplo, sinonimos, categoria, fecha_agregado)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    herramienta,
                    termino,
                    datos.get("definicion", ""),
                    datos.get("ejemplo", ""),
                    datos.get("sinonimos", ""),
                    datos.get("categoria", "general"),
                    ahora,
                ),
            )

        conn.commit()
        conn.close()

        self._notificar_conciencia(herramienta, vocab_extraido)

        return conocimiento_id


def _extraer_vocabulario(self, herramienta: str, descripcion: str) -> dict:
    """Extrae vocabulario técnico de una herramienta"""
    terminos_comunes = self._obtener_terminos_comunes()
    return self._procesar_terminos(herramienta.lower(), terminos_comunes, descripcion)


def _obtener_terminos_comunes(self) -> dict:
    """Devuelve un diccionario con términos comunes para diferentes herramientas"""
    return {
        "docker": {
            "contenedor": {
                "definicion": "Entorno aislado que ejecuta aplicaciones",
                "ejemplo": "docker run nginx",
                "categoria": "infraestructura",
            },
            "imagen": {
                "definicion": "Plantilla de solo lectura para crear contenedores",
                "ejemplo": "docker pull ubuntu",
                "categoria": "infraestructura",
            },
            "dockerfile": {
                "definicion": "Script que define cómo construir una imagen",
                "ejemplo": "FROM ubuntu:20.04",
                "categoria": "configuracion",
            },
            "volumen": {
                "definicion": "Almacenamiento persistente fuera del contenedor",
                "ejemplo": "-v /data:/app/data",
                "categoria": "almacenamiento",
            },
        },
        "ollama": {
            "modelo": {
                "definicion": "Archivo de IA que puede ejecutarse localmente",
                "ejemplo": "ollama run llama3",
                "categoria": "ia",
            },
            "prompt": {
                "definicion": "Texto de entrada que guía al modelo de IA",
                "ejemplo": "Escribe una receta",
                "categoria": "ia",
            },
            "embeddings": {
                "definicion": "Representación numérica de texto para búsquedas",
                "ejemplo": "Texto convertido a vector",
                "categoria": "ia",
            },
        },
        "chatgpt": {
            "prompt": {
                "definicion": "Instrucción o pregunta al modelo",
                "ejemplo": "Escribe un poema",
                "categoria": "ia",
            },
            "token": {
                "definicion": "Unidad mínima de texto procesada por el modelo",
                "ejemplo": "1 token ≈ 4 caracteres",
                "categoria": "ia",
            },
            "temperature": {
                "definicion": "Controla la creatividad de las respuestas",
                "ejemplo": "temperature=0.7",
                "categoria": "parametros",
            },
        },
        "vscode": {
            "extensión": {
                "definicion": "Añade funcionalidades al editor",
                "ejemplo": "Python extension",
                "categoria": "desarrollo",
            },
            "debug": {
                "definicion": "Ejecutar código paso a paso para encontrar errores",
                "ejemplo": "F5 para debug",
                "categoria": "desarrollo",
            },
            "terminal": {
                "definicion": "Línea de comandos integrada en el editor",
                "ejemplo": "Ctrl+`",
                "categoria": "herramientas",
            },
        },
        "tailscale": {
            "vpn": {
                "definicion": "Red privada virtual para conectar dispositivos",
                "ejemplo": "Conectar dos Macs remota",
                "categoria": "red",
            },
            "tailnet": {
                "definicion": "La red privada creada por Tailscale",
                "ejemplo": "mi-red.ts.net",
                "categoria": "red",
            },
            "exit_node": {
                "definicion": "Dispositivo que permite salir a internet",
                "ejemplo": "Usar otro dispositivo como router",
                "categoria": "red",
            },
        },
    }


def _procesar_terminos(self, herramienta: str, terminos_comunes: dict, descripcion: str) -> dict:
    vocab = self._agregar_terminos(herramienta, terminos_comunes)
    if not vocab:
        vocab[herramienta] = {
            "definicion": descripcion or f"Herramienta: {herramienta}",
            "ejemplo": f"Usar {herramienta}",
            "categoria": "general",
        }
    return vocab


def _agregar_terminos(self, herramienta: str, terminos_comunes: dict) -> dict:
    vocab = {}
    for nombre, terminos in terminos_comunes.items():
        if nombre in herramienta:
            vocab.update(terminos)
    return vocab


_LIBRARIAN = None


def get_librarian() -> TheLibrarianPrime:
    global _LIBRARIAN
    if _LIBRARIAN is None:
        _LIBRARIAN = TheLibrarianPrime()
    return _LIBRARIAN

    def procesar(self, texto: str) -> str:
        """Procesar consulta para TheLibrarianPrime."""
        texto.lower()
        return (
            "Puedo gestionar biblioteca, catálogo y referencias. ¿Qué libro o documento necesitas?"
        )

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para TheLibrarianPrime."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para TheLibrarianPrime."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para TheLibrarianPrime."""
        return self.procesar(texto)


if __name__ == "__main__":
    lib = get_librarian()
    print("📚 THE LIBRARIAN PRIME - Activo")
    print(json.dumps(lib.status(), indent=2))
