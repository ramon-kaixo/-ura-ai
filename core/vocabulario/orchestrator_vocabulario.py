#!/usr/bin/env python3
"""
Orquestador de Vocabulario - URA App
Coordina todos los agentes de vocabulario por departamento
"""


class OrchestadorVocabulario:
    """Coordina agentes de vocabulario por departamento"""

    def __init__(self):
        self.nombre = "orchestrator_vocabulario"
        self.departamentos = {
            "tecnologia": "agente_vocabulario_tecnico",
            "legal": "agente_vocabulario_legal",
            "financiero": "agente_vocabulario_financiero",
            "hosteleria": "agente_vocabulario_bar",
            "gastronomia": "agente_vocabulario_gastronomico",
            "codigo": "agente_vocabulario_codigo",  # NUEVO
        }

        self.subagentes = {
            "tecnologia": ["frontend", "backend", "devops", "seguridad"],
            "codigo": ["python", "javascript", "sql", "api", "ml"],
        }

        self.herramientas_vocabulario = {
            "black": "python",
            "isort": "python",
            "ruff": "python",
            "mypy": "python",
            "bandit": "seguridad",
            "pylint": "python",
        }

        # Importar guardrails
        try:
            from core.vocabulario.guardrails_vocabulario import guardrails_vocabulario

            self.guardrails = guardrails_vocabulario
        except:
            self.guardrails = None

    def obtener_vocabulario_departamento(self, departamento: str) -> str | None:
        """Obtener agente de vocabulario para un departamento"""
        return self.departamentos.get(departamento)

    def obtener_subagentes(self, departamento: str) -> list:
        """Obtener subagentes de un departamento"""
        return self.subagentes.get(departamento, [])

    def obtener_vocabulario_herramienta(self, herramienta: str) -> str | None:
        """Obtener vocabulario asociado a una herramienta"""
        return self.herramientas_vocabulario.get(herramienta)

    def mapear_contexto(self, departamento: str, tipo_codigo: str, box: str = None) -> dict:
        """Mapear contexto completo para un agente móvil con validación"""
        vocabulario_departamento = self.obtener_vocabulario_departamento(departamento)
        vocabulario_codigo = self.obtener_vocabulario_departamento("codigo")
        subagentes = self.obtener_subagentes(departamento)

        # Validar contexto con guardrails
        if self.guardrails:
            validacion = self.guardrails.validar_contexto(
                departamento, tipo_codigo, box or "desarrollo"
            )
            if not validacion["valido"]:
                return {
                    "departamento": departamento,
                    "vocabulario_departamento": vocabulario_departamento,
                    "vocabulario_codigo": vocabulario_codigo,
                    "tipo_codigo": tipo_codigo,
                    "subagentes": subagentes,
                    "contexto_completo": False,
                    "errores_validacion": validacion["errores"],
                }

        return {
            "departamento": departamento,
            "vocabulario_departamento": vocabulario_departamento,
            "vocabulario_codigo": vocabulario_codigo,
            "tipo_codigo": tipo_codigo,
            "subagentes": subagentes,
            "contexto_completo": True,
        }


# Instancia global
orchestrator_vocabulario = OrchestadorVocabulario()
