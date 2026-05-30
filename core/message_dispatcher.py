#!/usr/bin/env python3
"""
URA - Message Dispatcher
Encapsula el routing de mensajes del usuario a los handlers apropiados.

Extraído desde main_final.py (Fase 4, Paso 1).
"""

import contextlib
import logging
import sys
import time

from core.command_detector import (
    is_app_command,
    is_install_command,
    is_manual_command,
    is_screen_area_command,
    is_visual_automation_command,
    is_windsurf_command,
)
from core.ura_config import config
from core.ura_identity import get_system_prompt

logger = logging.getLogger(__name__)


class MessageDispatcher:
    """
    Router de mensajes del usuario.

    Toda la lógica originalmente en URAMainWindowFinal.send_message().
    Recibe el MainWindow como `context` y nunca toca widgets directamente:
    siempre vía context.chat_ura(), context.hide_progress(), etc.
    """

    def __init__(self, context):
        self.context = context
        # Resolución diferida de símbolos definidos en main_final
        # (clases, flags y funciones cargadas con try/except)
        self._main_module = sys.modules.get(context.__class__.__module__)

    # ------------------------------------------------------------------
    # Helpers de acceso al módulo principal
    # ------------------------------------------------------------------
    def _mf(self, name, default=None):
        """Obtiene un símbolo del módulo de main_final (o default si no existe)."""
        return getattr(self._main_module, name, default)

    def _security_check(self, message: str) -> bool:
        """
        Valida el mensaje con agente_policia_v2 antes de despacharlo.

        Devuelve True si se permite continuar, False si está bloqueado.
        Si agente_policia_v2 no está disponible o falla, se permite por
        defecto (fail-open) y se registra en logs.
        """
        try:
            # Preferir API simple si existe (validar_comando)
            try:
                from core.agente_policia_v2 import validar_comando

                validacion = validar_comando(message)
                permitido = validacion.get("permitido", True)
                motivo = validacion.get("motivo", "seguridad")
            except ImportError:
                # Fallback al API actual: AgentePoliciaV2.validar() vía get_agente_policia
                from core.agente_policia_v2 import get_agente_policia

                resultado = get_agente_policia().validar(message)
                veredicto = (resultado.get("veredicto") or "").upper()
                # Solo bloqueamos en RECHAZADO; REQUIERE_REVISION/APROBADO continúan
                permitido = veredicto != "RECHAZADO"
                razones = resultado.get("razon", [])
                motivo = "; ".join(razones) if isinstance(razones, list) else str(razones)

            if not permitido:
                self.context.chat_alert(f"Comando bloqueado: {motivo}")
                logger.warning(f"agente_policia bloqueó mensaje: {motivo}")
                return False

            return True
        except Exception as e:
            # Fail-open: si la validación falla, no rompemos el flujo del usuario
            logger.error(f"Error en validación de seguridad (continuando sin validar): {e}")
            return True

    def _check_semantic_memory(self, mensaje: str) -> str | None:
        """
        Busca en memoria semántica (singleton del módulo) antes de llamar a Ollama.

        Devuelve un texto con el contexto recuperado, o None si no hay
        resultados / la memoria no está disponible.
        """
        try:
            from core.semantic_memory import semantic_memory_manager

            # Forward-compat: si se añade un .search() en el futuro, úsalo.
            search = getattr(semantic_memory_manager, "search", None)
            if callable(search):
                resultados = search(mensaje, limit=3)
            else:
                # API actual: recall_from_default(query, top_k)
                resultados = semantic_memory_manager.recall_from_default(mensaje, top_k=3)

            if not resultados:
                return None

            # Soportamos varias formas: 'texto', 'content', 'text'
            partes = []
            for r in resultados:
                texto = r.get("texto") or r.get("content") or r.get("text") or ""
                if texto:
                    partes.append(texto)

            if not partes:
                return None

            return "\n".join(partes)
        except Exception as exc:
            logger.debug(f"Memoria semántica no disponible o falló: {exc}")
            return None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def dispatch(self, mensaje=None):
        """Punto de entrada: replica la lógica original de send_message()."""
        ctx = self.context

        # 0. Obtener mensaje (del input o del parámetro)
        if mensaje is None:
            message = ctx.user_input.text().strip()
        else:
            message = mensaje.strip() if isinstance(mensaje, str) else ""

        if not message:
            return

        # 0.5. Validación de seguridad (agente_policia_v2)
        if not self._security_check(message):
            return

        # 1. Triaje de entrada (Sistema de Dos Carreteras)
        if self._triaje_internet_aborted(message):
            return

        # 2. Rate limiting
        if self._apply_rate_limit():
            return

        # 3. Cache check
        cached = self._check_cache(message)
        if cached is not None:
            return

        # 4. Corrección automática
        message = self._auto_correct(message)

        # 5. Tracking + memoria conversacional + contextos
        ctx._last_user_message = message
        self._touch_tracker()
        self._add_to_memory(message)

        # 6. UI: añadir al historial y limpiar input
        timestamp = time.strftime("%H:%M:%S")
        ctx.chat_user(message)
        ctx.user_input.clear()
        ctx.show_progress()

        # 7. Comandos especiales (identidad, disco, etc.) - early returns
        if self._handle_special_commands(message):
            return

        # 8. Routing a handlers extraídos (Fase 2)
        if self._route_to_handler(message):
            return

        # 9. Comando del sistema (/...)
        if message.startswith("/"):
            if self._handle_system_command(message, timestamp):
                return

        # 10. Procesar con Ollama (streaming)
        self._dispatch_to_ollama(message)

    # ------------------------------------------------------------------
    # Submétodos privados
    # ------------------------------------------------------------------
    def _triaje_internet_aborted(self, message: str) -> bool:
        """Triaje rápido: detecta si va por la 'carretera 2 (internet)' y aplica timeout."""
        keywords_red = [
            "buscar",
            "web",
            "internet",
            "noticias",
            "precio",
            "google",
            "actualidad",
            "duckduckgo",
            "bing",
            "search",
        ]
        es_externo = any(word in message.lower() for word in keywords_red)
        if not es_externo:
            return False

        # Ejecución con PROTECCIÓN DE TIMEOUT (best-effort, solo POSIX)
        try:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("Timeout")

            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(10)
            try:
                # Placeholder: agente_policia no disponible; el timeout
                # real se aplica en la búsqueda web más adelante.
                pass
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        except TimeoutError:
            self.context.chat_alert("⚠️ Parálisis de Internet detectada. Saltando por seguridad.")
            self.context.hide_progress()
            return True
        except Exception as e:
            logger.warning(f"Error silencioso en message_dispatcher._timeout_handler: {e}")
            # fallback: Si signal/alarm no funciona, continuar con flujo normal

        return False

    def _apply_rate_limit(self) -> bool:
        """Devuelve True si debe abortar por rate limit."""
        ctx = self.context
        if config.rate_limiter_available and ctx.rate_limiter:
            if not ctx.rate_limiter.allow_request():
                ctx.chat_alert("⚠️ Demasiados requests. Espera unos segundos.")
                return True
        return False

    def _check_cache(self, message: str):
        """Si hay respuesta cacheada, la pinta y devuelve la respuesta. Si no, None."""
        ctx = self.context
        cache_key = f"ura_response:{message}"
        if config.cache_available and ctx.cache:
            cached_response = ctx.cache.get(cache_key)
            if cached_response:
                logger.info(f"Cache hit para: {message[:50]}...")
                ctx.chat_ura(cached_response)
                ctx.pending_ura_response = cached_response
                ctx.ura_pending_text.setPlainText(cached_response)
                ctx.hide_progress()
                return cached_response
        return None

    def _auto_correct(self, message: str) -> str:
        """Separa palabras pegadas tras un verbo de comando."""
        split_stuck_command = self._mf("split_stuck_command")
        if split_stuck_command is None:
            return message
        corrected = split_stuck_command(message)
        if corrected != message:
            logger.info("Comando corregido: %r -> %r", message, corrected)
            return corrected
        return message

    def _touch_tracker(self):
        """Evita que Ollama descargue el modelo por idle."""
        get_tracker = self._mf("get_tracker")
        if config.ram_manager_available and get_tracker is not None:
            with contextlib.suppress(Exception):
                get_tracker().touch()

    def _add_to_memory(self, message: str):
        """Guarda turno de usuario en memoria conversacional, dinámica y semántica."""
        ctx = self.context

        get_memory = self._mf("get_memory")
        if config.ura_memory_available and get_memory is not None:
            with contextlib.suppress(Exception):
                get_memory().add_user(message)

        if config.dynamic_context_available and ctx.dynamic_context:
            try:
                ctx.dynamic_context.add_message(message, role="user", priority=0.7)
            except Exception as e:
                logger.error(f"Error adding to dynamic context: {e}")

        if self._mf("SEMANTIC_MEMORY_AVAILABLE") and ctx.semantic_memory:
            try:
                ctx.semantic_memory.add_memory(
                    f"Usuario: {message}", {"type": "user_message"}, importance=0.6
                )
            except Exception as e:
                logger.error(f"Error adding to semantic memory: {e}")

    def _handle_special_commands(self, message: str) -> bool:
        """Comandos con respuesta inmediata: identidad, disco, búsqueda, visión."""
        ctx = self.context

        # Identidad / capacidades
        is_identity_query = self._mf("is_identity_query")
        get_identity = self._mf("get_identity")
        if (
            config.ura_identity_available
            and is_identity_query is not None
            and is_identity_query(message)
        ):
            ident = get_identity()
            reply = ident.capabilities_report()
            ctx.chat_ura(reply)
            ctx.pending_ura_response = reply
            ctx.ura_pending_text.setPlainText(reply)
            ctx.hide_progress()
            return True

        # Disco / almacenamiento
        is_disk_command = self._mf("is_disk_command")
        disk_report = self._mf("disk_report")
        low_space_warning = self._mf("low_space_warning")
        if (
            config.disk_monitor_available
            and is_disk_command is not None
            and is_disk_command(message)
        ):
            try:
                reporte = disk_report()
            except Exception as exc:
                ctx.chat_alert(f"No pude leer el estado del disco: {exc}")
                ctx.hide_progress()
                return True
            ctx.chat_ura(reporte)
            ctx.pending_ura_response = reporte
            ctx.ura_pending_text.setPlainText(reporte)
            warn = low_space_warning() if low_space_warning else None
            if warn:
                ctx.chat_alert(warn)
            ctx.hide_progress()
            return True

        # Búsqueda web
        is_search_command = self._mf("is_search_command")
        _WebSearchThread = self._mf("_WebSearchThread")
        if (
            config.web_search_available
            and is_search_command is not None
            and is_search_command(message)
        ):
            ctx.chat_ura("🌐 Buscando en internet… te lo resumo en un momento.")
            if getattr(ctx, "_search_thread", None) is not None and ctx._search_thread.isRunning():
                ctx.chat_alert("Ya hay una búsqueda en curso. Espera a que termine.")
                ctx.hide_progress()
                return True
            ctx._search_thread = _WebSearchThread(message, parent=ctx)
            ctx._search_thread.search_ready.connect(ctx._on_search_ready)
            ctx._search_thread.search_failed.connect(ctx._on_search_failed)
            ctx._search_thread.start()
            return True

        # Visión
        is_vision_command = self._mf("is_vision_command")
        _VisionThread = self._mf("_VisionThread")
        if config.vision_available and is_vision_command is not None and is_vision_command(message):
            ctx.chat_ura("👁️ Voy a mirar tu pantalla ahora mismo…")
            if getattr(ctx, "_vision_thread", None) is not None and ctx._vision_thread.isRunning():
                ctx.chat_alert("Ya hay una captura de pantalla en curso. Espera a que termine.")
                ctx.hide_progress()
                return True
            ctx._vision_thread = _VisionThread(prompt=message, parent=ctx)
            ctx._vision_thread.vision_ready.connect(ctx._on_vision_ready)
            ctx._vision_thread.vision_failed.connect(ctx._on_vision_failed)
            ctx._vision_thread.start()
            return True

        return False

    def _route_to_handler(self, message: str) -> bool:
        """Routing a los handlers extraídos en Fase 2 (visual, install, screen, manual, app, windsurf)."""
        ctx = self.context

        # Automatización visual
        if config.visual_automation_available and is_visual_automation_command(message):
            ctx.chat_ura("🤖 Voy a guiarte paso a paso usando visión y automatización…")
            ctx._handle_visual_automation(message)
            return True

        # Instalación en sandbox
        if config.sandbox_installer_available and is_install_command(message):
            ctx.chat_ura("📦 Voy a instalar el paquete en entorno aislado…")
            ctx._handle_sandbox_install(message)
            return True

        # Selección de área
        if config.screen_selector_available and is_screen_area_command(message):
            ctx.chat_ura("🖱️ Voy a analizar el área que selecciones…")
            ctx._handle_screen_area(message)
            return True

        # Consulta de manuales
        if config.manual_repository_available and is_manual_command(message):
            ctx.chat_ura("📖 Voy a buscar en los manuales…")
            ctx._handle_manual_query(message)
            return True

        # Aplicaciones macOS
        if config.mac_apps_available and is_app_command(message):
            ctx.chat_ura("🚀 Procesando comando de aplicaciones…")
            ctx._handle_app_command(message)
            return True

        # Windsurf binomio
        if config.windsurf_binomio_available and is_windsurf_command(message):
            ctx.chat_ura("🤖 Procesando comando de Windsurf…")
            ctx._handle_windsurf_command(message)
            return True

        return False

    def _handle_system_command(self, message: str, timestamp: str) -> bool:
        """Comandos que empiezan por '/' → terminal_gateway, con self-reflection."""
        ctx = self.context

        # Self-Reflection antes de ejecutar
        self_reflection_manager = self._mf("self_reflection_manager")
        if config.self_reflection_available and self_reflection_manager:
            try:
                reflection_layer = self_reflection_manager.get_layer()
                if reflection_layer:
                    decision = {
                        "decision_id": f"cmd_{timestamp}",
                        "action": message[1:],
                        "parameters": {},
                        "type": "terminal_command",
                    }
                    reflection_result = reflection_layer.reflect(decision)
                    if not reflection_result.passed and reflection_result.score < 0.5:
                        ctx.chat_alert(
                            f"⚠️ Self-Reflection bloqueó el comando: "
                            f"{reflection_result.suggestion or 'Razón no especificada'}"
                        )
                        ctx.hide_progress()
                        return True
            except Exception as e:
                logger.error(f"Error in self-reflection: {e}")

        success, output, error = ctx.terminal_gateway.smart_execute(message[1:])
        if error:
            ctx.ura_context_text.append(f"[{timestamp}] Error: {error}")

        if success and output:
            ctx.ura_context_text.append(f"[{timestamp}] Sistema: {output}")
            ctx.chat_ura(output)
            ctx.pending_ura_response = output
            ctx.ura_pending_text.setPlainText(output)

            cursor = ctx.ura_history_text.textCursor()
            cursor.movePosition(cursor.End)
            ctx.ura_history_text.setTextCursor(cursor)

            logger.info(f"Comando del sistema ejecutado: {message[:50]}...")
            ctx.hide_progress()
            return True
        elif error:
            ctx.ura_context_text.append(f"[{timestamp}] Error: {error}")
            ctx.hide_progress()
            return True

        return False

    def _react_enhance(self, message: str) -> str:
        """Enriquece el mensaje con análisis ReAct antes de enviar a Ollama."""
        try:
            react_engine = self._mf("react_engine")
            if react_engine is None or not self._mf("REACT_ENGINE_AVAILABLE"):
                return message
            ctx = self.context
            context = getattr(ctx, "windsurf_context", "") or getattr(
                ctx, "pending_ura_response", ""
            )
            steps = react_engine.run(context, message)
            if not steps:
                return message
            thoughts = [f"[PENSAMIENTO] {s.thought}" for s in steps if s.thought]
            if thoughts:
                reasoning = "\n".join(thoughts[-3:])
                return f"{reasoning}\n\n[MENSAJE] {message}"
        except Exception as e:
            logger.warning(f"ReAct enhancement skip: {e}")
        return message

    def _dispatch_to_ollama(self, message: str):
        """Procesa con Ollama via streaming thread."""
        ctx = self.context

        # ReAct: analizar antes de responder
        message = self._react_enhance(message)

        # Seleccionar modelo según complejidad
        model = ctx.select_model_for_message(message)

        # Obtener system prompt dinámico
        system = get_system_prompt()

        # Memoria semántica como contexto (instancia per-window legacy)
        semantic_context = ""
        if self._mf("SEMANTIC_MEMORY_AVAILABLE") and ctx.semantic_memory:
            try:
                memories = ctx.semantic_memory.recall(message, top_k=3)
                if memories:
                    semantic_context = "\n".join([f"- {m['content']}" for m in memories])
                    logger.info(f"Recalled {len(memories)} semantic memories")
            except Exception as e:
                logger.error(f"Error recalling semantic memory: {e}")

        # Enriquecer mensaje con contexto semántico del singleton del módulo
        memoria_contexto = self._check_semantic_memory(message)
        if memoria_contexto:
            mensaje_enriquecido = (
                f"Contexto previo relevante:\n{memoria_contexto}\n\nMensaje actual: {message}"
            )
            logger.info("Mensaje enriquecido con contexto de memoria semántica")
        else:
            mensaje_enriquecido = message

        # Procesar via streaming
        StreamingMessageProcessorThread = self._mf("StreamingMessageProcessorThread")
        ctx.streaming_response = ""
        ctx.streaming_thread = StreamingMessageProcessorThread(
            ctx.ollama_connector, mensaje_enriquecido, model, semantic_context, system
        )
        ctx.streaming_thread.chunk_ready.connect(ctx.handle_streaming_chunk)
        ctx.streaming_thread.response_complete.connect(ctx.handle_streaming_complete)
        ctx.streaming_thread.error_occurred.connect(ctx.handle_processing_error)
        ctx.active_streaming_threads.append(ctx.streaming_thread)
        ctx.streaming_thread.start()

        # Indicador en panel pendiente
        ctx.ura_pending_text.setPlainText("URA está escribiendo...")
