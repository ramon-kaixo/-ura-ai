#!/usr/bin/env python3
"""
Threads de URA — extraídos de main_final.py (FASE 1).
Todos los QThreads en un solo módulo para reducir el monolito.
"""

import logging
import os
import time
from pathlib import Path

from PyQt5.QtCore import QThread, QTimer, pyqtSignal

from core.ura_config import config

logger = logging.getLogger(__name__)

# ── Dependencias de voz ───────────────────────────────────
try:
    import speech_recognition as sr

    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None

try:
    import pyttsx3

    TTS_ENGINE = pyttsx3.init()
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    TTS_ENGINE = None

try:
    from gtts import gTTS

    try:
        from playsound3 import playsound
    except ImportError:
        from playsound import playsound
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# ── Dependencias de Ollama ────────────────────────────────
OLLAMA_AVAILABLE = False
try:
    pass

    OLLAMA_AVAILABLE = True
except ImportError:
    pass

# ── Dependencias de búsqueda ──────────────────────────────
try:
    from core.web_search import search_and_summarize

    config.web_search_available = True
except ImportError:
    search_and_summarize = None
    config.web_search_available = False

# ── Dependencias de visión ────────────────────────────────
try:
    from core.vision import look_at_screen

    config.vision_available = True
except ImportError:
    look_at_screen = None
    config.vision_available = False

# ── Dependencias de recuperación ──────────────────────────
try:
    from core.smart_recovery import SmartRecovery, RecoveryReport

    config.smart_recovery_available = True
except ImportError:
    SmartRecovery = None
    RecoveryReport = None
    config.smart_recovery_available = False

# ── Memoria ───────────────────────────────────────────────
try:
    from core.semantic_memory import get_memory

    config.ura_memory_available = True
except ImportError:
    get_memory = None
    config.ura_memory_available = False

# ── Seguridad ─────────────────────────────────────────────
try:
    from security_policy import require_authorization as _req
except ImportError:
    _req = None


# TODO: web_search module missing - search_and_summarize and is_search_command not found in project
# This thread depends on missing web_search module. Extract when module is available.
class _WebSearchThread(QThread):
    """Búsqueda web + resumen en segundo plano para no bloquear la UI."""

    search_ready = pyqtSignal(dict)
    search_failed = pyqtSignal(str)

    def __init__(self, query_or_command: str, parent=None):
        super().__init__(parent)
        self._q = query_or_command

    def run(self):
        try:
            if not config.web_search_available or search_and_summarize is None:
                self.search_failed.emit("Módulo de búsqueda web no disponible.")
                return
            out = search_and_summarize(self._q)
            self.search_ready.emit(out)
        except Exception as exc:
            logger.exception("Web search thread falló")
            self.search_failed.emit(str(exc))


# TODO: módulo faltante — extraer cuando se implemente vision.py (look_at_screen function missing)
class _VisionThread(QThread):
    """Captura la pantalla y llama a llava (Ollama) sin bloquear la UI."""

    vision_ready = pyqtSignal(str, str)  # (image_path, description)
    vision_failed = pyqtSignal(str)

    def __init__(self, prompt=None, parent=None):
        super().__init__(parent)
        self._prompt = prompt

    def run(self):
        try:
            if not config.vision_available or look_at_screen is None:
                self.vision_failed.emit(
                    "Módulo de visión no disponible (instala pyautogui y Pillow)."
                )
                return
            result = look_at_screen(prompt=self._prompt)
            self.vision_ready.emit(result.get("image", ""), result.get("description", ""))
        except Exception as exc:
            logger.exception("Vision thread falló")
            self.vision_failed.emit(str(exc))


