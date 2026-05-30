#!/usr/bin/env python3
"""
URA OpenClaw Spy — Espía de conversaciones de OpenClaw para aprendizaje

Este script lee los archivos de historial de sesiones de OpenClaw (~/.openclaw/agents/main/sessions/*.jsonl)
y extrae las interacciones (pregunta, respuesta) para alimentar el sistema de aprendizaje de URA.

Características:
- Solo lectura de archivos de historial (no modifica nada)
- Estado guardado en ~/.ura/openclaw_spy_state.json para evitar duplicados
- Detección de intención por palabras clave (sin embeddings)
- Integración con ObservationalLearner de URA
- Modo --once para ejecución única (apt para cron)
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("openclaw_spy")

# Rutas
OPENCLAW_SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
URA_STATE_FILE = Path.home() / ".ura" / "openclaw_spy_state.json"
URA_LOG_FILE = Path.home() / ".ura" / "openclaw_spy.log"
URA_PID_FILE = Path.home() / ".ura" / "spy.pid"


class OpenClawSpy:
    """Espía de conversaciones de OpenClaw para aprendizaje de URA."""

    def __init__(self, state_file: Path | None = None, log_file: Path | None = None):
        self.state_file = state_file or URA_STATE_FILE
        self.log_file = log_file or URA_LOG_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

        # Configurar logging en archivo
        self._setup_log_file()

        # Cargar ObservationalLearner
        try:
            from core.ura_observational_learner import get_learner

            self.learner = get_learner()
            logger.info("ObservationalLearner cargado correctamente")
        except ImportError as e:
            logger.error("No se pudo importar ObservationalLearner: %s", e)
            self.learner = None

    def _setup_log_file(self) -> None:
        """Configura logging en archivo con timestamp."""
        # Eliminar handlers existentes
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Configurar file handler
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # También mantener console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(file_formatter)
        logger.addHandler(console_handler)

        logger.setLevel(logging.INFO)

    def _load_state(self) -> dict[str, int]:
        """Carga el estado de procesamiento desde archivo."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Error cargando estado: %s", e)
            return {}

    def _save_state(self) -> None:
        """Guarda el estado de procesamiento en archivo."""
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error("Error guardando estado: %s", e)

    def _detect_intent(self, text: str) -> str:
        """
        Detecta la intención del texto usando palabras clave.
        Similar al método _intent_to_domain de ObservationalLearner.
        """
        text_lower = text.lower()

        intent_keywords = {
            "cocina": ["cocina", "receta", "plato", "ingredientes", "cocinar", "comida"],
            "contabilidad": ["contabilidad", "factura", "iva", "impuesto", "contable", "balance"],
            "marketing": ["marketing", "publicidad", "banner", "campaña", "promoción", "anuncio"],
            "leyes": ["ley", "normativa", "reglamento", "legal", "jurídico", "norma"],
            "rrhh": ["recursos humanos", "rrhh", "contrato", "empleado", "salario", "nómina"],
        }

        for intent, keywords in intent_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return intent

        return "general"

    def _extract_interaction(self, line: str) -> dict[str, str] | None:
        """
        Extrae una interacción (query, response) de una línea JSONL.

        Formato esperado de OpenClaw:
        {
            "messages": [
                {"role": "user", "content": "pregunta"},
                {"role": "assistant", "content": "respuesta"}
            ],
            ...
        }
        """
        try:
            data = json.loads(line)
            messages = data.get("messages", [])

            if not messages or len(messages) < 2:
                return None

            # Buscar el último par user-assistant
            query = None
            response = None

            for i in range(len(messages) - 1):
                if messages[i].get("role") == "user" and messages[i + 1].get("role") == "assistant":
                    query = messages[i].get("content", "").strip()
                    response = messages[i + 1].get("content", "").strip()
                    break

            if not query or not response:
                return None

            # Filtrar interacciones muy cortas
            if len(query) < 10 or len(response) < 10:
                return None

            return {
                "query": query,
                "response": response,
                "timestamp": data.get("timestamp", datetime.now().isoformat()),
            }
        except json.JSONDecodeError:
            return None
        except Exception as e:
            logger.debug("Error extrayendo interacción: %s", e)
            return None

    def _process_session_file(self, session_file: Path) -> int:
        """
        Procesa un archivo de sesión de OpenClaw.
        Devuelve el número de nuevas interacciones procesadas.
        """
        if not session_file.exists():
            logger.warning("Archivo de sesión no existe: %s", session_file)
            return 0

        session_key = str(session_file)
        last_processed = self.state.get(session_key, 0)
        new_interactions = 0

        try:
            with open(session_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Procesar líneas nuevas
            for line_num, line in enumerate(lines, start=1):
                if line_num <= last_processed:
                    continue

                interaction = self._extract_interaction(line.strip())
                if interaction:
                    # Detectar intención
                    intent = self._detect_intent(interaction["query"])

                    # Enviar al ObservationalLearner
                    if self.learner:
                        try:
                            asyncio.run(
                                self.learner.learn_from_interaction(
                                    interaction["query"], interaction["response"], intent
                                )
                            )
                            logger.info(
                                "Interacción procesada: %s -> %s (intent: %s)",
                                interaction["query"][:50] + "...",
                                interaction["response"][:50] + "...",
                                intent,
                            )
                            new_interactions += 1
                        except Exception as e:
                            logger.error("Error procesando interacción: %s", e)
                    else:
                        logger.warning(
                            "ObservationalLearner no disponible, interacción no procesada"
                        )

                # Actualizar estado después de cada línea
                self.state[session_key] = line_num
                self._save_state()

        except Exception as e:
            logger.error("Error procesando archivo %s: %s", session_file, e)

        return new_interactions

    def process_all_sessions(self) -> int:
        """
        Procesa todos los archivos de sesión de OpenClaw.
        Devuelve el número total de nuevas interacciones procesadas.
        """
        if not OPENCLAW_SESSIONS_DIR.exists():
            logger.warning(
                "Directorio de sesiones de OpenClaw no existe: %s", OPENCLAW_SESSIONS_DIR
            )
            return 0

        session_files = list(OPENCLAW_SESSIONS_DIR.glob("*.jsonl"))
        logger.info("Encontrados %d archivos de sesión", len(session_files))

        total_new = 0
        for session_file in session_files:
            logger.info("Procesando archivo: %s", session_file.name)
            new_count = self._process_session_file(session_file)
            total_new += new_count
            logger.info("Archivo %s: %d nuevas interacciones", session_file.name, new_count)

        logger.info("Total de nuevas interacciones procesadas: %d", total_new)
        return total_new

    def stats(self) -> dict:
        """Devuelve estadísticas del espía."""
        if not OPENCLAW_SESSIONS_DIR.exists():
            return {"error": "Directorio de sesiones no existe"}

        session_files = list(OPENCLAW_SESSIONS_DIR.glob("*.jsonl"))
        total_lines = 0
        processed_lines = sum(self.state.values())

        for session_file in session_files:
            try:
                with open(session_file, encoding="utf-8") as f:
                    total_lines += len(f.readlines())
            except Exception:
                continue

        return {
            "session_files": len(session_files),
            "total_lines": total_lines,
            "processed_lines": processed_lines,
            "pending_lines": total_lines - processed_lines,
            "state_file": str(self.state_file),
            "log_file": str(self.log_file),
            "learner_available": self.learner is not None,
        }


def _check_pid_file(pid_file: Path) -> bool:
    """Verifica si ya hay un daemon corriendo."""
    if not pid_file.exists():
        return False

    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())

        # Verificar si el proceso está corriendo
        try:
            os.kill(pid, 0)  # Signal 0 solo verifica si el proceso existe
            return True
        except OSError:
            # Proceso no existe, limpiar PID file antiguo
            pid_file.unlink()
            return False
    except (ValueError, OSError):
        # PID file corrupto, limpiar
        pid_file.unlink()
        return False


