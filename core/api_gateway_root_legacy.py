#!/usr/bin/env python3
"""
Sistema de API Gateway URA
Gateway único para todas las APIs
"""

import time
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, request


class APIGateway:
    """API Gateway"""

    def __init__(self):
        self.app = Flask(__name__)
        self.routes = {}
        self.rate_limits = {}

    def rate_limit(self, max_requests: int = 100, window_seconds: int = 60):
        """Decorador para rate limiting"""

        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                client_ip = request.remote_addr

                if client_ip not in self.rate_limits:
                    self.rate_limits[client_ip] = {"requests": [], "window_start": time.time()}

                client_data = self.rate_limits[client_ip]

                # Limpiar ventana antigua
                if time.time() - client_data["window_start"] > window_seconds:
                    client_data["requests"] = []
                    client_data["window_start"] = time.time()

                # Verificar límite
                if len(client_data["requests"]) >= max_requests:
                    return jsonify({"error": "Rate limit exceeded"}), 429

                client_data["requests"].append(time.time())

                return f(*args, **kwargs)

            return wrapper

        return decorator

    def agregar_ruta(self, path: str, methods: list[str], handler: callable):
        """Agrega ruta al gateway"""

        def route_handler():
            try:
                return handler(request)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        for method in methods:
            self.app.route(path, methods=[method])(route_handler)

        self.routes[path] = {"methods": methods, "handler": handler}

    def middleware_autenticacion(self, f):
        """Middleware de autenticación"""

        @wraps(f)
        def wrapper(*args, **kwargs):
            token = request.headers.get("Authorization")

            if not token:
                return jsonify({"error": "Unauthorized"}), 401

            # Verificar token usando variable de entorno
            expected_token = f"Bearer {os.getenv('API_GATEWAY_TOKEN', 'valid_token')}"
            if token != expected_token:
                return jsonify({"error": "Invalid token"}), 403

            return f(*args, **kwargs)

        return wrapper

    def middleware_logging(self, f):
        """Middleware de logging"""

        @wraps(f)
        def wrapper(*args, **kwargs):
            inicio = time.time()

            print(f"[{datetime.now().isoformat()}] {request.method} {request.path}")

            resultado = f(*args, **kwargs)

            duracion = time.time() - inicio
            print(f"[{datetime.now().isoformat()}] Response: {duracion:.3f}s")

            return resultado

        return wrapper

    def obtener_estadisticas(self) -> dict:
        """Obtiene estadísticas del gateway"""
        return {
            "total_rutas": len(self.routes),
            "rate_limits": len(self.rate_limits),
            "timestamp": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    gateway = APIGateway()

    # Ejemplo de ruta
    def handler_ejemplo(request):
        return jsonify({"mensaje": "Hola desde API Gateway"})

    gateway.agregar_ruta("/api/ejemplo", ["GET"], handler_ejemplo)

    print("🚀 API Gateway iniciado en puerto 5001")
    gateway.app.run(host="0.0.0.0", port=5001)
    gateway.app.run(host="0.0.0.0", port=5001)
