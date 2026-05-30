#!/usr/bin/env python3
"""
Guardrails de Vocabulario - URA App
Protecciones contra errores y alucinaciones
"""

import json
from datetime import datetime, timedelta


class GuardrailsVocabulario:
    """Protecciones para sistema de vocabulario"""

    def __init__(self):
        self.nombre = "guardrails_vocabulario"
        self.errores_recientes = []
        self.cache_respuestas = {}
        self.max_errores = 10
        self.timeout_ollama = 30

    def validar_contexto(self, departamento: str, tipo_codigo: str, box: str) -> dict:
        """Validar que el contexto es válido"""
        departamentos_validos = [
            "tecnologia",
            "legal",
            "financiero",
            "hosteleria",
            "gastronomia",
            "codigo",
        ]
        tipos_validos = ["python", "javascript", "sql", "html", "api", "ml", "devops", "seguridad"]

        errores = []

        if departamento not in departamentos_validos:
            errores.append(f"Departamento inválido: {departamento}")

        if tipo_codigo not in tipos_validos:
            errores.append(f"Tipo de código inválido: {tipo_codigo}")

        if not box or len(box) < 2:
            errores.append(f"Box inválido: {box}")

        return {"valido": len(errores) == 0, "errores": errores}

    def validar_respuesta_ollama(self, respuesta: str) -> dict:
        """Validar respuesta de Ollama"""
        if not respuesta or len(respuesta) < 10:
            return {"valida": False, "error": "Respuesta vacía o muy corta"}

        if "Error:" in respuesta:
            return {"valida": False, "error": "Ollama devolvió error"}

        # Intentar parsear JSON
        try:
            datos = json.loads(respuesta)

            # Validar campos requeridos
            campos_requeridos = ["categoria", "nivel_seguridad", "palabras_clave"]
            for campo in campos_requeridos:
                if campo not in datos:
                    return {"valida": False, "error": f"Campo faltante: {campo}"}

            # Validar tipos
            if not isinstance(datos["palabras_clave"], list):
                return {"valida": False, "error": "palabras_clave debe ser lista"}

            if len(datos["palabras_clave"]) == 0:
                return {"valida": False, "error": "palabras_clave está vacía"}

            return {"valida": True, "datos": datos}

        except json.JSONDecodeError:
            return {"valida": False, "error": "JSON inválido"}

    def verificar_tasa_errores(self) -> bool:
        """Verificar si tasa de errores es aceptable"""
        ahora = datetime.now()
        # Limpiar errores antiguos (más de 1 hora)
        self.errores_recientes = [
            e for e in self.errores_recientes if ahora - e["timestamp"] < timedelta(hours=1)
        ]

        total_errores = len(self.errores_recientes)

        if total_errores > self.max_errores:
            return False  # Tasa de errores demasiado alta

        return True

    def registrar_error(self, tipo: str, mensaje: str):
        """Registrar error para seguimiento"""
        self.errores_recientes.append(
            {"timestamp": datetime.now(), "tipo": tipo, "mensaje": mensaje}
        )

    def obtener_cache(self, clave: str) -> dict | None:
        """Obtener respuesta cacheada"""
        if clave in self.cache_respuestas:
            cache = self.cache_respuestas[clave]
            # Cache válido por 1 hora
            if datetime.now() - cache["timestamp"] < timedelta(hours=1):
                return cache["datos"]
            else:
                del self.cache_respuestas[clave]

        return None

    def guardar_cache(self, clave: str, datos: dict):
        """Guardar respuesta en cache"""
        self.cache_respuestas[clave] = {"timestamp": datetime.now(), "datos": datos}

    def generar_clave_cache(self, departamento: str, tipo_codigo: str, contenido: str) -> str:
        """Generar clave única para cache"""
        import hashlib

        contenido_hash = hashlib.sha256(contenido.encode()).hexdigest()[:16]
        return f"{departamento}_{tipo_codigo}_{contenido_hash}"

    def fallback_vocabulario_tecnico(self, tipo_codigo: str) -> dict:
        """Fallback a vocabulario técnico si Ollama falla"""
        vocabulario_por_defecto = {
            "python": {
                "categoria": "tecnico",
                "nivel_seguridad": "publico",
                "palabras_clave": ["python", "function", "class", "import"],
            },
            "javascript": {
                "categoria": "tecnico",
                "nivel_seguridad": "publico",
                "palabras_clave": ["javascript", "function", "const", "let"],
            },
            "sql": {
                "categoria": "tecnico",
                "nivel_seguridad": "publico",
                "palabras_clave": ["sql", "select", "from", "where"],
            },
        }

        return vocabulario_por_defecto.get(
            tipo_codigo,
            {"categoria": "general", "nivel_seguridad": "publico", "palabras_clave": ["codigo"]},
        )


# Instancia global
guardrails_vocabulario = GuardrailsVocabulario()
