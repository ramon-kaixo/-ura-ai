#!/usr/bin/env python3
"""
Init Utils - Paso 3A
──────────────────────
Utilidades para inicialización de componentes.
"""

import logging

logger = logging.getLogger(__name__)


def _init_config(window):
    """Inicializar configuración."""
    from config.settings_loader import load_config

    window.config = load_config()
    logger.info("Configuración inicializada")


def _init_connectors(window):
    """Inicializar conectores con soporte para Ollama remoto."""
    from connectors.ollama_connector import OllamaConnector

    # Leer configuración de Ollama remoto si existe
    ollama_host = window.config.get("ollama_host", "localhost")
    ollama_port = window.config.get("ollama_port", 11434)

    # Verificar si está configurado para usar Ollama remoto
    use_remote = window.config.get("ollama_use_remote", False)
    if use_remote:
        remote_host = window.config.get("ollama_remote_host", "")
        remote_port = window.config.get("ollama_remote_port", 11434)
        if remote_host:
            ollama_host = remote_host
            ollama_port = remote_port
            logger.info(f"Usando Ollama remoto: {ollama_host}:{ollama_port}")

    window.ollama_connector = OllamaConnector(
        host=ollama_host,
        port=ollama_port,
    )
    logger.info("Conectores inicializados")


def _init_memory(window):
    """Inicializar memoria."""
    from core.memory_manager import MemoryManager

    memory_dir = window.config.get("memory_dir", "memory")
    window.memory_manager = MemoryManager(memory_dir)
    logger.info("Memoria inicializada")


def _init_security(window):
    """Inicializar seguridad."""
    import threading
    import time
    import config

    window.network_audit = (
        NetworkAuditSystem(use_localhost=True) if config.network_audit_available else None
    )
    if window.network_audit:
        try:
            window.network_audit.run_full_audit()
            logger.info("Auditoría de red completada al inicio")
        except Exception as e:
            logger.error(f"Error ejecutando auditoría de red: {e}")

    window.thread_cleaner = ThreadCleaner() if config.thread_cleaner_available else None

    from core.autonomous_maintenance import AutonomousMaintenance

    window._autonomous_maintenance = AutonomousMaintenance()
    window._autonomous_maintenance.iniciar()

    # Disk monitor: bucle de background cada 5 minutos. daemon=True para
    # que muera con la app y no impida el cierre limpio.
    try:
        from core.disk_monitor import bucle as disk_monitor_bucle

        window._disk_monitor_thread = threading.Thread(
            target=disk_monitor_bucle,
            args=(300,),  # cada 5 minutos
            daemon=True,  # muere con la app
            name="DiskMonitorThread",
        )
        window._disk_monitor_thread.start()
        logger.info("DiskMonitorThread iniciado (intervalo: 300s)")
    except Exception as e:
        logger.error(f"Error iniciando DiskMonitorThread: {e}")

    # Cloud backup: bucle de backup nocturno cada 24h. daemon=True para
    # que muera con la app sin impedir el cierre limpio.
    try:
        from core.cloud_backup import hacer_backup

        def _backup_loop():
            while True:
                time.sleep(86400)  # cada 24 horas
                try:
                    hacer_backup()
                except Exception as exc:
                    logger.error(f"Error en backup nocturno: {exc}")

        window._backup_thread = threading.Thread(
            target=_backup_loop,
            daemon=True,
            name="CloudBackupThread",
        )
        window._backup_thread.start()
        logger.info("CloudBackupThread iniciado (intervalo: 24h)")
    except Exception as e:
        logger.error(f"Error iniciando CloudBackupThread: {e}")


def _init_threads(window):
    """Inicializar hilos."""
    window.voice_recognizer = None
    window.tts_engine = None
    window.continuous_conversation = None

    if get_telegram_bridge is not None:
        try:
            window.telegram_bridge = get_telegram_bridge()
            logger.info("Telegram bridge inicializado")
        except Exception as e:
            logger.error(f"Error inicializando Telegram bridge: {e}")
            window.telegram_bridge = None
    else:
        logger.warning("get_telegram_bridge no disponible - Telegram bridge no inicializado")
        window.telegram_bridge = None
    window.active_streaming_threads = []
    window.active_windsurf_threads = []
    window.voice_recognizer = None
    window.tts_engine = None


def _init_ui(window):
    """Inicializar UI."""
    window.setup_window()
    window.setup_optimized_ui()


def _init_voice(window):
    """Inicializar voz."""
    window.initialize_voice_components()
