#!/usr/bin/env python3
"""
Guardian Residente - Vigilante de carpetas con watchdog
Vigila que no entren archivos no autorizados
"""

import hashlib
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()


class GestorEventos(FileSystemEventHandler):
    """Maneja los eventos del sistema de archivos"""

    def __init__(self, pasillo: str, callback=None):
        self.pasillo = pasillo
        self.callback = callback
        self.eventos = []

    def on_any_event(self, event):
        """Procesa cualquier evento del sistema de archivos"""

        if event.is_directory:
            return

        tipo = event.event_type
        path = event.src_path
        nombre = Path(path).name

        evento = {
            "timestamp": datetime.now().isoformat(),
            "pasillo": self.pasillo,
            "tipo": tipo,
            "path": path,
            "nombre": nombre,
            "hash": hashlib.md5(path.encode(), usedforsecurity=False).hexdigest()[:8],
        }

        self.eventos.append(evento)

        if self.callback:
            self.callback(evento)


class GuardianResidente:
    """Vigilante de un pasillo/carpeta específico"""

    def __init__(self, pasillo: str, ruta_carpeta: str):
        self.pasillo = pasillo
        self.ruta = Path(ruta_carpeta)
        self.observador = None
        self.gestor = None
        self.activo = False
        self.eventos = []
        self._lock = threading.Lock()

        self.ruta.mkdir(parents=True, exist_ok=True)

    def iniciar(self, callback=None):
        """Inicia la vigilancia de la carpeta"""

        if self.activo:
            return {"success": False, "error": "Ya activo"}

        self.gestor = GestorEventos(self.pasillo, callback=callback)
        self.observador = Observer()
        self.observador.schedule(self.gestor, str(self.ruta), recursive=True)
        self.observador.start()
        self.activo = True

        return {"success": True, "mensaje": f"Guardian {self.pasillo} vigila {self.ruta}"}

    def parar(self):
        """Detiene la vigilancia"""

        if self.observador:
            self.observador.stop()
            self.observador.join()
        self.activo = False
        return {"success": True, "mensaje": f"Guardian {self.pasillo} detenido"}

    def obtener_eventos(self, ultimos: int = 10) -> list:
        """Devuelve los últimos eventos del pasillo"""

        with self._lock:
            return self.eventos[-ultimos:] if len(self.eventos) >= ultimos else self.eventos

    def get_estado(self) -> dict:
        """Estado actual del guardian"""

        return {
            "pasillo": self.pasillo,
            "ruta": str(self.ruta),
            "activo": self.activo,
            "eventos_count": len(self.eventos),
        }


class GuardianesResidentes:
    """Gestor de todos los guardianes"""

    def __init__(self, base_path: str | None = None):
        if base_path is None:
            base_path = str(BASE_DIR / "sandbox")
        self.base = Path(base_path)
        self.guardianes = {}
        self._lock = threading.Lock()

        self._crear_pasillos()

    def _crear_pasillos(self):
        """Crea los 4 pasillos si no existen"""

        pasillos = ["Aduana", "Pruebas", "Boveda", "Laboratorio"]

        for pasillo in pasillos:
            ruta = self.base / pasillo
            ruta.mkdir(parents=True, exist_ok=True)
            self.guardianes[pasillo] = GuardianResidente(pasillo, str(ruta))

    def iniciar_todos(self, callback=None) -> dict:
        """Inicia todos los guardianes"""

        resultados = {}

        with self._lock:
            for nombre, guardian in self.guardianes.items():
                resultados[nombre] = guardian.iniciar(callback=callback)

        return resultados

    def parar_todos(self) -> dict:
        """Detiene todos los guardianes"""

        resultados = {}

        with self._lock:
            for nombre, guardian in self.guardianes.items():
                resultados[nombre] = guardian.parar()

        return resultados

    def get_estado(self) -> dict:
        """Estado de todos los guardianes"""

        return {nombre: guardian.get_estado() for nombre, guardian in self.guardianes.items()}


def callback_evento(evento):
    """Callback para procesar eventos"""
    print(f"👁️ {evento['pasillo']}: {evento['tipo']} - {evento['nombre']}")


if __name__ == "__main__":
    guardianes = GuardianesResidentes()

    print("=" * 60)
    print("👁️ GUARDIANES RESIDENTES - VIGILANCIA DE CARPETAS")
    print("=" * 60)

    print("\n🚀 Iniciando guardianes...")
    resultados = guardianes.iniciar_todos(callback=callback_evento)

    for nombre, resultado in resultados.items():
        estado = "✅" if resultado["success"] else "❌"
        print(f"   {estado} {nombre}: {resultado.get('mensaje', '')}")

    print("\n📝 Simulando actividad en los pasillos...")

    pasillos = ["Aduana", "Pruebas", "Boveda", "Laboratorio"]

    for pasillo in pasillos:
        ruta = guardianes.base / pasillo
        archivo = ruta / f"test_{pasillo.lower()}.txt"
        archivo.write_text(f"Archivo de prueba - {pasillo}")
        time.sleep(0.2)

    print("\n📊 Estado de guardianes:")
    estado = guardianes.get_estado()

    for nombre, info in estado.items():
        print(f"   {nombre}: {info['eventos_count']} eventos, activo={info['activo']}")

    print("\n🛑 Deteniendo guardianes...")
    guardianes.parar_todos()
    print("   ✅ Guardianes detenidos")
