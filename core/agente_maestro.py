#!/usr/bin/env python3
"""
AgenteMaestro - Unifica los 5 meta-agentes para gobernanza unificada.

Meta-agentes:
- Registry (agents/registry.py) → sabe qué agentes existen
- AgenteConciencia (agents/agente_conciencia.py) → sabe estados
- AgenteSistemas (agents/agente_sistemas.py) → sabe herramientas
- AgenteGobierno (agents/agente_gobierno.py) → control de gobernanza
- AgenteSupervisor (agents/agente_supervisor.py) → monitoriza todo
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgenteMaestro:
    """Agente maestro que unifica los 5 meta-agentes existentes."""

    def __init__(self):
        """Inicializar agente maestro con los 5 meta-agentes."""
        self.nombre = "Agente Maestro"
        self.registry = None
        self.conciencia = None
        self.sistemas = None
        self.gobierno = None
        self.supervisor = None

        self._cargar_agentes()
        self._cargar_estados()
        self._cargar_herramientas()
        self._cargar_gobierno()
        self._cargar_supervisor()

        logger.info("Agente Maestro inicializado con 5 meta-agentes")

    def _cargar_agentes(self):
        """Cargar registry para obtener los agentes."""
        try:
            from agents.registry import list_agents, get_agent, REGISTRY

            self.registry = REGISTRY
            self.list_agents_func = list_agents
            self.get_agent_func = get_agent
            logger.info("Registry cargado")
        except Exception as e:
            logger.error(f"Error cargando registry: {e}")

    def _cargar_estados(self):
        """Cargar agente_conciencia para saber estados."""
        try:
            from agents.agente_conciencia import AgenteConciencia

            self.conciencia = AgenteConciencia()
            logger.info("AgenteConciencia cargado")
        except Exception as e:
            logger.error(f"Error cargando AgenteConciencia: {e}")

    def _cargar_herramientas(self):
        """Cargar agente_sistemas para saber herramientas."""
        try:
            # agente_sistemas no tiene clase, es solo funciones
            import agents.agente_sistemas as sistemas

            self.sistemas = sistemas
            logger.info("AgenteSistemas cargado")
        except Exception as e:
            logger.error(f"Error cargando AgenteSistemas: {e}")

    def _cargar_gobierno(self):
        """Cargar agente_gobierno para control de gobernanza."""
        try:
            from agents.agente_gobierno import AgenteGobierno

            self.gobierno = AgenteGobierno()
            logger.info("AgenteGobierno cargado")
        except Exception as e:
            logger.error(f"Error cargando AgenteGobierno: {e}")

    def _cargar_supervisor(self):
        """Cargar agente_supervisor para monitorizar todo."""
        try:
            from agents.agente_supervisor import AgenteSupervisor

            self.supervisor = AgenteSupervisor()
            logger.info("AgenteSupervisor cargado")
        except Exception as e:
            logger.error(f"Error cargando AgenteSupervisor: {e}")

    def listar_agentes(self) -> dict[str, Any]:
        """Listar todos los agentes y su estado."""
        agentes = {}

        # Usar CentralRouter.intent_to_agent para obtener los 94 agentes
        try:
            from core.central_router import CentralRouter

            router = CentralRouter()
            agentes["intent_to_agent"] = router.intent_to_agent
            agentes["total"] = len(router.intent_to_agent)
            # Devolver directamente el dict de agentes como lista para compatibilidad
            agentes["lista"] = list(router.intent_to_agent.keys())
        except Exception as e:
            logger.error(f"Error obteniendo agentes desde CentralRouter: {e}")
            # Fallback a registry (solo 15 agentes)
            if self.registry:
                try:
                    agentes["registry"] = self.registry
                    agentes["total"] = len(self.registry)
                    agentes["lista"] = list(self.registry.keys())
                except Exception as e2:
                    logger.error(f"Error listando agentes desde registry: {e2}")

        # Usar conciencia si está disponible (método scan_apps si existe)
        if self.conciencia:
            try:
                if hasattr(self.conciencia, "escanear_apps"):
                    apps = self.conciencia.escanear_apps()
                    agentes["apps"] = apps
                elif hasattr(self.conciencia, "scan_apps"):
                    apps = self.conciencia.scan_apps()
                    agentes["apps"] = apps
                else:
                    agentes["conciencia"] = "cargado pero sin método escanear_apps/scan_apps"
            except Exception as e:
                logger.error(f"Error obteniendo apps desde conciencia: {e}")

        return agentes

    def listar_herramientas(self) -> dict[str, Any]:
        """Listar todas las herramientas y su ubicación."""
        herramientas = {}

        if self.sistemas:
            try:
                # Usar funciones de agente_sistemas
                herramientas["red"] = (
                    self.sistemas.sensor_red()
                    if hasattr(self.sistemas, "sensor_red")
                    else "no disponible"
                )
                herramientas["recursos"] = (
                    self.sistemas.sensor_recursos()
                    if hasattr(self.sistemas, "sensor_recursos")
                    else "no disponible"
                )
                herramientas["servicios"] = (
                    self.sistemas.sensor_servicios()
                    if hasattr(self.sistemas, "sensor_servicios")
                    else "no disponible"
                )
            except Exception as e:
                logger.error(f"Error listando herramientas: {e}")

        return herramientas

    def estado_sistema(self) -> dict[str, Any]:
        """Obtener estado general del sistema."""
        estado = {}

        # Usar agente_supervisor si está disponible
        try:
            import agents.agente_supervisor as supervisor

            if hasattr(supervisor, "resumen_rapido"):
                estado["supervisor"] = supervisor.resumen_rapido()
            elif hasattr(supervisor, "estado_tareas"):
                estado["supervisor"] = supervisor.estado_tareas()
            else:
                estado["supervisor"] = "cargado pero sin métodos de estado"
        except Exception as e:
            logger.error(f"Error obteniendo estado desde supervisor: {e}")

        # Usar agente_conciencia si está disponible
        if self.conciencia:
            try:
                if hasattr(self.conciencia, "escanear_apps"):
                    apps = self.conciencia.escanear_apps()
                    estado["apps"] = apps
                elif hasattr(self.conciencia, "scan_apps"):
                    apps = self.conciencia.scan_apps()
                    estado["apps"] = apps
            except Exception as e:
                logger.error(f"Error obteniendo estado desde conciencia: {e}")

        return estado

    def _es_consulta_introspeccion(self, consulta: str) -> bool:
        """Determinar si la consulta es de introspección."""
        consulta_lower = consulta.lower()

        keywords_introspeccion = [
            "qué agentes",
            "qué herramientas",
            "qué puedes hacer",
            "lista agentes",
            "quiénes estáis",
            "qué sabes hacer",
            "qué programas",
            "cómo está el sistema",
            "qué está pasando",
            "estado del sistema",
            "qué hay instalado",
            "qué conoces",
            "qué tienes",
            "qué puedes",
            "qué eres capaz",
            "qué hay",
            "qué existe",
            "qué hay disponible",
            "listar",
            "mostrar",
            "ver",
            "ver todo",
        ]

        return any(keyword in consulta_lower for keyword in keywords_introspeccion)

    def _es_consulta_herramientas(self, consulta: str) -> bool:
        """Determinar si la consulta es sobre herramientas del sistema."""
        consulta_lower = consulta.lower()

        keywords_herramientas = [
            "qué programas",
            "qué está instalado",
            "qué software",
            "qué herramientas",
            "qué apps",
            "qué aplicaciones",
            "instalado",
            "programas",
            "software",
            "apps",
        ]

        return any(keyword in consulta_lower for keyword in keywords_herramientas)

    def _es_consulta_estado(self, consulta: str) -> bool:
        """Determinar si la consulta es sobre el estado del sistema."""
        consulta_lower = consulta.lower()

        keywords_estado = [
            "cómo está",
            "qué está pasando",
            "estado del sistema",
            "estado general",
            "estado sistema",
            "todo bien",
            "funcionando",
            "operativo",
            "status del sistema",
        ]

        # Excluir consultas que claramente NO son de estado general
        exclusiones = [
            "seguridad",
            "firewall",
            "antivirus",
            "blindaje",
            "vulnerabilidad",
            "amenaza",
            "ataque",
            "malware",
            "backup",
            "copia",
            "restaurar",
        ]
        for excl in exclusiones:
            if excl in consulta_lower:
                return False

        return any(keyword in consulta_lower for keyword in keywords_estado)

    def preguntar(self, consulta: str) -> str:
        """
        Consulta unificada que deriva al meta-agente adecuado.

        Args:
            consulta: Consulta del usuario

        Returns:
            String con respuesta
        """
        consulta.lower()

        # a) Consulta sobre agentes (introspección)
        if self._es_consulta_introspeccion(consulta):
            agentes = self.listar_agentes()
            return self._formatear_agentes(agentes)

        # b) Consulta sobre herramientas del sistema
        elif self._es_consulta_herramientas(consulta):
            herramientas = self.listar_herramientas()
            return self._formatear_herramientas(herramientas)

        # c) Consulta sobre estado del sistema
        elif self._es_consulta_estado(consulta):
            estado = self.estado_sistema()
            return self._formatear_estado(estado)

        # d) No hay coincidencia clara
        else:
            return "No estoy seguro de entender tu consulta. ¿Podrías ser más específico?"

    def _formatear_agentes(self, agentes: dict[str, Any]) -> str:
        """Formatear lista de agentes para respuesta."""
        if not agentes:
            return "No hay agentes disponibles."

        resultado = "Agentes disponibles:\n"

        if "registry" in agentes and agentes["registry"]:
            resultado += f"- Total de agentes: {len(agentes['registry'])}\n"

        if "estados" in agentes and agentes["estados"]:
            resultado += "\nEstados de agentes:\n"
            for agente, estado in agentes["estados"].items():
                resultado += f"- {agente}: {estado}\n"

        return resultado

    def _formatear_herramientas(self, herramientas: dict[str, Any]) -> str:
        """Formatear lista de herramientas para respuesta."""
        if not herramientas:
            return "No hay herramientas disponibles."

        resultado = "Herramientas disponibles:\n"

        for herramienta, info in herramientas.items():
            resultado += f"- {herramienta}: {info}\n"

        return resultado

    def _formatear_estado(self, estado: dict[str, Any]) -> str:
        """Formatear estado del sistema para respuesta."""
        if not estado:
            return "No hay información de estado disponible."

        resultado = "Estado del sistema:\n"

        for key, value in estado.items():
            resultado += f"- {key}: {value}\n"

        return resultado

    def ejecutar(self, consulta: str) -> dict[str, Any]:
        """Ejecutar consulta (alias de preguntar)."""
        return {"respuesta": self.preguntar(consulta)}

    def consultar(self, consulta: str) -> dict[str, Any]:
        """Consultar información (alias de preguntar)."""
        return self.preguntar(consulta)

    def responder(self, consulta: str) -> dict[str, Any]:
        """Responder pregunta (alias de preguntar)."""
        return self.preguntar(consulta)


# Instancia global del agente maestro
_agente_maestro_instance: AgenteMaestro | None = None


def get_agente_maestro() -> AgenteMaestro:
    """Obtener instancia global del agente maestro (singleton)."""
    global _agente_maestro_instance
    if _agente_maestro_instance is None:
        _agente_maestro_instance = AgenteMaestro()
    return _agente_maestro_instance


if __name__ == "__main__":
    maestro = get_agente_maestro()
    print(maestro.estado_sistema())
    print("✅ Agente Maestro activo")
