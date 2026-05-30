#!/usr/bin/env python3
"""
Imports and Initialization - Paso 3A
────────────────────────────────────
Imports y configuración inicial de la aplicación.
"""

import logging
import sys
from pathlib import Path


# Agregar rutas de módulos
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

# Importar configuración centralizada
from core.ura_config import config

# Importar Sistema de Auditoría de Red
try:
    pass

    config.network_audit_available = True
except ImportError as e:
    print(f"Advertencia: No se pudo importar NetworkAuditSystem: {e}")
    config.network_audit_available = False

# Importar Limpiador de Hilos
try:
    pass

    config.thread_cleaner_available = True
except ImportError as e:
    print(f"Advertencia: No se pudo importar ThreadCleaner: {e}")
    config.thread_cleaner_available = False

# Variables de disponibilidad ahora en config.ura_config

# Importar ReAct Engine
try:
    from core.react_engine import ReActEngine, get_react_engine

    REACT_ENGINE_AVAILABLE = True
except ImportError:
    REACT_ENGINE_AVAILABLE = False
    ReActEngine = None
    get_react_engine = None

# Importar Telegram Security Bridge
try:
    from core.telegram_security_bridge import get_telegram_bridge
except ImportError:
    get_telegram_bridge = None

# PyQt5 imports

# Validación de seguridad al inicio
from core.validators import validate_security_setup

# Ejecutar validación de seguridad
security_warnings = validate_security_setup()
if security_warnings:
    for warning in security_warnings:
        print(f"⚠️ {warning}")

# Función de ejecución segura con fallback

# Verificación de dependencias al arrancar - importada desde core.validators
from core.validators import check_dependencies

deps_ok, missing_deps = check_dependencies()
if not deps_ok:
    print(f"⚠️ Faltan dependencias: {', '.join(missing_deps)}")
    print(f"Instala con: pip install {' '.join(missing_deps)}")

# Sanitización de entrada - importada desde core.utils

# Límite de memoria y CPU
try:
    import resource

    # Obtener límite actual
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    # Limitar memoria a 4GB (solo si el límite actual lo permite)
    if hard >= 4 * 1024 * 1024 * 1024:
        resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 * 1024 * 1024, hard))
        print("✅ Límite de memoria establecido a 4GB")
    else:
        print(
            f"⚠️  Límite máximo del sistema es {hard // (1024**3)}GB, no se puede establecer a 4GB"
        )
except (ImportError, ValueError) as e:
    print(f"⚠️  No se pudo establecer límite de memoria: {e}")

# Visor web (QWebEngineView) - opcional
try:
    pass

    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

# Control de ratón y teclado
try:
    import pyautogui

    pyautogui.PAUSE = 0.1
    pyautogui.FAILSAFE = True
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    pyautogui = None

# Voz
try:
    import speech_recognition as sr

    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None

# TTS
try:
    import pyttsx3

    TTS_ENGINE = pyttsx3.init()
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    TTS_ENGINE = None

try:
    pass

    try:
        from playsound3 import playsound  # fork compatible con Python 3.12+
    except ImportError:
        from playsound import playsound  # fallback al original si existe
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# Ollama Connector
OLLAMA_AVAILABLE = False
ollama_connector = None

try:
    from connectors.ollama_connector import OllamaConnector

    ollama_connector = OllamaConnector()

    OLLAMA_AVAILABLE = True
    print("✅ Ollama importado correctamente")
except ImportError as e:
    print(f"⚠️ No se pudo importar ollama: {e}")
    from core.fallbacks import MockOllamaConnector

    ollama_connector = MockOllamaConnector()

# Workflow Engine
try:
    pass
except ImportError:
    pass

# Circuit Breaker
try:
    from core.circuit_breaker import CircuitBreaker, circuit_breaker_decorator

    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False
    CircuitBreaker = None
    circuit_breaker_decorator = None

# Semantic Search
try:
    pass

    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError:
    SEMANTIC_SEARCH_AVAILABLE = False
    semantic_search_engine = None

# Semantic Memory
try:
    from core.semantic_memory import semantic_memory_manager

    SEMANTIC_MEMORY_AVAILABLE = True
except ImportError:
    SEMANTIC_MEMORY_AVAILABLE = False
    semantic_memory_manager = None

# Configuración logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ura_app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Ruta raíz de la app (usada por Smart Recovery y otros módulos)
APP_PATH = Path(__file__).parent.parent

# Threads
try:
    from services.threads import (
        _WebSearchThread,
        _VisionThread,
        _CleanSafeListThread,
        _CleanSafeAuthThread,
        _SmartRecoveryThread,
        VoiceRecognitionThread,
        TextToSpeechThread,
        ContinuousVoiceConversationThread,
        MessageProcessorThread,
        StreamingMessageProcessorThread,
        OllamaConnectionChecker,
        logger as threads_logger,
    )
except ImportError:
    _WebSearchThread = None
    _VisionThread = None
    _CleanSafeListThread = None
    _CleanSafeAuthThread = None
    _SmartRecoveryThread = None
    VoiceRecognitionThread = None
    TextToSpeechThread = None
    ContinuousVoiceConversationThread = None
    MessageProcessorThread = None
    StreamingMessageProcessorThread = None
    OllamaConnectionChecker = None
    threads_logger = None

# Windsurf Thread
try:
    from core.threads.windsurf_simulator_thread import WindsurfThread
except ImportError:
    WindsurfThread = None

# UI Widgets
try:
    from ui.widgets import StatusIndicator, CompactVoiceButton
except ImportError:
    StatusIndicator = None
    CompactVoiceButton = None

# Command Detectors
try:
    from core.command_detector import (
        is_app_command,
        is_install_command,
        is_manual_command,
        is_screen_area_command,
        is_visual_automation_command,
        is_windsurf_command,
    )
except ImportError:
    is_app_command = None
    is_install_command = None
    is_manual_command = None
    is_screen_area_command = None
    is_visual_automation_command = None
    is_windsurf_command = None


# Monitorización en segundo plano
def health_monitor():
    """Monitor de salud en segundo plano"""
    import time as time_module

    while True:
        try:
            time_module.sleep(60)  # Chequear cada minuto

            # Verificar Ollama
            if OLLAMA_AVAILABLE and "ollama_connector" in globals():
                try:
                    if not ollama_connector.test_connection(test_model=False):
                        logger.warning("Ollama caído, intentando reconectar...")
                        ollama_connector.test_connection(test_model=False)
                except Exception as e:
                    logger.error(f"Error verificando Ollama: {e}")

            # Verificar memoria semántica
            if SEMANTIC_MEMORY_AVAILABLE and "semantic_memory_manager" in globals():
                try:
                    # Solo loggear si está disponible
                    logger.debug("Memoria semántica activa")
                except Exception as e:
                    logger.error(f"Error verificando memoria semántica: {e}")

        except Exception as e:
            logger.error(f"Error en monitor de salud: {e}")
            time_module.sleep(60)  # Esperar antes de reintentar
