"""
AGENTE ARQUITECTURA - Diseña sistemas y estructura
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agente_logger import AgenteLogger

logger = AgenteLogger("agente_arquitectura")

import sqlite3
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "board.db"


def analizar_requerimientos(descripcion):
    """Analiza requerimientos y sugiere arquitectura"""
    palabras = descripcion.lower().split()

    indicadores = {
        "web": ["web", "api", "http", "servidor", "frontend", "backend"],
        "datos": ["base de datos", "bd", "sql", "datos", "almacenar"],
        "automatizacion": ["automatizar", "tarea", "repetitivo", "cron", "schedule"],
        "ia": ["ia", "ai", "ollama", "chat", "mensaje"],
        "archivo": ["archivo", "carpeta", "organizar", "fichero"],
    }

    detectado = {}
    for categoria, keywords in indicadores.items():
        if any(k in palabras for k in keywords):
            detectado[categoria] = True

    if not detectado:
        detectado["general"] = True

    return {
        "requerimientos": listdetectado.keys(),
        "complejidad": (
            "alta"
            if len(listdetectado.keys()) > 3
            else "media"
            if len(listdetectado.keys()) > 1
            else "baja"
        ),
        "tecnologias_sugeridas": sugerir_tecnologias(listdetectado.keys()),
    }


def sugerir_tecnologias(categorias):
    """Sugiere tecnologías según categorías"""
    sugerencias = []

    if "web" in categorias:
        sugerencias.append("Flask")
        sugerencias.append("FastAPI")
    if "datos" in categorias:
        sugerencias.append("SQLite")
        sugerencias.append("PostgreSQL")
    if "automatizacion" in categorias:
        sugerencias.append("Python scripts")
        sugerencias.append("LaunchAgent")
    if "ia" in categorias:
        sugerencias.append("Ollama")
        sugerencias.append("LangChain")
    if "archivo" in categorias:
        sugerencias.append("Pathlib")

    return sugerencias


def listdetectado():
    return list(detectado.keys()) if "detectado" in dir() else []


def guardar_proyecto(nombre, descripcion, arquitectura):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS proyectos_arquitectura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            arquitectura TEXT,
            estado TEXT DEFAULT 'diseno',
            created_at TEXT NOT NULL
        )
    """
    )

    c.execute(
        """
        INSERT INTO proyectos_arquitectura (nombre, descripcion, arquitectura, created_at)
        VALUES (?, ?, ?, ?)
    """,
        (nombre, descripcion, arquitectura, datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()


def listar_proyectos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT nombre, descripcion, estado, created_at
        FROM proyectos_arquitectura
        ORDER BY created_at DESC
    """
    )

    return c.fetchall()


if __name__ == "__main__":
    print("=== AGENTE ARQUITECTURA ===")
    print("Analizando requerimientos...")

    req = analizar_requerimientos(
        "Quiero un sistema que escanee archivos y los organice automáticamente"
    )
    print(f"Detectado: {req}")
