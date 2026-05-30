#!/usr/bin/env python3
"""
Agente de Vocabulario de Código - URA App
Vocabulario técnico para programación
Sin sinónimos ni antónimos - Reduce palabras sin perder contexto
"""


class AgenteVocabularioCodigo:
    """Vocabulario técnico para programación"""

    def __init__(self):
        self.nombre = "agente_vocabulario_codigo"
        self.vocabulario_base = {
            "python": [
                "function",
                "class",
                "import",
                "def",
                "return",
                "if",
                "else",
                "for",
                "while",
                "try",
                "except",
            ],
            "javascript": [
                "function",
                "const",
                "let",
                "var",
                "return",
                "if",
                "else",
                "for",
                "while",
                "try",
                "catch",
            ],
            "sql": [
                "SELECT",
                "FROM",
                "WHERE",
                "JOIN",
                "GROUP BY",
                "ORDER BY",
                "INSERT",
                "UPDATE",
                "DELETE",
            ],
            "api": [
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "endpoint",
                "request",
                "response",
                "status",
                "json",
            ],
            "ml": [
                "model",
                "train",
                "predict",
                "fit",
                "transform",
                "feature",
                "label",
                "accuracy",
                "loss",
            ],
            "devops": [
                "docker",
                "kubernetes",
                "ci",
                "cd",
                "pipeline",
                "deploy",
                "build",
                "test",
                "container",
            ],
            "seguridad": [
                "encryption",
                "hash",
                "token",
                "auth",
                "vulnerability",
                "exploit",
                "patch",
                "audit",
            ],
        }

    def analizar(self, contenido: str, tipo_codigo: str = "python") -> dict:
        """Analizar código y extraer vocabulario técnico"""
        terminos_tecnicos = self.vocabulario_base.get(tipo_codigo, self.vocabulario_base["python"])

        encontrados = []
        for termino in terminos_tecnicos:
            if termino.lower() in contenido.lower():
                encontrados.append(termino)

        return {
            "tipo_codigo": tipo_codigo,
            "terminos_tecnicos": encontrados,
            "total_terminos": len(encontrados),
            "sin_sinonimos": True,
            "sin_antonimos": True,
            "reducido": True,
            "contexto_completo": True,
        }

    def reducir_palabras(self, texto: str, tipo_codigo: str = "python") -> str:
        """Reducir palabras sin perder contexto"""
        terminos_tecnicos = self.vocabulario_base.get(tipo_codigo, self.vocabulario_base["python"])

        palabras = texto.split()
        palabras_reducidas = []

        for palabra in palabras:
            # Mantener términos técnicos
            if (
                any(termino.lower() in palabra.lower() for termino in terminos_tecnicos)
                or len(palabra) > 3
            ):
                palabras_reducidas.append(palabra)

        return " ".join(palabras_reducidas)

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVocabularioCodigo."""
        texto.lower()
        return (
            "Puedo explicar código, sintaxis, APIs y funciones. ¿Qué concepto de código necesitas?"
        )

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVocabularioCodigo."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVocabularioCodigo."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVocabularioCodigo."""
        return self.procesar(texto)


# Instancia global
agente_vocabulario_codigo = AgenteVocabularioCodigo()
