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
        vocab = {}

        terminos_comunes = {
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

        herramienta_lower = herramienta.lower()
        for nombre, terminos in terminos_comunes.items():
            if nombre in herramienta_lower:
                vocab.update(terminos)

        if not vocab:
            vocab[herramienta.lower()] = {
                "definicion": descripcion or f"Herramienta: {herramienta}",
                "ejemplo": f"Usar {herramienta}",
                "categoria": "general",
            }

        return vocab

    def _buscar_tutorial(self, herramienta: str) -> str | None:
        """Busca tutorial existente en biblioteca"""
        patrones = [
            self.manuales_dir / f"{herramienta.lower()}.md",
            self.manuales_dir / f"{herramienta.lower()}_manual.md",
            BIBLIOTECA_DIR / f"{herramienta.lower()}.md",
            BIBLIOTECA_DIR / "manuales" / f"{herramienta.lower()}.md",
        ]

        for path in patrones:
            if path.exists():
                return str(path)

        return None

    def _notificar_conciencia(self, herramienta: str, vocab: dict):
        """Notifica a todos los agentes que hay nueva herramienta"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        agentes_a_notificar = [
            "director_tecnico",
            "director_creativo",
            "director_seguridad",
            "director_gastronomico",
            "director_memoria",
        ]

        terminos_clave = list(vocab.keys())[:5]
        mensaje = f"📚 NUEVA HERRAMIENTA: {herramienta}\n"
        mensaje += f"📖 Vocabulario aprendido: {', '.join(terminos_clave)}\n"
        mensaje += "💡 Todos los agentes ya pueden usarla"

        c.execute(
            """
            INSERT INTO notificaciones_conciencia
            (herramienta, mensaje, agentes_notificados, fecha_enviado)
            VALUES (?, ?, ?, ?)
        """,
            (herramienta, mensaje, json.dumps(agentes_a_notificar), datetime.now().isoformat()),
        )

        conn.commit()
        conn.close()

        print(f"[BIBLIOTECARIO] 💡 Notificación enviada: {herramienta}")

    def descargar_manual(self, herramienta: str, url: str) -> bool:
        """Descarga manual/tutorial de una herramienta"""
        import requests

        manuales_paths = [
            self.manuales_dir / f"{herramienta.lower()}.md",
            self.manuales_dir / f"{herramienta.lower()}_manual.md",
        ]

        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                for path in manuales_paths:
                    if not path.exists():
                        path.write_text(response.text)
                        self._actualizar_tutorial_encontrado(herramienta, str(path))
                        return True
        except Exception as e:
            print(f"Error descargando manual: {e}")

        return False

    def _actualizar_tutorial_encontrado(self, herramienta: str, fuente: str):
        """Marca que se encontró tutorial"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            UPDATE conocimiento_herramientas
            SET tutorial_encontrado = 1, fuente_tutorial = ?
            WHERE nombre = ?
        """,
            (fuente, herramienta),
        )

        conn.commit()
        conn.close()

    def obtener_vocabulario_herramienta(self, herramienta: str) -> list[dict]:
        """Obtiene todo el vocabulario de una herramienta"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT termino, definicion, ejemplo, sinonimos, categoria
            FROM vocabulario_herramientas
            WHERE herramienta = ? ORDER BY termino
        """,
            (herramienta,),
        )

        resultados = [
            {
                "termino": r[0],
                "definicion": r[1],
                "ejemplo": r[2],
                "sinonimos": r[3],
                "categoria": r[4],
            }
            for r in c.fetchall()
        ]

        conn.close()
        return resultados

    def buscar_en_vocabulario(self, query: str) -> list[dict]:
        """Busca en todo el vocabulario"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT herramienta, termino, definicion, ejemplo, categoria
            FROM vocabulario_herramientas
            WHERE termino LIKE ? OR definicion LIKE ?
            ORDER BY herramienta, termino
        """,
            (f"%{query}%", f"%{query}%"),
        )

        resultados = [
            {
                "herramienta": r[0],
                "termino": r[1],
                "definicion": r[2],
                "ejemplo": r[3],
                "categoria": r[4],
            }
            for r in c.fetchall()
        ]

        conn.close()
        return resultados

    def obtener_informe(self, herramienta: str | None = None) -> dict:
        """Obtiene informe de conocimiento"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        if herramienta:
            c.execute(
                """
                SELECT nombre, descripcion, vocab_extraido, tutorial_encontrado,
                       fuente_tutorial, agentes_que_lo_han_aprendido
                FROM conocimiento_herramientas WHERE nombre = ?
            """,
                (herramienta,),
            )
            row = c.fetchone()
            conn.close()

            if not row:
                return {"error": "Herramienta no encontrada"}

            return {
                "herramienta": row[0],
                "descripcion": row[1],
                "vocabulario": json.loads(row[2]) if row[2] else {},
                "tiene_tutorial": row[3],
                "fuente_tutorial": row[4],
                "agentes_que_lo_aprendieron": json.loads(row[5]) if row[5] else [],
            }

        c.execute(
            "SELECT COUNT(*), tutorial_encontrado FROM conocimiento_herramientas GROUP BY tutorial_encontrado"
        )
        stats = dict(c.fetchall())

        c.execute("SELECT COUNT(*) FROM vocabulario_herramientas")
        total_vocab = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM notificaciones_conciencia WHERE leido = 0")
        notificaciones_pendientes = c.fetchone()[0]

        conn.close()

        return {
            "total_herramientas": stats.get(1, 0) + stats.get(0, 0),
            "con_tutorial": stats.get(1, 0),
            "sin_tutorial": stats.get(0, 0),
            "total_vocabulario": total_vocab,
            "notificaciones_pendientes": notificaciones_pendientes,
            "conciencia": self.conciencia,
        }

    def status(self) -> dict:
        """Estado actual del Bibliotecario"""
        informe = self.obtener_informe()
        return {
            "nombre": "The Librarian Prime",
            "rol": "Docente del Sistema",
            "herramientas_procesadas": informe.get("total_herramientas", 0),
            "vocabularios_activos": informe.get("total_vocabulario", 0),
            "tutoriales_encontrados": informe.get("con_tutorial", 0),
            "mision": "Nadie trabaja a ciegas - todos saben usar las herramientas",
        }


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
