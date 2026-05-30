#!/usr/bin/env python3
"""
URA Técnico Supervisor - Verificación hacia arriba
Verifica cada respuesta de URA contrastando con 3 fuentes
"""

from datetime import datetime, UTC
from typing import Any

from core.logging_config import get_logger

logger = get_logger("tecnico_supervisor", log_dir="./logs")


class TecnicoSupervisor:
    """Técnico Supervisor - Verifica respuestas de URA"""

    def __init__(self):
        """Inicializar técnico supervisor"""
        self.fuentes = [
            "DeepSeek",  # DeepSeek
            "Claude",  # Claude AI
            "Gemini",  # Gemini
            "ChatGPT",  # ChatGPT
        ]
        self.verificaciones = []

    def verificar_respuesta(self, respuesta_ura: str, peticion: str) -> dict[str, Any]:
        """
        Verificar respuesta de URA contrastando con 4 fuentes (DeepSeek, Claude, Gemini, ChatGPT)

        Args:
            respuesta_ura: Respuesta de URA
            peticion: Petición original

        Returns:
            Resultado de verificación
        """
        logger.info(f"Verificando respuesta para: {peticion[:50]}...")

        # Obtener respuestas de 3 fuentes
        respuestas_fuentes = []
        for fuente in self.fuentes:
            respuesta_fuente = self._consultar_fuente(fuente, peticion)
            respuestas_fuentes.append({"fuente": fuente, "respuesta": respuesta_fuente})

        # Comparar respuestas
        coincidencias = self._comparar_respuestas(respuesta_ura, respuestas_fuentes)

        # Determinar si aprueba
        umbral_aprobacion = 0.7  # 70% de coincidencia
        aprobada = coincidencias >= umbral_aprobacion

        resultado = {
            "peticion": peticion,
            "respuesta_ura": respuesta_ura,
            "respuestas_fuentes": respuestas_fuentes,
            "coincidencia": coincidencias,
            "aprobada": aprobada,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        # Guardar verificación
        self.verificaciones.append(resultado)

        if aprobada:
            logger.info(f"Respuesta APROBADA (coincidencia: {coincidencias:.2%})")
        else:
            logger.warning(f"Respuesta RECHAZADA (coincidencia: {coincidencias:.2%})")

        return resultado

    def _consultar_fuente(self, fuente: str, peticion: str) -> str:
        """
        Consultar una fuente (DeepSeek, Claude, Gemini, ChatGPT)
        Con fallback automático si falla

        Args:
            fuente: Nombre de la fuente
            peticion: Petición

        Returns:
            Respuesta de la fuente
        """
        try:
            if fuente == "DeepSeek":
                return self._consultar_con_fallback(self._consultar_deepseek, peticion)
            elif fuente == "Claude":
                return self._consultar_con_fallback(self._consultar_claude, peticion)
            elif fuente == "Gemini":
                return self._consultar_con_fallback(self._consultar_gemini, peticion)
            elif fuente == "ChatGPT":
                return self._consultar_con_fallback(self._consultar_chatgpt, peticion)
            else:
                return ""
        except Exception as e:
            logger.error(f"Error consultando {fuente}: {e}")
            return ""

    def _consultar_deepseek(self, peticion: str) -> str:
        """Consultar DeepSeek"""
        try:
            from core.integraciones.deepseek_api import deepseek_api

            if deepseek_api:
                return deepseek_api.consultar(peticion)
            else:
                # Fallback a modo demo
                return self._respuesta_demo("DeepSeek", peticion)
        except Exception as e:
            logger.error(f"Error consultando DeepSeek: {e}")
            return self._respuesta_demo("DeepSeek", peticion)

    def _consultar_claude(self, peticion: str) -> str:
        """Consultar Claude AI"""
        try:
            from core.integraciones.claude_api import claude_api

            if claude_api:
                return claude_api.consultar(peticion)
            else:
                return self._respuesta_demo("Claude", peticion)
        except Exception as e:
            logger.error(f"Error consultando Claude: {e}")
            return self._respuesta_demo("Claude", peticion)

    def _consultar_gemini(self, peticion: str) -> str:
        """Consultar Gemini"""
        try:
            from core.integraciones.gemini_api import gemini_api

            if gemini_api:
                return gemini_api.consultar(peticion)
            else:
                return self._respuesta_demo("Gemini", peticion)
        except Exception as e:
            logger.error(f"Error consultando Gemini: {e}")
            return self._respuesta_demo("Gemini", peticion)

    def _consultar_chatgpt(self, peticion: str) -> str:
        """Consultar ChatGPT"""
        try:
            from core.integraciones.chatgpt_api import chatgpt_api

            if chatgpt_api:
                return chatgpt_api.consultar(peticion)
            else:
                return self._respuesta_demo("ChatGPT", peticion)
        except Exception as e:
            logger.error(f"Error consultando ChatGPT: {e}")
            return self._respuesta_demo("ChatGPT", peticion)

    def _respuesta_demo(self, fuente: str, peticion: str) -> str:
        """
        Generar respuesta demo cuando API no está configurada

        Args:
            fuente: Nombre de la fuente
            peticion: Petición

        Returns:
            Respuesta demo
        """
        return f"[DEMO - {fuente} no configurado] Respuesta simulada para: {peticion}"

    def _consultar_con_fallback(self, metodo_consulta, peticion: str) -> str:
        """
        Consultar con fallback automático entre fuentes

        Args:
            metodo_consulta: Método de consulta a intentar
            peticion: Petición

        Returns:
            Respuesta de la primera fuente que funcione
        """
        try:
            # Intentar la fuente principal
            resultado = metodo_consulta(peticion)

            # Si es respuesta demo, intentar otras fuentes
            if "[DEMO" in resultado:
                logger.warning("Fuente principal no disponible, intentando fallback...")

                # Intentar otras fuentes en orden de prioridad
                for otra_fuente in ["Claude", "ChatGPT", "Gemini", "DeepSeek"]:
                    if otra_fuente != metodo_consulta.__name__.replace("_consultar_", ""):
                        try:
                            if otra_fuente == "Claude":
                                resultado_fallback = self._consultar_claude(peticion)
                            elif otra_fuente == "ChatGPT":
                                resultado_fallback = self._consultar_chatgpt(peticion)
                            elif otra_fuente == "Gemini":
                                resultado_fallback = self._consultar_gemini(peticion)
                            elif otra_fuente == "DeepSeek":
                                resultado_fallback = self._consultar_deepseek(peticion)

                            if "[DEMO" not in resultado_fallback:
                                logger.info(f"Fallback exitoso usando {otra_fuente}")
                                return resultado_fallback
                        except Exception:
                            continue

                # Si todas fallan, usar respuesta demo
                return resultado

            return resultado

        except Exception as e:
            logger.error(f"Error en consulta con fallback: {e}")
            return self._respuesta_demo("fallback", peticion)

    def _comparar_respuestas(self, respuesta_ura: str, respuestas_fuentes: list[dict]) -> float:
        """
        Comparar respuesta de URA con fuentes

        Args:
            respuesta_ura: Respuesta de URA
            respuestas_fuentes: Respuestas de fuentes

        Returns:
            Porcentaje de coincidencia (0-1)
        """
        if not respuestas_fuentes:
            return 0.0

        coincidencias = 0
        for rf in respuestas_fuentes:
            # Simular comparación (en producción usaría similitud real)
            if (
                respuesta_ura.lower() in rf["respuesta"].lower()
                or rf["respuesta"].lower() in respuesta_ura.lower()
            ):
                coincidencias += 1

        return coincidencias / len(respuestas_fuentes)

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        if not self.verificaciones:
            return {"total": 0}

        aprobadas = sum(1 for v in self.verificaciones if v["aprobada"])
        rechazadas = len(self.verificaciones) - aprobadas

        return {
            "total": len(self.verificaciones),
            "aprobadas": aprobadas,
            "rechazadas": rechazadas,
            "tasa_aprobacion": aprobadas / len(self.verificaciones),
        }


# Instancia global
tecnico_supervisor = TecnicoSupervisor()


if __name__ == "__main__":
    supervisor = TecnicoSupervisor()

    # Test
    resultado = supervisor.verificar_respuesta(
        respuesta_ura="Bitcoin está a $50,000", peticion="¿Cuál es el precio de Bitcoin?"
    )

    print(f"Aprobada: {resultado['aprobada']}")
    print(f"Coincidencia: {resultado['coincidencia']:.2%}")
    print(f"Estadísticas: {supervisor.get_estadisticas()}")
