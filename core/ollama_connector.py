#!/usr/bin/env python3

"""
URA Ollama Connector
Conexión y gestión de Ollama — host/puerto configurables vía OLLAMA_HOST o config_manager.
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Configuración de Ollama con fallback para GX10
OLLAMA_PRIMARY = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_FALLBACK = "http://localhost:11434"

# Importar configuracin centralizada de modelo
from core.model_config import get_active_model

# Módulos de seguridad (Paso 2B)
from core.security.input_sanitizer import sanitize_user_input
from core.security.jailbreak_guard import detect_jailbreak_attempt

# Importar caché Redis si está disponible
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class SystemPromptLoader:
    """Cargador de System Prompts por Departamento"""

    def __init__(self, config_path: Path | None = None):
        """
        Inicializar cargador de system prompts

        Args:
            config_path: Ruta al archivo department_profiles.json
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "department_profiles.json"

        self.config_path = config_path
        self.profiles = self.load_profiles()
        self.model_mapping = self.profiles.get("model_mapping", {})

    def load_profiles(self) -> dict:
        """Cargar perfiles de departamento desde JSON"""
        try:
            if self.config_path.exists():
                with open(self.config_path, encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(
                    f"Perfiles de departamento cargados: {len(data.get('departments', {}))} departamentos"
                )
                return data
            else:
                logger.warning(f"Archivo de perfiles no encontrado: {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"Error cargando perfiles de departamento: {e}")
            return {}

    def get_system_prompt(self, model_name: str) -> str:
        """
        Obtener system prompt para un modelo especfico

        Args:
            model_name: Nombre del modelo (ej: "qwen2.5:7b-instruct", "gestion:latest")

        Returns:
            str: System prompt completo con identidad, autorizacin y protocolo
        """
        # Buscar departamento en mapeo de modelos
        department = self.model_mapping.get(model_name)

        if not department:
            # Si no est en mapeo, intentar inferir del nombre del modelo
            for dept_key in self.profiles.get("departments", {}):
                if dept_key in model_name.lower():
                    department = dept_key
                    break

        if not department:
            logger.warning(f"No se encontr departamento para modelo {model_name}, usando default")
            department = "gestion"  # Default

        dept_profile = self.profiles.get("departments", {}).get(department, {})

        if not dept_profile:
            logger.warning(f"No se encontr perfil para departamento {department}, usando default")
            dept_profile = self.profiles.get("departments", {}).get("gestion", {})

        # Construir system prompt con estructura obligatoria
        identity = dept_profile.get("identity", "Eres URA, asistente.")
        tool_authorization = dept_profile.get(
            "tool_authorization", "Tienes acceso a las herramientas de URA."
        )
        action_protocol = dept_profile.get(
            "action_protocol", "Ejecuta las operaciones directamente."
        )

        system_prompt = f"""{identity}

{tool_authorization}

{action_protocol}

NO respondas con frases de "como modelo de lenguaje" o "no puedo" cuando tengas la capacidad de ejecutar la operacin.
"""

        logger.info(f"System prompt generado para {model_name} (departamento: {department})")
        return system_prompt

    def get_department(self, model_name: str) -> str | None:
        """
        Obtener departamento de un modelo

        Args:
            model_name: Nombre del modelo

        Returns:
            str: Nombre del departamento o None
        """
        return self.model_mapping.get(model_name)


class OllamaConnector:
    """Conector para Ollama con reconexin automtica"""

    def __init__(self, host: str | None = None, port: int | None = None, default_model=None):
        # Si no se especifica modelo, usar configuracin centralizada
        if default_model is None:
            default_model = get_active_model()

        # Usar OLLAMA_PRIMARY con fallback a OLLAMA_FALLBACK
        _host, _port = "localhost", 11434
        if host is None or port is None:
            try:
                from urllib.parse import urlparse

                # Intentar OLLAMA_PRIMARY primero
                parsed_primary = urlparse(OLLAMA_PRIMARY)
                _host = parsed_primary.hostname or "localhost"
                _port = parsed_primary.port or 11434

                # Test rápido con timeout < 3s
                try:
                    requests.get(f"{OLLAMA_PRIMARY}/api/tags", timeout=2)
                    logger.info(f"Usando OLLAMA_PRIMARY: {OLLAMA_PRIMARY}")
                except Exception:
                    # Fallback a OLLAMA_FALLBACK
                    parsed_fallback = urlparse(OLLAMA_FALLBACK)
                    _host = parsed_fallback.hostname or "localhost"
                    _port = parsed_fallback.port or 11434
                    logger.warning(f"OLLAMA_PRIMARY falló, usando fallback: {OLLAMA_FALLBACK}")
            except Exception:
                pass
        else:
            _host = host
            _port = port

        self.host = _host
        self.port = _port
        self.default_model = default_model
        self.current_model = default_model
        self.is_connected = False
        self.connection_callbacks = []
        self.monitoring_thread = None
        self.should_monitor = True
        self.timeout = 30

        # Inicializar caché Redis
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
                self.redis_client.ping()
                logger.info("Caché Redis conectado")
            except Exception as e:
                logger.warning(f"Redis no disponible: {e}")
                self.redis_client = None

        # Inicializar cargador de system prompts
        self.system_prompt_loader = SystemPromptLoader()

    def add_connection_callback(self, callback: Callable[[bool], None]):
        """Aadir callback para cambios de conexin"""
        self.connection_callbacks.append(callback)

    def remove_connection_callback(self, callback: Callable[[bool], None]):
        """Remover callback de conexin"""
        if callback in self.connection_callbacks:
            self.connection_callbacks.remove(callback)

    def _notify_connection_change(self, connected: bool):
        """Notificar cambios de conexin"""
        for callback in self.connection_callbacks:
            try:
                callback(connected)
            except Exception as e:
                logger.error(f"Error en callback de conexin: {e}")

    def test_connection(self, test_model: bool = False) -> bool:
        """Probar conexin con Ollama y verificar modelo funciona"""
        try:
            # Primero verificar que el servicio responde
            url = f"http://{self.host}:{self.port}/api/tags"
            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                if self.is_connected:
                    self.is_connected = False
                    self._notify_connection_change(False)
                    logger.warning(f"Ollama responde con error: {response.status_code}")
                return False

            # Verificar que el modelo est disponible (opcional)
            if test_model:
                models = self.get_models()
                if self.default_model not in models:
                    logger.warning(
                        f"Modelo {self.default_model} no disponible. Modelos disponibles: {models}"
                    )
                    # No desconectar si el modelo no existe, solo advertir
                    # Intentar usar el primer modelo disponible
                    if models:
                        self.default_model = models[0]
                        self.current_model = models[0]
                        logger.info(f"Cambiando a modelo disponible: {self.default_model}")

                # Probar generacin real con mensaje de prueba (opcional)
                try:
                    test_response = self.generate(
                        "Test",
                        model=self.default_model,
                        options={"max_tokens": 5, "temperature": 0.1},
                    )
                    logger.info(f"Test de generacin exitoso: {test_response[:50]}...")
                except Exception as gen_error:
                    logger.warning(f"Test de generacin fall pero conexin OK: {gen_error}")
                    # No desconectar por fallo en test de generacin

            # Si el servicio responde, marcar como conectado
            if not self.is_connected:
                self.is_connected = True
                self._notify_connection_change(True)
                logger.info(
                    f"Conectado a Ollama en {self.host}:{self.port} con modelo {self.default_model}"
                )
            return True

        except Exception as e:
            if self.is_connected:
                self.is_connected = False
                self._notify_connection_change(False)
            logger.error(f"Error en conexin con Ollama: {e}")
            return False

    def get_models(self) -> list[str]:
        """Obtener lista de modelos disponibles"""
        try:
            url = f"http://{self.host}:{self.port}/api/tags"
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                logger.info(f"Modelos disponibles: {len(models)}")
                return models
            else:
                logger.error(f"Error obteniendo modelos: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error conectando a Ollama para obtener modelos: {e}")
            return []

    def pull_model(
        self, model_name: str, progress_callback: Callable[[str], None] | None = None
    ) -> bool:
        """Descargar modelo si no existe"""
        try:
            # Verificar si ya existe
            models = self.get_models()
            if model_name in models:
                logger.info(f"Modelo {model_name} ya existe")
                return True

            logger.info(f"Descargando modelo {model_name}...")
            url = f"http://{self.host}:{self.port}/api/pull"
            data = {"name": model_name}

            response = requests.post(
                url, json=data, stream=True, timeout=300
            )  # 5 minutos para descargar modelo

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "status" in data:
                                status = data["status"]
                                if progress_callback:
                                    progress_callback(status)
                                logger.info(f"Descargando: {status}")
                        except json.JSONDecodeError:
                            continue

                logger.info(f"Modelo {model_name} descargado exitosamente")
                return True
            else:
                logger.error(f"Error descargando modelo: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error descargando modelo {model_name}: {e}")
            return False

    def generate(
        self,
        prompt: str,
        model: str | None = None,
        stream: bool = False,
        options: dict | None = None,
        use_system_prompt: bool = True,
    ) -> str:
        """Generar respuesta con Ollama"""
        # Paso 2B: Sanitizar prompt
        prompt = sanitize_user_input(prompt)

        # Paso 2B: Detectar jailbreak
        if detect_jailbreak_attempt(prompt):
            logger.warning(f"Jailbreak attempt detectado en generate: {prompt[:50]}...")
            raise ValueError("Prompt bloqueado por seguridad (jailbreak attempt)")

        if not self.is_connected and not self.test_connection():
            raise ConnectionError("No conectado a Ollama")

        model = model or self.current_model

        # Verificar caché Redis
        cache_key = None
        if self.redis_client:
            cache_key = (
                f"ollama:{model}:{hashlib.md5(prompt.encode(), usedforsecurity=False).hexdigest()}"
            )
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit para prompt: {prompt[:50]}...")
                    return cached
            except Exception as e:
                logger.warning(f"Error leyendo caché: {e}")

        try:
            # Obtener system prompt para el modelo
            system_prompt = ""
            if use_system_prompt:
                system_prompt = self.system_prompt_loader.get_system_prompt(model)

            # Usar /api/chat para soportar system messages
            url = f"http://{self.host}:{self.port}/api/chat"

            # Optimizacin: Reducir max_tokens por defecto para respuestas ms rpidas
            default_options = {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 500,  # Reducido de 1000 a 500 para respuestas ms rpidas
            }
            if options:
                default_options.update(options)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            data = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": default_options,
            }

            logger.debug(f"Enviando a Ollama (chat): {prompt[:100]}...")
            if system_prompt:
                logger.debug(f"System prompt inyectado para {model}")

            response = requests.post(url, json=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                response_text = result.get("message", {}).get("content", "")
                logger.debug(f"Respuesta de Ollama: {response_text[:100]}...")

                # Guardar en caché Redis
                if self.redis_client and cache_key:
                    try:
                        self.redis_client.setex(cache_key, 3600, response_text)  # 1 hora TTL
                        logger.debug("Respuesta guardada en caché")
                    except Exception as e:
                        logger.warning(f"Error guardando en caché: {e}")

                return response_text
            else:
                logger.error(f"Error en generacin: {response.status_code}")
                raise Exception(f"Error Ollama: {response.status_code}")

        except Exception as e:
            logger.error(f"Error generando con Ollama: {e}")
            raise

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        options: dict | None = None,
        use_system_prompt: bool = True,
    ) -> str:
        """Chat con formato de mensajes"""
        # Paso 2B: Sanitizar mensajes
        for msg in messages:
            if "content" in msg:
                msg["content"] = sanitize_user_input(msg["content"])
                # Paso 2B: Detectar jailbreak en mensajes
                if detect_jailbreak_attempt(msg["content"]):
                    logger.warning(f"Jailbreak attempt detectado en chat: {msg['content'][:50]}...")
                    raise ValueError("Mensaje bloqueado por seguridad (jailbreak attempt)")

        if not self.is_connected and not self.test_connection():
            raise ConnectionError("No conectado a Ollama")

        model = model or self.current_model

        try:
            # Obtener system prompt para el modelo
            system_prompt = ""
            if use_system_prompt:
                system_prompt = self.system_prompt_loader.get_system_prompt(model)

            url = f"http://{self.host}:{self.port}/api/chat"
            # Optimizacin: Reducir max_tokens por defecto para respuestas ms rpidas
            default_options = {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 500,  # Reducido de 1000 a 500 para respuestas ms rpidas
            }
            if options:
                default_options.update(options)

            # Prepend system prompt if provided
            final_messages = []
            if system_prompt:
                final_messages.append({"role": "system", "content": system_prompt})
            final_messages.extend(messages)

            data = {
                "model": model,
                "messages": final_messages,
                "stream": False,
                "options": default_options,
            }

            if system_prompt:
                logger.debug(f"System prompt inyectado para {model} (chat)")

            response = requests.post(url, json=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "")
            else:
                raise Exception(f"Error Ollama: {response.status_code}")

        except Exception as e:
            logger.error(f"Error en chat: {e}")
            raise

    def set_model(self, model_name: str) -> bool:
        """Cambiar modelo actual"""
        models = self.get_models()
        if model_name in models:
            self.current_model = model_name
            logger.info(f"Modelo cambiado a: {model_name}")
            return True
        else:
            logger.warning(f"Modelo {model_name} no disponible")
            return False

    def get_model_info(self, model_name: str) -> dict | None:
        """Obtener informacin detallada de un modelo"""
        try:
            url = f"http://{self.host}:{self.port}/api/show"
            data = {"name": model_name}

            response = requests.post(url, json=data, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            logger.error(f"Error obteniendo info del modelo: {e}")
            return None

    def start_monitoring(self, interval: int = 5):
        """Iniciar monitorizacin de conexin"""

        def monitor():
            while self.should_monitor:
                try:
                    self.test_connection()
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Error en monitorizacin: {e}")
                    time.sleep(interval)

        self.should_monitor = True
        self.monitoring_thread = threading.Thread(target=monitor, daemon=True)
        self.monitoring_thread.start()
        logger.info("Monitorizacin de Ollama iniciada")

    def stop_monitoring(self):
        """Detener monitorizacin"""
        self.should_monitor = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Monitorizacin de Ollama detenida")

    def health_check(self) -> dict:
        """Verificacin completa de salud"""
        return {
            "connected": self.is_connected,
            "host": self.host,
            "port": self.port,
            "current_model": self.current_model,
            "available_models": len(self.get_models()),
            "monitoring": self.should_monitor,
        }


def completar(modelo: str, system: str, prompt: str) -> dict:
    """
    Wrapper simple para completar con Ollama (usado por code generators)

    Args:
        modelo: Nombre del modelo Ollama
        system: System prompt
        prompt: Prompt del usuario

    Returns:
        Dict con {texto, ok, error}
    """
    try:
        connector = OllamaConnector()
        connector.default_model = modelo
        connector.current_model = modelo

        # Usar chat para soportar system message
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

        response_text = connector.chat(messages, model=modelo, use_system_prompt=False)

        return {"texto": response_text, "ok": True, "error": None}
    except Exception as e:
        logger.error(f"Error en completar(): {e}")
        return {"texto": None, "ok": False, "error": str(e)}


def _make_ollama_connector() -> OllamaConnector:
    """Crea el conector usando OLLAMA_HOST (env) o config_manager, con fallback a localhost."""
    env_host = os.environ.get("OLLAMA_HOST", "")
    if env_host:
        parts = env_host.replace("http://", "").replace("https://", "").split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 11434
        return OllamaConnector(host=host, port=port)
    try:
        from core.config_manager import get_config_manager
        from urllib.parse import urlparse

        url = get_config_manager().config.ollama.get_ollama_url()
        parsed = urlparse(url)
        return OllamaConnector(
            host=parsed.hostname or "localhost",
            port=parsed.port or 11434,
        )
    except Exception:
        return OllamaConnector()


# Singleton global para uso en toda la aplicación
ollama_connector = _make_ollama_connector()
