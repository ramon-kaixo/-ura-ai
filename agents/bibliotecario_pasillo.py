#!/usr/bin/env python3
"""
Bibliotecario de Pasillo - Uno por pasillo, con su índice local y asignación de códigos
"""

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
BASE_PATH = BASE_DIR / "sandbox"

INDICE_PASILLOS = {
    "Aduana": {
        "descripcion": "Puerta de entrada - todo entra aquí primero",
        "nivel_seguridad": "BAJO",
        "tipos_permitidos": ["*"],
    },
    "Pruebas": {
        "descripcion": "Sandbox de pruebas - apps sin verificar",
        "nivel_seguridad": "MEDIO",
        "tipos_permitidos": ["app", "dmg", "zip", "py", "sh"],
    },
    "Boveda": {
        "descripcion": "Almacenamiento cifrado - datos sensibles",
        "nivel_seguridad": "ALTO",
        "tipos_permitidos": ["pdf", "doc", "txt", "json", "key"],
    },
    "Laboratorio": {
        "descripcion": "Entorno de desarrollo con Ollama",
        "nivel_seguridad": "MEDIO",
        "tipos_permitidos": ["*"],
    },
}


class BibliotecarioPasillo:
    """Bibliotecario para un pasillo específico"""

    def __init__(self, nombre_pasillo: str):
        self.nombre = nombre_pasillo
        self.ruta = BASE_PATH / nombre_pasillo
        self.indice_path = self.ruta / ".indice.json"
        self.db_path = self.ruta / "indice.db"

        self.ruta.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.indice = self._cargar_indice()

    def _init_db(self):
        """Inicializa la base de datos del índice"""

        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS indice_archivos (
                codigo TEXT PRIMARY KEY,
                nombre TEXT,
                tipo TEXT,
                hash TEXT,
                fecha_ingreso TEXT,
                pasillo_origen TEXT,
                estado TEXT DEFAULT 'activo',
                metadata TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS log_movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                accion TEXT,
                desde TEXT,
                hacia TEXT,
                codigo TEXT,
                timestamp TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _cargar_indice(self):
        """Carga el índice desde archivo JSON"""

        if self.indice_path.exists():
            return json.loads(self.indice_path.read_text())

        return {
            "pasillo": self.nombre,
            "config": INDICE_PASILLOS.get(self.nombre, {}),
            "ultimo_codigo": 0,
            "total_archivos": 0,
        }

    def _guardar_indice(self):
        """Guarda el índice a archivo JSON"""

        self.indice_path.write_text(json.dumps(self.indice, indent=2))

    def _generar_codigo(self) -> str:
        """Genera un código único para el archivo"""

        self.indice["ultimo_codigo"] += 1
        codigo = f"{self.nombre[:3].upper()}-{self.indice['ultimo_codigo']:05d}"

        self._guardar_indice()

        return codigo

    def _calcular_hash(self, ruta: Path) -> str:
        """Calcula el hash de un archivo"""

        if ruta.is_file():
            return hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]
        return ""

    def registrar(self, ruta_archivo: Path, pasillo_origen: str = None) -> dict:
        """Registra un archivo en el pasillo"""

        if not ruta_archivo.exists():
            return {"success": False, "error": "Archivo no existe"}

        codigo = self._generar_codigo()
        hash_archivo = self._calcular_hash(ruta_archivo)
        nombre = ruta_archivo.name
        tipo = ruta_archivo.suffix.lower().replace(".", "")

        ahora = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO indice_archivos
            (codigo, nombre, tipo, hash, fecha_ingreso, pasillo_origen, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (codigo, nombre, tipo, hash_archivo, ahora, pasillo_origen, "{}"),
        )

        conn.commit()
        conn.close()

        self.indice["total_archivos"] += 1
        self._guardar_indice()

        return {
            "success": True,
            "codigo": codigo,
            "nombre": nombre,
            "hash": hash_archivo,
            "pasillo": self.nombre,
        }

    def mover_a(self, codigo: str, pasillo_destino: str) -> dict:
        """Mueve un archivo a otro pasillo"""

        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute("SELECT nombre, hash FROM indice_archivos WHERE codigo = ?", (codigo,))
        row = c.fetchone()

        if not row:
            conn.close()
            return {"success": False, "error": "Código no encontrado"}

        nombre, hash_original = row

        archivo_actual = self.ruta / nombre
        destino = BASE_PATH / pasillo_destino / nombre

        if archivo_actual.exists():
            shutil.move(str(archivo_actual), str(destino))

        c.execute(
            """
            INSERT INTO log_movimientos (accion, desde, hacia, codigo, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("MOVER", self.nombre, pasillo_destino, codigo, datetime.now().isoformat()),
        )

        c.execute("UPDATE indice_archivos SET estado = 'movido' WHERE codigo = ?", (codigo,))

        conn.commit()
        conn.close()

        return {"success": True, "codigo": codigo, "desde": self.nombre, "hacia": pasillo_destino}

    def buscar(self, termino: str = None, tipo: str = None) -> list:
        """Busca archivos en el índice"""

        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        query = "SELECT codigo, nombre, tipo, hash, fecha_ingreso FROM indice_archivos WHERE estado = 'activo'"
        params = []

        if termino:
            query += " AND nombre LIKE ?"
            params.append(f"%{termino}%")

        if tipo:
            query += " AND tipo = ?"
            params.append(tipo)

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        return [
            {"codigo": row[0], "nombre": row[1], "tipo": row[2], "hash": row[3], "fecha": row[4]}
            for row in rows
        ]

    def get_informe(self) -> dict:
        """Genera informe del pasillo"""

        conn = sqlite3.connect(self.db_path, timeout=30)
        c = conn.cursor()

        c.execute(
            "SELECT COUNT(*), tipo FROM indice_archivos WHERE estado = 'activo' GROUP BY tipo"
        )
        por_tipo = {row[1]: row[0] for row in c.fetchall()}

        c.execute("SELECT COUNT(*) FROM indice_archivos WHERE estado = 'movido'")
        movidos = c.fetchone()[0]

        conn.close()

        return {
            "pasillo": self.nombre,
            "config": INDICE_PASILLOS.get(self.nombre, {}),
            "total_activos": self.indice.get("total_archivos", 0),
            "movidos": movidos,
            "por_tipo": por_tipo,
        }


class BibliotecariosPasillo:
    """Gestor de todos los bibliotecarios"""

    def __init__(self):
        self.bibliotecarios = {}

        for pasillo in INDICE_PASILLOS:
            self.bibliotecarios[pasillo] = BibliotecarioPasillo(pasillo)

    def get_bibliotecario(self, nombre: str) -> BibliotecarioPasillo:
        """Obtiene un bibliotecario específico"""
        return self.bibliotecarios.get(nombre)

    def mover(self, codigo: str, desde: str, hacia: str) -> dict:
        """Mueve un archivo entre pasillos"""

        bib_origen = self.bibliotecarios.get(desde)
        if not bib_origen:
            return {"success": False, "error": "Pasillo origen no existe"}

        return bib_origen.mover_a(codigo, hacia)

    def buscar_global(self, termino: str) -> dict:
        """Busca en todos los pasillos"""

        resultados = {}

        for nombre, bib in self.bibliotecarios.items():
            resultados[nombre] = bib.buscar(termino=termino)

        return resultados

    def informe_global(self) -> dict:
        """Informe de todos los pasillos"""

        return {nombre: bib.get_informe() for nombre, bib in self.bibliotecarios.items()}


if __name__ == "__main__":
    bibliotecarios = BibliotecariosPasillo()

    print("=" * 60)
    print("📚 BIBLIOTECARIOS DE PASILLO")
    print("=" * 60)

    print("\n📋 Registrando archivos de prueba...")

    bib_aduana = bibliotecarios.get_bibliotecario("Aduana")
    test_file = BASE_PATH / "Aduana" / "test_receta.txt"
    test_file.write_text("Receta de tortilla española")

    resultado = bib_aduana.registrar(test_file, pasillo_origen="externo")
    print(f"   ✅ Registrado: {resultado}")

    print("\n🔍 Buscando en pasillo...")
    resultados = bib_aduana.buscar(termino="test")
    print(f"   Encontrados: {len(resultados)}")
    if resultados:
        print(f"   Código: {resultados[0]['codigo']}")

    print("\n📊 Informe global:")
    informe = bibliotecarios.informe_global()
    for pasillo, info in informe.items():
        print(f"   {pasillo}: {info['total_activos']} archivos")
