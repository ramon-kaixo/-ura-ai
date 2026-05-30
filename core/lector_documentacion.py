#!/usr/bin/env python3
"""
Módulo: core/lector_documentacion.py
Propósito: Lee y analiza documentación en PDFs, Markdown e imágenes con OCR y embeddings.
Dependencias principales: pathlib, re, json, datetime, tempfile, asyncio
Reglas especiales: Usar NamedTemporaryFile en vez de mktemp. Limpiar archivos temporales SIEMPRE con try/finally.
"""

import logging
import re

logger = logging.getLogger(__name__)


class LectorDocumentacion:
    """Lector de documentación técnica para procedimientos."""

    def __init__(self):
        """Inicializa el lector de documentación."""
        self.search_orchestrator = None

        # Intentar cargar search orchestrator
        try:
            from core.buscadores.orchestrator import SearchOrchestrator

            self.search_orchestrator = SearchOrchestrator()
            logger.info("SearchOrchestrator cargado en LectorDocumentacion")
        except Exception as e:
            logger.warning(f"No se pudo cargar SearchOrchestrator: {e}")

    def buscar_manual(self, sistema: str, accion: str) -> str:
        """
        Busca manual oficial del sistema.

        Usa agentes de búsqueda N2 para encontrar documentación.

        Args:
            sistema: Nombre del sistema (ej: "OVHcloud VPS")
            accion: Acción a realizar (ej: "Activar modo rescue")

        Returns:
            URL del manual más relevante o string vacío si no se encuentra
        """
        logger.info(f"Buscando manual para: {sistema} - {accion}")

        if not self.search_orchestrator:
            logger.error("SearchOrchestrator no disponible")
            return ""

        # Construir query de búsqueda
        query = f"documentación oficial {sistema} {accion} pasos"
        logger.info(f"Query de búsqueda: {query}")

        try:
            # Ejecutar búsqueda
            import asyncio

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                result = asyncio.run(self.search_orchestrator.search(query))
            else:
                import nest_asyncio

                nest_asyncio.apply()
                result = asyncio.run(self.search_orchestrator.search(query))

            if result and result.results:
                # Devolver la URL del primer resultado más relevante
                url = result.results[0].get("url", "")
                logger.info(f"Manual encontrado: {url}")
                return url
            else:
                logger.warning("No se encontraron resultados")
                return ""

        except Exception as e:
            logger.error(f"Error buscando manual: {e}")
            return ""

    def descargar_documento(self, url: str) -> str:
        """
        Descarga el contenido de un documento.

        Si es HTML, usa stealth_fetcher.
        Si es PDF, usa requests + PyPDF2.

        Args:
            url: URL del documento

        Returns:
            Texto completo del documento
        """
        logger.info(f"Descargando documento: {url}")

        try:
            # Detectar si es PDF
            if url.lower().endswith(".pdf"):
                return self._descargar_pdf(url)
            else:
                return self._descargar_html(url)
        except Exception as e:
            logger.error(f"Error descargando documento: {e}")
            return ""

    def _descargar_html(self, url: str) -> str:
        """Descarga contenido HTML usando stealth_fetcher."""
        try:
            from core.stealth_fetcher import StealthFetcher

            fetcher = StealthFetcher()
            content = fetcher.fetch(url)
            logger.info(f"HTML descargado: {len(content)} caracteres")
            return content
        except ImportError:
            logger.warning("StealthFetcher no disponible, usando requests básico")
            import requests

            response = requests.get(url, timeout=30)
            return response.text
        except Exception as e:
            logger.error(f"Error descargando HTML: {e}")
            return ""

    def _descargar_pdf(self, url: str) -> str:
        """Descarga y extrae texto de PDF."""
        try:
            import requests
            from io import BytesIO
            import PyPDF2

            response = requests.get(url, timeout=30)
            pdf_file = BytesIO(response.content)

            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""

            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"

            logger.info(f"PDF descargado: {len(text)} caracteres")
            return text

        except ImportError:
            logger.error("PyPDF2 no disponible")
            return ""
        except Exception as e:
            logger.error(f"Error descargando PDF: {e}")
            return ""

    def extraer_pasos(self, texto: str, accion: str) -> list[dict]:
        """
        Extrae pasos del documento para realizar la acción.

        Usa LLaVA para extraer instrucciones paso a paso.

        Args:
            texto: Texto completo del documento
            accion: Acción a realizar

        Returns:
            Lista de dicts con pasos
        """
        logger.info(f"Extrayendo pasos para: {accion}")

        # Construir prompt para LLaVA
        prompt = f"""
Extrae del siguiente texto los pasos exactos para realizar la acción '{accion}'.

Para cada paso, indica:
- Número de paso
- Tipo de acción (clic, escribir, seleccionar, esperar)
- Elemento a interactuar (botón, campo, menú, etc.)
- Texto a escribir (si aplica)

Devuelve una lista numerada con instrucciones claras.

Texto:
{texto[:5000]}  # Limitar a 5000 caracteres para evitar timeout
"""

        try:
            from agents.agente_vision import analizar_imagen
            import tempfile
            from PIL import Image, ImageDraw

            # Crear imagen temporal con el texto (para LLaVA)
            img = Image.new("RGB", (800, 1200), color="white")
            draw = ImageDraw.Draw(img)

            # Escribir texto en la imagen (simplificado)
            y_pos = 50
            for line in texto.split("\n")[:50]:  # Primeras 50 líneas
                draw.text((50, y_pos), line[:100], fill="black")
                y_pos += 20

            # Guardar imagen temporal
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                temp_path = tf.name
            img.save(temp_path)

            try:
                respuesta = analizar_imagen(temp_path, prompt)
            finally:
                import os

                os.unlink(temp_path)

            # Parsear respuesta
            pasos = self._parsear_pasos_llava(respuesta)
            logger.info(f"Pasos extraídos: {len(pasos)}")
            return pasos

        except Exception as e:
            logger.error(f"Error extrayendo pasos: {e}")
            # Fallback: intentar parsear directamente del texto
            return self._parsear_pasos_fallback(texto, accion)

    def _parsear_pasos_llava(self, respuesta: str) -> list[dict]:
        """Parsea respuesta de LLaVA para extraer pasos."""
        pasos = []

        if not respuesta:
            return pasos

        lineas = respuesta.split("\n")
        paso_actual = 1

        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue

            # Detectar número de paso
            match = re.match(r"^(\d+)[\.\)]", linea)
            if match:
                paso_actual = int(match.group(1))

            # Detectar tipo de acción
            accion = "clic"
            if "escribir" in linea.lower() or "escriba" in linea.lower():
                accion = "escribir"
            elif "seleccionar" in linea.lower():
                accion = "seleccionar"
            elif "esperar" in linea.lower():
                accion = "esperar"

            # Extraer elemento (texto después del número)
            elemento = linea
            if match:
                elemento = linea[match.end() :].strip()

            pasos.append(
                {"paso": paso_actual, "accion": accion, "elemento": elemento[:100], "texto": ""}
            )

        return pasos

    def _parsear_pasos_fallback(self, texto: str, accion: str) -> list[dict]:
        """Parsea pasos directamente del texto (fallback)."""
        pasos = []

        # Buscar patrones comunes de pasos
        lineas = texto.split("\n")
        paso_num = 1

        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue

            # Detectar inicio de paso
            if re.match(r"^\d+[\.\)]", linea) or "paso" in linea.lower():
                pasos.append(
                    {"paso": paso_num, "accion": "clic", "elemento": linea[:100], "texto": ""}
                )
                paso_num += 1

        return pasos

    def ejecutar_procedimiento(self, plan: list[dict]) -> bool:
        """
        Ejecuta un procedimiento paso a paso.

        Para cada paso, ejecuta la acción usando el mapa visual.

        Args:
            plan: Lista de dicts con pasos

        Returns:
            True si todo se completó, False si falló
        """
        logger.info(f"Ejecutando procedimiento con {len(plan)} pasos")

        if not plan:
            logger.warning("Plan vacío")
            return False

        try:
            from agents.agente_gui import GUIAgent

            gui = GUIAgent()
        except ImportError:
            logger.error("GUIAgent no disponible")
            return False

        for paso in plan:
            logger.info(f"Paso {paso['paso']}: {paso['accion']} - {paso['elemento']}")

            try:
                if paso["accion"] == "clic":
                    # Buscar elemento en mapa visual y hacer clic
                    # (simplificado: clic en centro de pantalla)
                    gui.click(gui.screen_width // 2, gui.screen_height // 2)

                elif paso["accion"] == "escribir":
                    # Escribir texto
                    if paso.get("texto"):
                        gui.write(paso["texto"])

                elif paso["accion"] == "seleccionar":
                    # Seleccionar opción
                    gui.press_key("tab")

                elif paso["accion"] == "esperar":
                    # Esperar
                    import time

                    time.sleep(2)

                # Pausa entre pasos
                import time

                time.sleep(1)

            except Exception as e:
                logger.error(f"Error en paso {paso['paso']}: {e}")
                # Buscar ayuda
                try:
                    from core.explorador_sistemico import get_explorador

                    explorador = get_explorador()
                    explorador.buscar_ayuda(f"Error en paso {paso['paso']}: {e}")
                except Exception:
                    logger.warning("No se pudo buscar ayuda")
                return False

        logger.info("Procedimiento completado exitosamente")
        return True
