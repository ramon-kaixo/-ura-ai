#!/usr/bin/env python3
"""Agente de voz con bucle cognitivo — escucha, planifica, verifica."""

import logging
import time

import speech_recognition as sr
import pyttsx3

from core.memory.semantic_brain import SemanticBrain
from core.vision.state_verifier import StateVerifier
from core.planner_react import ReActPlanner

logger = logging.getLogger("AgenteVoz")


class AgenteVoz:
    """Agente principal con voz, contexto y ejecucion cognitiva."""

    def __init__(self) -> None:
        self.brain = SemanticBrain()
        self.verifier = StateVerifier()
        self.planner = ReActPlanner(laia_agent=self)
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

    def escuchar(self) -> str | None:
        """Escucha el microfono y transcribe a texto.

        Returns:
            Texto transcrito o None si fallo.
        """
        with self.microphone as source:
            logger.info("Escuchando...")
            audio = self.recognizer.listen(source)
        try:
            texto = self.recognizer.recognize_google(audio, language="es-ES")
            logger.info("Tú: %s", texto)
            return texto
        except Exception as exc:
            logger.warning("Error reconociendo voz: %s", exc)
            return None

    def hablar(self, texto: str) -> None:
        """Sintetiza voz a partir de texto.

        Args:
            texto: Texto a hablar.
        """
        logger.info("URA: %s", texto)
        self.engine.say(texto)
        self.engine.runAndWait()

    def procesar_comando(self, comando: str) -> bool:
        """Procesa un comando de voz con memoria y planificacion.

        Args:
            comando: Texto del comando.

        Returns:
            True si la accion se completo con exito.
        """
        contexto = self.brain.buscar_instrucciones(comando, app_name="TPV")
        plan = self.planner.ejecutar_objetivo(comando, contexto)
        exito = self.verifier.verificar_cambio_esperado(plan)
        if not exito:
            self.hablar("Parece que algo fallo. Usare el sandbox para repararlo.")
        else:
            self.hablar("Accion completada con exito.")
        return exito

    def bucle(self) -> None:
        """Bucle principal de escucha y procesamiento."""
        self.hablar("Hola, soy URA. En que puedo ayudarte?")
        while True:
            comando = self.escuchar()
            if comando and "ura" in comando.lower():
                self.procesar_comando(comando)
            time.sleep(0.5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agente = AgenteVoz()
    agente.bucle()