class _CleanSafeListThread(QThread):
    """Genera lista_limpieza.txt en background (escanea el disco sin bloquear la UI)."""

    list_ready = pyqtSignal(str, str)  # (path, contenido)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        import subprocess

        try:
            script = Path(__file__).parent / "tools" / "generar_lista_limpieza.sh"
            list_path = Path(__file__).parent / "lista_limpieza.txt"
            subprocess.run(
                ["bash", str(script)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if not list_path.exists():
                self.failed.emit("lista_limpieza.txt no generada")
                return
            contenido = list_path.read_text(encoding="utf-8", errors="replace")
            self.list_ready.emit(str(list_path), contenido)
        except Exception as exc:
            self.failed.emit(str(exc))


class _CleanSafeAuthThread(QThread):
    """Pide Face ID + ejecuta el borrado real sin bloquear la UI."""

    finished_auth = pyqtSignal(bool, int, int)  # (authorized, borrados, errores)

    def __init__(self, list_path: Path, contenido: str, parent=None):
        super().__init__(parent)
        self._list_path = list_path
        self._contenido = contenido

    def run(self):
        import shutil

        authorized = False
        borrados, errores = 0, 0
        try:
            from security_policy import require_authorization as _req

            authorized = bool(
                _req(
                    action_name="Limpieza Segura",
                    payload={"lista": str(self._list_path)},
                    reason="URA: confirma la eliminación de los 'restos de obra' listados",
                )
            )
        except Exception as exc:
            logger.exception("Limpieza Segura: error en require_authorization: %s", exc)
            authorized = False

        if authorized:
            for linea in self._contenido.splitlines():
                p = linea.strip()
                if not p or p.startswith("#"):
                    continue
                ruta = Path(p)
                if not ruta.exists():
                    continue
                try:
                    if ruta.is_dir():
                        shutil.rmtree(ruta, ignore_errors=False)
                    else:
                        ruta.unlink()
                    borrados += 1
                except Exception:
                    errores += 1
        self.finished_auth.emit(authorized, borrados, errores)


# TODO: módulos faltantes — extraer cuando se implementen SmartRecovery y RecoveryReport classes
class _SmartRecoveryThread(QThread):
    """Ejecuta SmartRecovery en segundo plano para no bloquear la UI."""

    finished_report = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            if config.smart_recovery_available and SmartRecovery is not None:
                report = SmartRecovery().run()
            else:
                report = None
        except Exception as exc:
            logger.exception("Smart Recovery falló")
            report = RecoveryReport() if RecoveryReport else None
            if report is not None:
                report.errors.append(f"Excepción fatal: {exc}")
        self.finished_report.emit(report)


class VoiceRecognitionThread(QThread):
    """Thread para reconocimiento de voz"""

    recognized_text = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.recognizer = sr.Recognizer() if SPEECH_RECOGNITION_AVAILABLE else None
        self.microphone = None
        self.is_listening = False
        self._stop_requested = False

        if SPEECH_RECOGNITION_AVAILABLE:
            try:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
            except Exception as e:
                logger.error(f"Error inicializando micrófono: {e}")

    def start_listening(self):
        """Iniciar escucha de voz"""
        if not self.is_listening and self.microphone:
            self.is_listening = True
            self._stop_requested = False
            self.start()

    def stop_listening(self):
        """Detener escucha de voz"""
        self.is_listening = False

    def stop(self):
        """Solicitar parada del thread"""
        self._stop_requested = True
        self.is_listening = False

    def run(self):
        """Ejecutar reconocimiento de voz"""
        if not self.recognizer or not self.microphone:
            self.error_occurred.emit("Reconocimiento de voz no disponible")
            return

        try:
            with self.microphone as source:
                self.recognized_text.emit("Escuchando...")
                audio = self.recognizer.listen(source, timeout=15, phrase_time_limit=15)

            # Intentar reconocer con Google (requiere internet)
            try:
                text = self.recognizer.google(audio, language="es-ES")
                self.recognized_text.emit(text)
            except sr.UnknownValueError:
                self.error_occurred.emit("No se pudo entender el audio")
            except sr.RequestError as e:
                # Fallback a reconocimiento offline si falla Google
                try:
                    text = self.recognizer.sphinx(audio, language="es")
                    self.recognized_text.emit(text)
                except:
                    self.error_occurred.emit(f"Error de reconocimiento: {e}")

        except sr.WaitTimeoutError:
            self.error_occurred.emit("Tiempo de espera agotado")
        except Exception as e:
            self.error_occurred.emit(f"Error en reconocimiento: {e}")


class TextToSpeechThread(QThread):
    """Thread para síntesis de voz"""

    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.text_to_speak = ""
        self.use_gtts = GTTS_AVAILABLE and not TTS_AVAILABLE
        self._stop_requested = False

    def speak(self, text):
        """Hablar texto"""
        self.text_to_speak = text
        self._stop_requested = False
        if not self.isRunning():
            self.start()

    def stop(self):
        """Solicitar parada del thread"""
        self._stop_requested = True
        self.text_to_speak = ""

    def run(self):
        """Ejecutar síntesis de voz"""
        if not self.text_to_speak:
            return

        if self._stop_requested:
            return

        try:
            self.speaking_started.emit()

            if self.use_gtts and GTTS_AVAILABLE:
                # Usar gTTS
                tts = gTTS(text=self.text_to_speak, lang="es")
                temp_file = "temp_speech.mp3"
                tts.save(temp_file)
                if not self._stop_requested:
                    playsound(temp_file)
                os.remove(temp_file)
            elif TTS_AVAILABLE:
                # Usar pyttsx3
                TTS_ENGINE.say(self.text_to_speak)
                if not self._stop_requested:
                    TTS_ENGINE.runAndWait()
            else:
                self.error_occurred.emit("Síntesis de voz no disponible")

        except Exception as e:
            self.error_occurred.emit(f"Error en síntesis de voz: {e}")
        finally:
            self.speaking_finished.emit()


class ContinuousVoiceConversationThread(QThread):
    """Thread para conversación continua por voz"""

    user_speaking = pyqtSignal(str)
    ura_responding = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self, workflow):
        super().__init__()
        self.workflow = workflow
        self.is_running = False
        self.voice_recognizer = VoiceRecognitionThread()
        self.tts_engine = TextToSpeechThread()

        # Conectar señales
        self.voice_recognizer.recognized_text.connect(self.on_user_text)
        self.voice_recognizer.error_occurred.connect(self.error_occurred)

    def start_conversation(self):
        """Iniciar conversación continua"""
        self.is_running = True
        self.status_changed.emit("Conversación activa - Habla cuando quieras")
        self.start()

    def stop_conversation(self):
        """Detener conversación continua"""
        self.is_running = False
        self.voice_recognizer.stop_listening()
        self.status_changed.emit("Conversación detenida")

    def on_user_text(self, text):
        """Manejar texto reconocido del usuario"""
        if not self.is_running or text == "Escuchando...":
            return

        self.user_speaking.emit(text)

        # Procesar con URA
        try:
            response = self.workflow.process(text)
            self.ura_responding.emit(response)

            # Hablar respuesta
            self.tts_engine.speak(response)

            # Pequeña pausa antes de volver a escuchar
            time.sleep(1)

            # Volver a escuchar si sigue activo
            if self.is_running:
                QTimer.singleShot(1000, self.voice_recognizer.start_listening)

        except Exception as e:
            self.error_occurred.emit(f"Error procesando: {e}")

    def run(self):
        """Ejecutar conversación continua"""
        if self.is_running:
            self.voice_recognizer.start_listening()


# UI Widgets - importados desde ui.widgets

# Command Detectors - importados desde core.command_detector


class MessageProcessorThread(QThread):
    """Thread mejorado para procesar mensajes con reintentos automáticos"""

    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, workflow, message):
        super().__init__()
        self.workflow = workflow
        self.message = message
        self.max_retries = 3
        self.retry_delay = 2

    def run(self):
        for attempt in range(self.max_retries):
            try:
                response = self.workflow.process(self.message)
                self.response_ready.emit(response)
                return
            except Exception as e:
                logger.error(f"Error procesando mensaje (intento {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    self.error_occurred.emit(
                        f"Error procesando mensaje después de {self.max_retries} intentos: {e}"
                    )


