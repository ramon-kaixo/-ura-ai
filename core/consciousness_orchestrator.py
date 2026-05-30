#!/usr/bin/env python3
"""
Módulo: core/consciousness_orchestrator.py
Propósito: Orquestador de niveles de conciencia URA: coordina comunicación y resuelve conflictos entre niveles.
Dependencias principales: json, datetime, pathlib, threading
Reglas especiales: Priorizar el nivel más alto en conflictos. Registrar todas las decisiones.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)


class ConsciousnessOrchestrator:
    """
    Orquestador central de la conciencia de URA.

    Uso:
        co = ConsciousnessOrchestrator()
        co.initialize()
        context = co.fetch_all_contexts()  # Para inyectar en prompts
        co.start_cycle(interval=30)  # Bucle de activación periódica
    """

    def __init__(self):
        self.modules: dict[str, object] = {}
        self.cycle_thread: threading.Thread | None = None
        self.running = False
        self.context_cache: str = ""
        self.last_fetch: float = 0
        self.cache_ttl: float = 30.0

    def initialize(self):
        """Inicializa todos los módulos de conciencia disponibles."""
        module_loaders = [
            # Conciencia del entorno (Niveles 21-24)
            ("environment", "core.ura_environment_awareness", "get_ura_environment_awareness"),
            ("hardware", "core.ura_hardware_awareness", "get_ura_hardware_awareness"),
            ("applications", "core.ura_applications_awareness", "get_ura_applications_awareness"),
            ("tools", "core.ura_tools_awareness", "get_ura_tools_awareness"),
            # Conciencia superior (Niveles 1-20)
            ("self_knowledge", "core.ura_self_knowledge", "get_ura_self_knowledge"),
            ("emotions", "core.ura_emotions", "get_ura_emotions"),
            ("memory", "core.ura_memory", "get_ura_memory"),
            ("personality", "core.ura_personality", "get_ura_personality"),
            ("goals", "core.ura_goals", "get_ura_goals"),
            ("planning", "core.ura_planning", "get_ura_planning"),
            ("metrics", "core.ura_metrics", "get_ura_metrics"),
            ("self_reflection", "core.ura_self_reflection", "get_ura_self_reflection"),
            ("anticipation", "core.ura_anticipation", "get_ura_anticipation"),
            ("context_continuity", "core.ura_context_continuity", "get_ura_context_continuity"),
            ("theory_of_mind", "core.ura_theory_of_mind", "get_ura_theory_of_mind"),
        ]

        for name, module_path, factory_fn in module_loaders:
            try:
                mod = __import__(module_path, fromlist=[factory_fn])
                fn = getattr(mod, factory_fn)
                instance = fn()
                self.modules[name] = instance
            except Exception as e:
                logger.debug(f"Módulo de conciencia no disponible: {name} ({e})")

        logger.info(f"Conciencia inicializada: {len(self.modules)} módulos cargados")

    def fetch_all_contexts(self, force: bool = False) -> str:
        """
        Recolecta el contexto de todos los módulos de conciencia.
        Usa caché con TTL para evitar sobrecarga.
        """
        now = time.time()
        if not force and now - self.last_fetch < self.cache_ttl and self.context_cache:
            return self.context_cache

        parts = []

        for name in ["environment", "hardware", "applications", "tools"]:
            mod = self.modules.get(name)
            if mod:
                try:
                    if name == "environment":
                        ctx = mod.get_environment_context()
                    elif name == "hardware":
                        ctx = mod.get_hardware_context()
                    elif name == "applications":
                        ctx = mod.get_applications_context()
                    elif name == "tools":
                        ctx = mod.get_tools_context()
                    else:
                        continue
                    if ctx:
                        parts.append(ctx)
                except Exception as e:
                    logger.debug(f"Contexto {name}: {e}")

        for name in [
            "self_knowledge",
            "emotions",
            "memory",
            "personality",
            "goals",
            "planning",
            "metrics",
            "self_reflection",
            "anticipation",
            "context_continuity",
            "theory_of_mind",
        ]:
            mod = self.modules.get(name)
            if mod:
                try:
                    ctx = mod.get_summary_for_prompt()
                    if ctx:
                        parts.append(ctx)
                except AttributeError:
                    try:
                        ctx = mod.get_context_for_prompt()
                        if ctx:
                            parts.append(ctx)
                    except Exception as e:
                        logger.debug(f"Contexto {name}: {e}")
                except Exception as e:
                    logger.debug(f"Contexto {name}: {e}")

        self.context_cache = "\n\n".join(p for p in parts if p)
        self.last_fetch = now
        return self.context_cache

    def start_cycle(self, interval: int = 30):
        """Inicia el bucle de activación periódica en un hilo."""
        if self.running:
            return

        self.running = True

        def _cycle():
            import time as _time

            while self.running:
                try:
                    self.fetch_all_contexts(force=True)
                    self._prune_old_contexts()
                except Exception as e:
                    logger.error(f"Error en ciclo de conciencia: {e}")
                _time.sleep(interval)

        self.cycle_thread = threading.Thread(
            target=_cycle, daemon=True, name="ura-consciousness-cycle"
        )
        self.cycle_thread.start()
        logger.info(f"Ciclo de conciencia iniciado (intervalo={interval}s)")

    def stop_cycle(self):
        """Detiene el ciclo de activación."""
        self.running = False

    def _prune_old_contexts(self):
        """Limpia contextos antiguos para evitar acumulación."""
        for name, mod in self.modules.items():
            try:
                if hasattr(mod, "prune_old"):
                    mod.prune_old()
            except Exception as e:
                logger.warning(f"Error silencioso en consciousness_orchestrator.prune: {e}")
                # fallback: continuar


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    co = ConsciousnessOrchestrator()
    co.initialize()
    context = co.fetch_all_contexts()
    print(f"Contextos cargados: {len(context)} caracteres")
    co.start_cycle(interval=5)
    time.sleep(2)
    co.stop_cycle()