def _write_pid_file(pid_file: Path) -> None:
    """Escribe el PID del proceso actual en el archivo."""
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))


def _remove_pid_file(pid_file: Path) -> None:
    """Elimina el archivo PID."""
    if pid_file.exists():
        pid_file.unlink()


def _signal_handler(signum, frame):
    """Manejador de señales para limpieza graceful."""
    logger.info("Recibida señal %d, limpiando y saliendo...", signum)
    _remove_pid_file(URA_PID_FILE)
    sys.exit(0)


def main():
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="URA OpenClaw Spy — Espía de conversaciones de OpenClaw para aprendizaje"
    )
    parser.add_argument(
        "--once", action="store_true", help="Ejecutar una vez y salir (apt para cron)"
    )
    parser.add_argument(
        "--daemon", action="store_true", help="Ejecutar en modo daemon (bucle infinito)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Intervalo en segundos para modo daemon (por defecto: 60)",
    )
    parser.add_argument("--stats", action="store_true", help="Mostrar estadísticas y salir")
    parser.add_argument("--state-file", type=str, help="Ruta alternativa al archivo de estado")
    parser.add_argument("--log-file", type=str, help="Ruta alternativa al archivo de log")
    parser.add_argument("--verbose", action="store_true", help="Modo verbose")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    state_file = Path(args.state_file) if args.state_file else None
    log_file = Path(args.log_file) if args.log_file else None
    spy = OpenClawSpy(state_file=state_file, log_file=log_file)

    if args.stats:
        stats = spy.stats()
        print(json.dumps(stats, indent=2))
        return

    if args.daemon:
        # Verificar si ya hay un daemon corriendo
        if _check_pid_file(URA_PID_FILE):
            logger.error("Ya hay un daemon corriendo. PID file: %s", URA_PID_FILE)
            print(f"ERROR: Ya hay un daemon corriendo. PID file: {URA_PID_FILE}")
            sys.exit(1)

        # Escribir PID file
        _write_pid_file(URA_PID_FILE)
        logger.info("Daemon iniciado con PID %d", os.getpid())
        logger.info("Intervalo: %d segundos", args.interval)

        # Configurar manejadores de señales
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        try:
            while True:
                logger.info("Ejecutando ciclo de espionaje...")
                total = spy.process_all_sessions()
                logger.info("Ciclo completado: %d nuevas interacciones", total)
                logger.info("Esperando %d segundos...", args.interval)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Interrumpido por usuario")
        finally:
            _remove_pid_file(URA_PID_FILE)
            logger.info("Daemon detenido")
        return

    if args.once:
        total = spy.process_all_sessions()
        logger.info("Ejecución completada: %d nuevas interacciones", total)
        return

    # Modo interactivo (por defecto)
    logger.info("Modo interactivo no implementado. Usa --once para ejecución única.")
    logger.info("Para ejecución periódica, usa --daemon o cron con --once.")


if __name__ == "__main__":
    main()