class StreamingMessageProcessorThread(QThread):
    """Thread para procesar mensajes con streaming (respuesta palabra por palabra)"""

    chunk_ready = pyqtSignal(str)  # Emite cada chunk/token
    response_complete = pyqtSignal(str)  # Emite respuesta completa
    error_occurred = pyqtSignal(str)

    def __init__(
        self, ollama_connector, message, model="qwen2.5:3b-instruct", semantic_context="", system=""
    ):
        super().__init__()
        self.ollama_connector = ollama_connector
        self.message = message
        self.model = model
        self.semantic_context = semantic_context
        self.system = system
        self.max_retries = 3
        self.retry_delay = 2
        self._stop_requested = False
        # Usar system prompt dinámico si se proporciona, sino usar el hardcodeado
        if system:
            self.full_prompt = f"{system}\n\nRamón: {message}\nURA:"
        else:
            # Inyectar el ADN de URA + memoria reciente como prompt permanente
            try:
                parts = []
                # Prompt simple en español para permitir respuestas naturales
                parts.append(
                    "Eres URA, un asistente inteligente en español. Puedes responder preguntas sobre cocina, programación, finanzas, arte, viajes y cualquier otro tema. RESPIRE SIEMPRE Y EXCLUSIVAMENTE EN ESPAÑOL. NUNCA responda en portugués, chino, inglés o ningún otro idioma. Nunca digas 'No tengo acceso'."
                )
                # Memoria dinámica: SOLO para coordinación interna con agentes, no afecta respuestas al usuario
                if config.ura_memory_available and get_memory is not None:
                    ctx = get_memory().render(model=self.model)
                    if ctx:
                        parts.append(f"<!-- COORDINACIÓN INTERNA AGENTES -->\n{ctx}")
                # Añadir contexto semántico si está disponible: SOLO para coordinación interna
                if self.semantic_context:
                    parts.append(
                        f"<!-- CONTEXTO SEMÁNTICO INTERNO -->\nContexto relevante: {self.semantic_context}"
                    )
                parts.append(f"Ramón: {message}\nURA:")
                self.full_prompt = "\n\n---\n".join(parts) if len(parts) > 1 else message
            except Exception:
                self.full_prompt = message

    def stop(self):
        """Solicitar parada del thread"""
        self._stop_requested = True

    def run(self):
        for attempt in range(self.max_retries):
            try:
                full_response = ""

                def chunk_callback(chunk):
                    nonlocal full_response
                    full_response += chunk
                    self.chunk_ready.emit(chunk)

                # Usar generate_stream para streaming (ROLLBACK TEMPORAL para diagnóstico)
                response = self.ollama_connector.generate_stream(
                    self.full_prompt,
                    model=self.model,
                    chunk_callback=chunk_callback,
                    options={"max_tokens": 3000},
                    use_system_prompt=False,
                )

                self.response_complete.emit(response)
                return

            except Exception as e:
                logger.error(f"Error procesando mensaje con streaming (intento {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    self.error_occurred.emit(
                        f"Error procesando mensaje después de {self.max_retries} intentos: {e}"
                    )


