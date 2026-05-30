#!/usr/bin/env python3
"""
agente_vision.py — Agente de visión para URA
Toma capturas de pantalla y las analiza con LLaVA
"""

import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

SISTEMA = Path(__file__).parent.parent
LOG = SISTEMA / "logs" / "vision.log"
LOG.parent.mkdir(exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")


def tomar_captura_legacy(ruta_salida=None):
    """Toma una captura de pantalla (legacy)."""
    if ruta_salida is None:
        ruta_salida = tempfile.mktemp(suffix=".png")

    try:
        subprocess.run(["screencapture", "-x", ruta_salida], check=True, timeout=10)
        log(f"Captura guardada: {ruta_salida}")
        return ruta_salida
    except Exception as e:
        log(f"Error capturando: {e}")
        return None


def analizar_imagen_legacy(ruta_imagen, pregunta=None):
    """Analiza una imagen con LLaVA (legacy)."""
    if pregunta is None:
        pregunta = "Describe detalladamente qué ves en esta pantalla. Incluye texto visible, interfaz, colores y cualquier elemento notable."

    try:
        result = subprocess.run(
            ["ollama", "run", "llava", pregunta, ruta_imagen],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            log(f"Error LLaVA: {result.stderr}")
            return None
    except Exception as e:
        log(f"Excepción: {e}")
        return None


def detectar_pantalla_bloqueada():
    """Detecta si la pantalla está bloqueada."""
    captura = tomar_captura_legacy()
    if not captura:
        return {"bloqueada": True, "razon": "No se pudo capturar"}

    respuesta = analizar_imagen_legacy(
        captura,
        "¿La pantalla muestra un bloqueo, login, pantalla de inicio de sesión o requiere contraseña? Responde sí o no.",
    )

    os.remove(captura)

    if respuesta and any(
        p in respuesta.lower()
        for p in ["sí", "si", "yes", "bloqueo", "lock", "login", "contraseña", "password"]
    ):
        return {"bloqueada": True, "respuesta": respuesta[:200]}

    return {"bloqueada": False}


def detectar_error_visible():
    """Busca errores visibles en pantalla."""
    captura = tomar_captura_legacy()
    if not captura:
        return {"error": True, "razon": "No se pudo capturar"}

    respuesta = analizar_imagen_legacy(
        captura,
        "¿Ves algún mensaje de error, alerta roja, warning, diálogo de error, o notificación de problema en esta pantalla? Describe lo que ves.",
    )

    os.remove(captura)

    return {
        "error_detectado": respuesta is not None and len(respuesta) > 50,
        "descripcion": respuesta[:500] if respuesta else "Sin análisis",
    }


def describir_pantalla():
    """Describe la pantalla actual."""
    captura = tomar_captura_legacy()
    if not captura:
        return "No se pudo capturar la pantalla"

    descripcion = analizar_imagen_legacy(captura)
    os.remove(captura)

    return descripcion or "Sin descripción disponible"


def generar_informe():
    desc = describir_pantalla()
    return f"""
╔══════════════════════════════════════════════════════╗
║          ANÁLISIS DE PANTALLA — {datetime.now().strftime("%Y-%m-%d %H:%M")}
╠══════════════════════════════════════════════════════╣
║  Estado: Análisis completado
╚══════════════════════════════════════════════════════╝

{desc}
"""


class AgenteVision:
    """Agente de visión para URA con capacidades de captura y análisis de imágenes"""

    def __init__(self):
        """Inicializar agente de visión"""
        self.log_path = LOG

    def _log(self, msg: str):
        """Escribir log"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_path, "a") as f:
            f.write(f"[{ts}] {msg}\n")

    def tomar_captura(self, ruta_salida: str | Path = None) -> Path | None:
        """
        Toma una captura de pantalla

        Args:
            ruta_salida: Ruta donde guardar la captura (opcional)

        Returns:
            Path a la captura o None si falló
        """
        if ruta_salida is None:
            ruta_salida = tempfile.mktemp(suffix=".png")

        ruta_salida = Path(ruta_salida)

        try:
            subprocess.run(["screencapture", "-x", str(ruta_salida)], check=True, timeout=10)
            self._log(f"Captura guardada: {ruta_salida}")
            return ruta_salida
        except Exception as e:
            self._log(f"Error capturando: {e}")
            return None

    def execute(self, imagen_path: str | Path, pregunta: str = None) -> str:
        """
        Analiza una imagen con LLaVA/Ollama

        Args:
            imagen_path: Ruta a la imagen
            pregunta: Pregunta específica (opcional)

        Returns:
            Descripción de la imagen o None si falló
        """
        imagen_path = Path(imagen_path)

        if not imagen_path.exists():
            self._log(f"Imagen no encontrada: {imagen_path}")
            return None

        if pregunta is None:
            pregunta = "Describe detalladamente qué ves en esta imagen. Incluye texto visible, objetos, colores y cualquier elemento notable."

        try:
            result = subprocess.run(
                ["ollama", "run", "llava", pregunta, str(imagen_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                descripcion = result.stdout.strip()
                self._log(f"Análisis completado: {len(descripcion)} caracteres")
                return descripcion
            else:
                self._log(f"Error LLaVA: {result.stderr}")
                return None
        except Exception as e:
            self._log(f"Excepción analizando imagen: {e}")
            return None

    def analizar_imagen(self, ruta_imagen: str | Path, pregunta: str = None) -> str:
        """
        Analiza una imagen (método de compatibilidad)

        Args:
            ruta_imagen: Ruta a la imagen
            pregunta: Pregunta específica (opcional)

        Returns:
            Descripción de la imagen
        """
        return self.execute(ruta_imagen, pregunta)

    def detectar_pantalla_bloqueada(self) -> dict:
        """Detecta si la pantalla está bloqueada"""
        captura = self.tomar_captura()
        if not captura:
            return {"bloqueada": True, "razon": "No se pudo capturar"}

        respuesta = self.execute(
            captura,
            "¿La pantalla muestra un bloqueo, login, pantalla de inicio de sesión o requiere contraseña? Responde sí o no.",
        )

        captura.unlink(missing_ok=True)

        if respuesta and any(
            p in respuesta.lower()
            for p in ["sí", "si", "yes", "bloqueo", "lock", "login", "contraseña", "password"]
        ):
            return {"bloqueada": True, "respuesta": respuesta[:200]}

        return {"bloqueada": False}

    def detectar_error_visible(self) -> dict:
        """Busca errores visibles en pantalla"""
        captura = self.tomar_captura()
        if not captura:
            return {"error": True, "razon": "No se pudo capturar"}

        respuesta = self.execute(
            captura,
            "¿Ves algún mensaje de error, alerta roja, warning, diálogo de error, o notificación de problema en esta pantalla? Describe lo que ves.",
        )

        captura.unlink(missing_ok=True)

        return {
            "error_detectado": respuesta is not None and len(respuesta) > 50,
            "descripcion": respuesta[:500] if respuesta else "Sin análisis",
        }

    def describir_pantalla(self) -> str:
        """Describe la pantalla actual"""
        captura = self.tomar_captura()
        if not captura:
            return "No se pudo capturar la pantalla"

        descripcion = self.execute(captura)
        captura.unlink(missing_ok=True)

        return descripcion or "Sin descripción disponible"

    def generar_informe(self) -> str:
        """Genera informe de análisis de pantalla"""
        desc = self.describir_pantalla()
        return f"""
╔══════════════════════════════════════════════════════╗
║          ANÁLISIS DE PANTALLA — {datetime.now().strftime("%Y-%m-%d %H:%M")}
╠══════════════════════════════════════════════════════╣
║  Estado: Análisis completado
╚══════════════════════════════════════════════════════╝

{desc}
"""

    # Métodos de compatibilidad con interfaz de agentes URA
    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVision"""
        texto_lower = texto.lower()
        if "captura" in texto_lower or "pantalla" in texto_lower:
            return self.describir_pantalla()
        elif "error" in texto_lower:
            return json.dumps(self.detectar_error_visible(), indent=2)
        elif "bloqueada" in texto_lower or "lock" in texto_lower:
            return json.dumps(self.detectar_pantalla_bloqueada(), indent=2)
        else:
            return (
                "Puedo ver pantalla, capturar imágenes y hacer OCR. Usa: captura, error, bloqueada"
            )

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVision"""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVision"""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVision"""
        return self.procesar(texto)


# Singleton para consistencia con otros agentes
_vision_instance = None


def get_agente_vision() -> AgenteVision:
    """Obtener instancia singleton de AgenteVision"""
    global _vision_instance
    if _vision_instance is None:
        _vision_instance = AgenteVision()
    return _vision_instance


if __name__ == "__main__":
    import sys

    if "--capturar" in sys.argv:
        vision = AgenteVision()
        print(vision.describir_pantalla())
    elif "--error" in sys.argv:
        vision = AgenteVision()
        print(json.dumps(vision.detectar_error_visible(), indent=2))
    elif "--bloqueada" in sys.argv:
        vision = AgenteVision()
        print(json.dumps(vision.detectar_pantalla_bloqueada(), indent=2))
    else:
        vision = AgenteVision()
        print(vision.generar_informe())
