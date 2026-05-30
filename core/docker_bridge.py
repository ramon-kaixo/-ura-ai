#!/usr/bin/env python3
"""
Puente entre URA_App (host) y Sandbox Docker
Permite comunicación bidireccional entre la interfaz y los agentes
"""

import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DockerBridge:
    """Puente de comunicación con sandbox Docker"""

    def __init__(self, docker_host: str = "localhost", docker_port: int = 8080):
        self.docker_host = docker_host
        self.docker_port = docker_port
        self.base_url = f"http://{docker_host}:{docker_port}"
        self.redis_host = "localhost"
        self.redis_port = 6379

    def enviar_tarea_agente(self, agente: str, accion: str, params: dict) -> dict:
        """Enviar tarea a agente en sandbox Docker"""
        try:
            # Usar Redis como cola de mensajes
            import redis

            r = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)

            mensaje = {
                "origen": "URA_App",
                "destino": "sandbox",
                "agente": agente,
                "accion": accion,
                "params": params,
                "timestamp": str(datetime.now()),
            }

            # Publicar en canal Redis
            r.publish("ura_tasks", json.dumps(mensaje))

            logger.info(f"Tarea enviada a {agente}: {accion}")
            return {"estado": "enviado", "mensaje_id": str(hash(json.dumps(mensaje)))}
        except Exception as e:
            logger.error(f"Error enviando tarea: {e}")
            return {"estado": "error", "mensaje": str(e)}

    def recibir_resultado(self, timeout: int = 30) -> dict | None:
        """Recibir resultado desde sandbox Docker"""
        try:
            import redis

            r = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)

            # Suscribirse a canal de resultados
            pubsub = r.pubsub()
            pubsub.subscribe("ura_results")

            # Esperar mensaje
            for message in pubsub.listen():
                if message["type"] == "message":
                    resultado = json.loads(message["data"])
                    logger.info(f"Resultado recibido: {resultado}")
                    return resultado

            return None
        except Exception as e:
            logger.error(f"Error recibiendo resultado: {e}")
            return None

    def obtener_estado_sandbox(self) -> dict:
        """Obtener estado del sandbox Docker"""
        try:
            import redis

            r = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)

            # Verificar conexión Redis
            r.ping()

            # Obtener estado desde Redis
            estado = r.get("ura_sandbox_state")
            if estado:
                return json.loads(estado)
            else:
                return {"estado": "desconocido", "mensaje": "No hay estado disponible"}
        except Exception as e:
            logger.error(f"Error obteniendo estado: {e}")
            return {"estado": "error", "mensaje": str(e)}

    def iniciar_agente_sandbox(self, agente: str) -> bool:
        """Solicitar inicio de agente en sandbox"""
        resultado = self.enviar_tarea_agente("orquestador", "iniciar_agente", {"agente": agente})
        return resultado.get("estado") == "enviado"


# Instancia global
docker_bridge = DockerBridge()

if __name__ == "__main__":
    from datetime import datetime

    print("Puente Docker iniciado")
    print(f"Estado sandbox: {docker_bridge.obtener_estado_sandbox()}")
