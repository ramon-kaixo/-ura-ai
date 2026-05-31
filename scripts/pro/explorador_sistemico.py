#!/usr/bin/env python3
"""
Explorador Sistemico — Módulo de exploración visual de URA

Este módulo permite a URA explorar interfaces gráficas de forma sistemática
mediante un flujo de 4 fases: Reconocimiento, Catalogación, Estudio Funcional y Ejecución Informada.

Características:
- Singleton pattern (una sola instancia)
- Anti-detección con pausas aleatorias
- Integración con agente_gui y agente_vision
- Mapas de elementos guardados en ~/.ura/explorador/
"""

import json
import logging
import random
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Rutas
EXPLORADOR_DIR = Path.home() / ".ura" / "explorador"
EXPLORADOR_DIR.mkdir(parents=True, exist_ok=True)


class ExploradorSistemico:
    """Explorador sistemático de interfaces gráficas (singleton)."""

    _instance: Optional["ExploradorSistemico"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.current_screenshot = None
        self.current_map = None
        self.last_coordinates = None

        logger.info("ExploradorSistemico inicializado")

    def _random_delay(self, min_sec: float = 0.3, max_sec: float = 1.5):
        """Pausa aleatoria para anti-detección."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _avoid_pattern(self, x: int, y: int) -> tuple[int, int]:
        """Evita repetir el mismo patrón de coordenadas."""
        if self.last_coordinates and self.last_coordinates == (x, y):
            # Añadir pequeño offset aleatorio
            offset_x = random.randint(-5, 5)
            offset_y = random.randint(-5, 5)
            x = max(0, x + offset_x)
            y = max(0, y + offset_y)

        self.last_coordinates = (x, y)
        return x, y

    # ============================================================
    # FASE 1 – RECONOCIMIENTO
    # ============================================================

    def reconocer_pantalla(self, url: str | None = None) -> dict:
        """
        FASE 1: Reconocimiento de pantalla.

        Si se proporciona URL, abre la página.
        Toma captura y divide en regiones lógicas.
        Analiza cada región con LLaVA.

        Args:
            url: URL opcional para abrir en navegador

        Returns:
            Dict con descripciones de cada región
        """
        logger.info("=== FASE 1: RECONOCIMIENTO ===")

        # Abrir URL si se proporciona
        if url:
            logger.info(f"Abriendo URL: {url}")
            subprocess.run(["open", "-a", "Google Chrome", url], check=True)
            self._random_delay(2, 4)

        # Importar agente de visión
        try:
            from agents.agente_vision import tomar_captura, analizar_imagen
        except ImportError as e:
            logger.error(f"No se pudo importar agente_vision: {e}")
            return {"error": "No se pudo cargar agente_vision"}

        # Tomar captura
        self.current_screenshot = tomar_captura()
        if not self.current_screenshot:
            return {"error": "No se pudo tomar captura"}

        logger.info(f"Captura tomada: {self.current_screenshot}")

        # Obtener tamaño de pantalla
        try:
            from agents.agente_gui import GUIAgent

            gui = GUIAgent()
            screen_width, screen_height = gui.screen_width, gui.screen_height
        except:
            screen_width, screen_height = 1920, 1080  # Default

        logger.info(f"Pantalla: {screen_width}x{screen_height}")

        # Definir regiones
        regiones = {
            "menu_lateral": {
                "descripcion": "menú lateral (x<300)",
                "coords": (0, 0, 300, screen_height),
                "pregunta": "Describe cada botón, pestaña, campo de texto, enlace o icono visible en la región izquierda de esta pantalla (menú lateral). Sé preciso con las posiciones.",
            },
            "area_contenido": {
                "descripcion": "área de contenido (x>300)",
                "coords": (300, 0, screen_width, screen_height),
                "pregunta": "Describe cada botón, pestaña, campo de texto, enlace o icono visible en la región central/derecha de esta pantalla (área de contenido). Sé preciso con las posiciones.",
            },
            "barra_superior": {
                "descripcion": "barra superior (y<100)",
                "coords": (0, 0, screen_width, 100),
                "pregunta": "Describe cada botón, pestaña, campo de texto, enlace o icono visible en la barra superior de esta pantalla. Sé preciso con las posiciones.",
            },
            "barra_inferior": {
                "descripcion": "barra inferior (y>800)",
                "coords": (0, max(800, screen_height - 200), screen_width, screen_height),
                "pregunta": "Describe cada botón, pestaña, campo de texto, enlace o icono visible en la barra inferior de esta pantalla. Sé preciso con las posiciones.",
            },
        }

        # Analizar cada región
        descripciones = {}
        for nombre, info in regiones.items():
            logger.info(f"Analizando región: {nombre}")
            self._random_delay()

            descripcion = analizar_imagen(self.current_screenshot, info["pregunta"])
            descripciones[nombre] = {
                "descripcion_region": info["descripcion"],
                "coords": info["coords"],
                "analisis_llava": descripcion or "Sin análisis",
            }
            logger.info(f"Región {nombre} analizada")

        logger.info("=== FASE 1 COMPLETADA ===")
        return descripciones

    # ============================================================
    # FASE 2 – CATALOGACIÓN
    # ============================================================

    def catalogar_elementos(self, descripciones: dict) -> dict:
        """
        FASE 2: Catalogación de elementos.

        Extrae elementos individuales de las descripciones.
        Usa OCR como respaldo.
        Construye mapa JSON.

        Args:
            descripciones: Dict con descripciones de cada región

        Returns:
            Dict con mapa de elementos
        """
        logger.info("=== FASE 2: CATALOGACIÓN ===")

        mapa = {
            "fecha": datetime.now().isoformat(),
            "screenshot": str(self.current_screenshot) if self.current_screenshot else None,
            "elementos": [],
        }

        # Extraer elementos de cada región
        for nombre_region, info in descripciones.items():
            if "error" in info:
                continue

            analisis = info.get("analisis_llava", "")
            coords = info.get("coords", (0, 0, 0, 0))

            # Parsear análisis de LLaVA para extraer elementos
            elementos_extraidos = self._parsear_elementos_llava(analisis, nombre_region, coords)
            mapa["elementos"].extend(elementos_extraidos)

        # Guardar mapa
        nombre_sitio = self._extraer_nombre_sitio()
        mapa_path = EXPLORADOR_DIR / f"{nombre_sitio}_map.json"

        with open(mapa_path, "w", encoding="utf-8") as f:
            json.dump(mapa, f, indent=2, ensure_ascii=False)

        logger.info(f"Mapa guardado: {mapa_path}")
        self.current_map = mapa

        logger.info("=== FASE 2 COMPLETADA ===")
        return mapa

    def _parsear_elementos_llava(self, analisis: str, region: str, coords: tuple) -> list[dict]:
        """Parsea análisis de LLaVA para extraer elementos."""
        elementos = []

        # Palabras clave para tipos de elementos
        tipo_keywords = {
            "botón": ["botón", "button", "click"],
            "enlace": ["enlace", "link", "hipervínculo"],
            "campo": ["campo", "input", "textbox", "textarea"],
            "pestaña": ["pestaña", "tab"],
            "icono": ["icono", "icon"],
            "menú": ["menú", "menu"],
            "checkbox": ["checkbox", "casilla"],
            "dropdown": ["dropdown", "select", "desplegable"],
        }

        # Dividir análisis en líneas o frases
        lineas = analisis.split(". ")

        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue

            # Determinar tipo
            elemento_tipo = "otro"
            for tipo, keywords in tipo_keywords.items():
                if any(kw in linea.lower() for kw in keywords):
                    elemento_tipo = tipo
                    break

            # Extraer texto visible (asumir que es el texto entre comillas o la primera parte)
            texto_visible = linea[:100]  # Simplificado

            # Coordenadas aproximadas (centro de la región)
            x_center = (coords[0] + coords[2]) // 2
            y_center = (coords[1] + coords[3]) // 2

            elemento = {
                "nombre": texto_visible,
                "tipo": elemento_tipo,
                "region": region,
                "coordenadas_aproximadas": [x_center, y_center],
                "texto_visible": texto_visible,
                "funcion_inferida": "",
            }

            elementos.append(elemento)

        return elementos

    def _extraer_nombre_sitio(self) -> str:
        """Extrae nombre del sitio de la URL o usa timestamp."""
        if self.current_screenshot:
            # Usar timestamp del nombre del archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"sitio_{timestamp}"
        return f"sitio_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ============================================================
    # FASE 3 – ESTUDIO FUNCIONAL
    # ============================================================

    def estudiar_funcionalidad(self, mapa: dict) -> dict:
        """
        FASE 3: Estudio funcional de elementos.

        Para cada elemento, recorta región y pregunta a LLaVA su función.
        Rellena campo funcion_inferida.

        Args:
            mapa: Dict con mapa de elementos

        Returns:
            Dict con mapa actualizado
        """
        logger.info("=== FASE 3: ESTUDIO FUNCIONAL ===")

        if not self.current_screenshot:
            logger.error("No hay captura actual para estudiar funcionalidad")
            return mapa

        try:
            from agents.agente_vision import analizar_imagen
            from PIL import Image
        except ImportError as e:
            logger.error(f"No se pudo importar dependencias: {e}")
            return mapa

        try:
            img = Image.open(self.current_screenshot)
        except Exception as e:
            logger.error(f"Error abriendo imagen: {e}")
            return mapa

        # Estudiar cada elemento
        for elemento in mapa.get("elementos", []):
            if elemento.get("funcion_inferida"):
                continue  # Ya estudiado

            coords = elemento.get("coordenadas_aproximadas", [0, 0])
            x, y = coords[0], coords[1]

            # Recortar región alrededor del elemento (100x100)
            try:
                region = img.crop((max(0, x - 50), max(0, y - 50), x + 50, y + 50))

                # Guardar recorte temporal
                temp_path = EXPLORADOR_DIR / f"temp_elemento_{elemento.get('tipo', 'otro')}.png"
                region.save(temp_path)

                # Preguntar a LLaVA
                pregunta = "¿Para qué sirve este elemento en el contexto de esta página? ¿Qué acción realizará si hago clic en él?"
                respuesta = analizar_imagen(str(temp_path), pregunta)

                elemento["funcion_inferida"] = respuesta or "Función desconocida"
                logger.info(
                    f"Elemento {elemento.get('nombre')}: {elemento['funcion_inferida'][:50]}"
                )

                # Limpiar temporal
                temp_path.unlink()

                self._random_delay()
            except Exception as e:
                logger.warning(f"Error estudiando elemento {elemento}: {e}")
                elemento["funcion_inferida"] = "Error en análisis"

        # Guardar mapa actualizado
        nombre_sitio = self._extraer_nombre_sitio()
        mapa_path = EXPLORADOR_DIR / f"{nombre_sitio}_map.json"

        with open(mapa_path, "w", encoding="utf-8") as f:
            json.dump(mapa, f, indent=2, ensure_ascii=False)

        logger.info("=== FASE 3 COMPLETADA ===")
        return mapa

    # ============================================================
    # FASE 4 – EJECUCIÓN INFORMADA
    # ============================================================

    def ejecutar(self, accion: str) -> bool:
        """
        FASE 4: Ejecución informada.

        Busca elemento que coincida con la acción y lo ejecuta.

        Args:
            accion: Orden en lenguaje natural

        Returns:
            True si exitoso, False si falla
        """
        logger.info(f"=== FASE 4: EJECUCIÓN INFORMADA - {accion} ===")

        if not self.current_map:
            logger.error("No hay mapa actual. Ejecuta explorar_y_ejecutar primero.")
            return False

        # Buscar elemento que coincida
        elemento = self._buscar_elemento_por_accion(accion)

        if not elemento:
            logger.warning(f"No se encontró elemento para acción: {accion}")
            return self.buscar_ayuda(f"No se encontró elemento para: {accion}")

        # Ejecutar acción
        try:

            gui = GUIAgent()

            coords = elemento.get("coordenadas_aproximadas", [0, 0])
            x, y = self._avoid_pattern(coords[0], coords[1])

            logger.info(f"Ejecutando clic en ({x}, {y}) para {elemento.get('nombre')}")
            gui.click(x, y)

            self._random_delay()
            logger.info("Acción ejecutada exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error ejecutando acción: {e}")
            return self.buscar_ayuda(f"Error ejecutando acción: {e}")

    def _buscar_elemento_por_accion(self, accion: str) -> dict | None:
        """Busca elemento cuyo nombre o función coincida con la acción."""
        accion_lower = accion.lower()

        for elemento in self.current_map.get("elementos", []):
            nombre = elemento.get("nombre", "").lower()
            funcion = elemento.get("funcion_inferida", "").lower()

            # Coincidencia exacta o parcial
            if accion_lower in nombre or accion_lower in funcion:
                return elemento

            # Coincidencia por palabras clave
            if any(palabra in nombre or palabra in funcion for palabra in accion_lower.split()):
                return elemento

        return None

    # ============================================================
    # MÉTODOS ADICIONALES
    # ============================================================

    def buscar_ayuda(self, mensaje_error: str | None = None) -> bool:
        """
        Busca ayuda en la pantalla.

        Busca iconos de chat, burbujas de ayuda, enlaces de soporte.
        Si no hay chat, busca pestañas de errores, notificaciones, logs.

        Args:
            mensaje_error: Mensaje de error opcional para enviar al chat

        Returns:
            True si se encontró ayuda, False si no
        """
        logger.info("Buscando ayuda...")

        captura = tomar_captura()
        if not captura:
            return False

        # Buscar iconos de ayuda
        pregunta = "¿Ves algún icono de chat, burbuja de ayuda, botón de soporte, enlace de contacto o botón de ayuda en esta pantalla?"
        respuesta = analizar_imagen(captura, pregunta)

        if "sí" in respuesta.lower() or "si" in respuesta.lower():
            logger.info("Encontrado elemento de ayuda")
            # Intentar hacer clic en centro de pantalla (simplificado)
            try:

                gui = GUIAgent()
                gui.click(gui.screen_width // 2, gui.screen_height // 2)

                if mensaje_error:
                    self._random_delay()
                    gui.write(mensaje_error)

                return True
            except:
                return False

        # Buscar pestañas de errores/notificaciones
        pregunta_errores = "¿Ves alguna pestaña, botón o enlace que diga 'Errores', 'Notificaciones', 'Alertas', 'Logs' o 'Soporte'?"
        respuesta_errores = analizar_imagen(captura, pregunta_errores)

        if "sí" in respuesta_errores.lower() or "si" in respuesta_errores.lower():
            logger.info("Encontrada pestaña de errores/notificaciones")
            return True

        logger.warning("No se encontró ayuda en pantalla")
        return False

    def detectar_patrones_robot(self):
        """Asegura que los movimientos tengan pausas aleatorias."""
        # Este método se llama implícitamente en cada acción
        self._random_delay()

    def explorar_y_ejecutar(self, url: str, accion: str) -> bool:
        """
        Método principal: explora y ejecuta acción.

        Ejecuta las 4 fases en orden y luego ejecuta la acción pedida.

        Args:
            url: URL a explorar
            accion: Acción a ejecutar

        Returns:
            True si exitoso, False si falla
        """
        logger.info(f"=== EXPLORAR Y EJECUTAR: {url} - {accion} ===")

        try:
            # FASE 1: Reconocimiento
            descripciones = self.reconocer_pantalla(url)
            if "error" in descripciones:
                return False

            # FASE 2: Catalogación
            mapa = self.catalogar_elementos(descripciones)

            # FASE 3: Estudio Funcional
            mapa = self.estudiar_funcionalidad(mapa)

            # FASE 4: Ejecución Informada
            resultado = self.ejecutar(accion)

            return resultado

        except Exception as e:
            logger.error(f"Error en explorar_y_ejecutar: {e}")
            return False

    def ejecutar_con_manual(self, sistema: str, accion: str) -> bool:
        """
        Ejecuta acción usando documentación oficial.

        Flujo:
        1. Busca manual del sistema
        2. Descarga documento
        3. Extrae pasos
        4. Explora pantalla (fases 1-3)
        5. Ejecuta pasos usando mapa visual
        6. Si falla, busca ayuda

        Args:
            sistema: Nombre del sistema (ej: "OVHcloud VPS")
            accion: Acción a realizar (ej: "Activar modo rescue")

        Returns:
            True si exitoso, False si falla
        """
        logger.info(f"=== EJECUTAR CON MANUAL: {sistema} - {accion} ===")

        try:
            from core.lector_documentacion import LectorDocumentacion

            lector = LectorDocumentacion()

            # 1. Buscar manual
            logger.info("Buscando manual...")
            url_manual = lector.buscar_manual(sistema, accion)
            if not url_manual:
                logger.warning("No se encontró manual, usando exploración directa")
                # Fallback: usar exploración directa sin manual
                return self._exploracion_directa(sistema, accion)

            # 2. Descargar documento
            logger.info("Descargando documento...")
            texto_documento = lector.descargar_documento(url_manual)
            if not texto_documento:
                logger.warning("No se pudo descargar documento")
                return self._exploracion_directa(sistema, accion)

            # 3. Extraer pasos
            logger.info("Extrayendo pasos...")
            pasos = lector.extraer_pasos(texto_documento, accion)
            if not pasos:
                logger.warning("No se pudieron extraer pasos")
                return self._exploracion_directa(sistema, accion)

            logger.info(f"Pasos extraídos: {len(pasos)}")

            # 4. Explorar pantalla (fases 1-3)
            logger.info("Explorando pantalla...")
            descripciones = self.reconocer_pantalla()
            if "error" in descripciones:
                logger.warning("Error en reconocimiento, ejecutando pasos sin mapa")
            else:
                mapa = self.catalogar_elementos(descripciones)
                mapa = self.estudiar_funcionalidad(mapa)

            # 5. Ejecutar pasos
            logger.info("Ejecutando pasos...")
            resultado = lector.ejecutar_procedimiento(pasos)

            if not resultado:
                logger.warning("Fallo ejecutando pasos, buscando ayuda")
                self.buscar_ayuda("Error ejecutando procedimiento del manual")

            return resultado

        except Exception as e:
            logger.error(f"Error en ejecutar_con_manual: {e}")
            # Fallback: intentar exploración directa
            return self._exploracion_directa(sistema, accion)

    def _exploracion_directa(self, sistema: str, accion: str) -> bool:
        """Fallback: exploración directa sin manual."""
        logger.info("=== EXPLORACIÓN DIRECTA (FALLBACK) ===")

        try:
            # Intentar detectar URL del sistema
            if "ovh" in sistema.lower():
                url = "https://www.ovh.com/manager/#/vps/vps-57a71715.vps.ovh.net/dashboard"
            else:
                logger.warning("No se pudo determinar URL del sistema")
                return False

            # Ejecutar exploración directa
            return self.explorar_y_ejecutar(url, accion)

        except Exception as e:
            logger.error(f"Error en exploración directa: {e}")
            return False


# ============================================================
# SINGLETON HELPER
# ============================================================

_explorador_instance: ExploradorSistemico | None = None


def get_explorador() -> ExploradorSistemico:
    """Devuelve la instancia singleton de ExploradorSistemico."""
    global _explorador_instance
    if _explorador_instance is None:
        _explorador_instance = ExploradorSistemico()
    return _explorador_instance
