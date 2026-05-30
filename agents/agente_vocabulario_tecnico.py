"""
AGENTE VOCABULARIO TÉCNICO - Términos de informática y tecnología
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agente_logger import AgenteLogger

logger = AgenteLogger("agente_vocabulario_tecnico")

import sqlite3
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "board.db"

TERMINOS_TECNICOS = [
    (
        "API",
        "Interfaz de Programación de Aplicaciones - conjunto de protocolos para comunicar software",
        "Llamar a la API de Ollama",
        "interfaz, endpoint",
    ),
    (
        "Docker",
        "Plataforma de contenedores para empaquetar aplicaciones",
        "Crear un contenedor Docker",
        "contenedor, imagen",
    ),
    (
        "SQLite",
        "Base de datos ligera embebida en archivos",
        "Usar SQLite para board.db",
        "base de datos, db",
    ),
    ("Flask", "Framework web ligero en Python", "Crear API con Flask", "framework, backend"),
    ("Ollama", "Motor local de modelos LLM", "Ejecutar modelo con Ollama", "LLM, IA local"),
    (
        "orchestrator",
        "Coordinador central que gestiona agentes",
        "El orchestrator recibe tareas",
        "coordinador, dispatcher",
    ),
    (
        "agent",
        "Programa autónomo especializado en una tarea",
        "El agente de contabilidad",
        "agente, bot",
    ),
    ("cron", "Programador de tareas en Unix/Linux", "Tarea cron cada hora", "scheduler, scheduled"),
    (
        "LaunchAgent",
        "Servicio de inicio automático en macOS",
        "Crear LaunchAgent para URA",
        "service, daemon",
    ),
    ("path", "Ruta del sistema de archivos", "Añadir al PATH", "ruta, directorio"),
    (
        "variable_entorno",
        "Variable del sistema que guarda configuración",
        "Guardar API key en variable de entorno",
        "env, ENV",
    ),
    ("pip", "Gestor de paquetes Python", "Instalar con pip install", "paquete, install"),
    ("git", "Sistema de control de versiones", "Hacer commit con git", "version control, github"),
    ("bash", "Intérprete de comandos shell Unix", "Ejecutar script bash", "shell, terminal"),
    (
        "script",
        "Archivo con órdenes ejecutables",
        "Crear script de backup",
        "programa, automatización",
    ),
    (
        "debug",
        "Proceso de encontrar y corregir errores",
        "Modo debug activado",
        "depurar, troubleshooting",
    ),
    ("log", "Registro de eventos del sistema", "Revisar logs de error", "registro, historial"),
    ("backup", "Copia de seguridad de datos", "Hacer backup diario", "copia, restauración"),
    ("token", "Unidad de texto procesada por modelos LLM", "Límite de 4096 tokens", "chunk, texto"),
    (
        "prompt",
        "Instrucción dada a un modelo de IA",
        "Escribir un buen prompt",
        "instrucción, comando",
    ),
]


def init_vocabulario_tecnico():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for termino, definicion, ejemplo, sinonimos in TERMINOS_TECNICOS:
        c.execute(
            """
            INSERT OR IGNORE INTO biblioteca_vocabulario (categoria, termino, definicion, ejemplo, sinonimos, created_at)
            VALUES ('tecnico', ?, ?, ?, ?, ?)
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
        WHERE categoria = 'tecnico' AND termino LIKE ?
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


def listar_todos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT termino, definicion FROM biblioteca_vocabulario WHERE categoria = 'tecnico'")

    resultados = c.fetchall()
    conn.close()

    return [{"termino": r[0], "definicion": r[1]} for r in resultados]


class AgenteVocabularioTecnico:
    """Wrapper para AgenteVocabularioTecnico."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVocabularioTecnico."""
        return "Puedo definir términos técnicos e informáticos. ¿Qué término técnico necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVocabularioTecnico."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVocabularioTecnico."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVocabularioTecnico."""
        return self.procesar(texto)


if __name__ == "__main__":
    init_vocabulario_tecnico()
    print("=== Vocabulario Técnico ===")
    terminos = listar_todos()
    print(f"Total términos: {len(terminos)}")