class OllamaConnectionChecker(QThread):
    """Thread dedicado a verificar y reintentar conexión con Ollama"""

    connection_status = pyqtSignal(bool)
    error_message = pyqtSignal(str)
    ollama_dropped = pyqtSignal()
    ollama_recovered = pyqtSignal()

    def __init__(self, ollama_connector):
        super().__init__()
        self.ollama_connector = ollama_connector
        if OLLAMA_AVAILABLE and ollama_connector is not None:
            logger.info("OllamaConnectionChecker usando conector existente")
        else:
            logger.warning("OllamaConnectionChecker: OLLAMA_AVAILABLE=False o conector es None")

        self.running = True
        self.last_connected = True  # Estado anterior para detectar caídas
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3
        self.degraded_mode = False

    def run(self):
        while self.running:
            try:
                # Usar el conector real sin prueba de modelo (solo verificar que el servicio responde)
                connected = self.ollama_connector.test_connection(test_model=False)
                self.connection_status.emit(connected)

                if not connected:
                    if self.last_connected:
                        # Ollama acaba de caerse
                        self.ollama_dropped.emit()
                        logger.warning("Ollama se ha caído - intentando relanzar...")

                    # Verificar límite de reintentos con backoff
                    if self.recovery_attempts < self.max_recovery_attempts:
                        # Intentar relanzar Ollama con backoff exponencial
                        backoff_delay = min(2**self.recovery_attempts, 10)  # Max 10 segundos
                        logger.info(
                            f"Intento de recuperación {self.recovery_attempts + 1}/{self.max_recovery_attempts}, esperando {backoff_delay}s..."
                        )
                        time.sleep(backoff_delay)
                        self._restart_ollama()
                        self.error_message.emit(
                            f"Ollama no responde - reintento {self.recovery_attempts + 1}/{self.max_recovery_attempts}..."
                        )
                        self.last_connected = False
                        self.recovery_attempts += 1
                    else:
                        # Pasar a modo degradado después de 3 reintentos
                        if not self.degraded_mode:
                            self.degraded_mode = True
                            logger.error(
                                "⚠️ Ollama no disponible tras 3 reintentos - entrando en modo degradado (solo lectura)"
                            )
                            self.error_message.emit(
                                "⚠️ Ollama no disponible - modo degradado (solo lectura)"
                            )
                            self.last_connected = False
                else:
                    if not self.last_connected:
                        # Ollama se ha recuperado
                        self.ollama_recovered.emit()
                        logger.info(
                            f"Ollama recuperado después de {self.recovery_attempts} intentos"
                        )
                        self.recovery_attempts = 0
                    self.last_connected = True

            except Exception as e:
                if self.last_connected:
                    self.ollama_dropped.emit()
                self.connection_status.emit(False)
                self.error_message.emit(f"Error conectando con Ollama: {e}")
                self.last_connected = False

            # Esperar 5 segundos antes del siguiente intento
            for _ in range(50):
                if not self.running:
                    return
                time.sleep(0.1)

    def _restart_ollama(self):
        """Relanzar Ollama automáticamente"""
        try:
            import subprocess

            logger.info("Relanzando Ollama...")
            # Relanzar Ollama en background
            subprocess.Popen(
                ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            # Esperar a que arranque
            time.sleep(3)
        except Exception as e:
            logger.error(f"Error relanzando Ollama: {e}")

    def stop(self):
        self.running = False
