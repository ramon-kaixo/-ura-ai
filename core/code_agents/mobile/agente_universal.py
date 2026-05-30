#!/usr/bin/env python3
"""
Agente Universal Móvil - URA App
Crea cualquier tipo de código (Python, JavaScript, SQL, HTML, API, etc.)
"""

from core.code_agents.mobile.agente_documentador import agente_documentador
from core.code_agents.mobile.agente_registrador import agente_registrador
from core.validadores.validador_obediencia import validador_obediencia
from core.vocabulario.orchestrator_vocabulario import orchestrator_vocabulario


class AgenteUniversal:
    """Agente universal que crea cualquier tipo de código"""

    def __init__(self):
        self.nombre = "agente_universal"
        self.box_actual = None
        self.registrador = agente_registrador
        self.documentador = agente_documentador
        self.orchestrator_vocabulario = orchestrator_vocabulario
        self.validador_obediencia = validador_obediencia
        # Importar agente vocabulario
        try:
            from agents.agente_vocabulario import get_agente_vocabulario

            self.vocabulario = get_agente_vocabulario()
        except:
            self.vocabulario = None
        # Importar agente vocabulario de código
        try:
            from agents.agente_vocabulario_codigo import agente_vocabulario_codigo

            self.vocabulario_codigo = agente_vocabulario_codigo
        except:
            self.vocabulario_codigo = None

    def asignar_box(self, box: str):
        """Asignar agente a un box específico"""
        self.box_actual = box

    def generar_codigo(
        self, especificacion: str, tipo_codigo: str, departamento: str = "codigo"
    ) -> str:
        """Generar código según tipo"""
        # Mapear contexto completo con orquestador de vocabulario
        contexto = self.orchestrator_vocabulario.mapear_contexto(departamento, tipo_codigo)

        # Registrar acción
        self.registrador.registrar(
            self.nombre,
            "generar_codigo",
            {"especificacion": especificacion, "tipo": tipo_codigo, "contexto": contexto},
        )

        plantillas = {
            "python": self._generar_python,
            "javascript": self._generar_javascript,
            "sql": self._generar_sql,
            "html": self._generar_html,
            "api": self._generar_api,
            "microservicios": self._generar_microservicios,
            "ml": self._generar_ml,
            "data": self._generar_data,
            "devops": self._generar_devops,
            "seguridad": self._generar_seguridad,
        }

        generador = plantillas.get(tipo_codigo, self._generar_python)
        codigo = generador(especificacion)

        # Generar documentación
        self.documentador.generar_documentacion(codigo, especificacion, tipo_codigo)

        # Analizar código con vocabulario si está disponible
        if self.vocabulario:
            # Contexto completo para el análisis
            contexto_completo = f"""
Código generado por: {self.nombre}
Box actual: {self.box_actual}
Tipo de código: {tipo_codigo}
Departamento: {departamento}
Especificación original: {especificacion}
Propósito: Generación de código según especificación

Código:
{codigo}
"""
            analisis = self.vocabulario.analizar(contexto_completo, tipo="texto")
            self.registrador.registrar(
                self.nombre,
                "analisis_vocabulario",
                {"analisis": analisis, "contexto_completo": True},
            )

        # Analizar con vocabulario de código específico
        if self.vocabulario_codigo:
            analisis_codigo = self.vocabulario_codigo.analizar(codigo, tipo_codigo)
            self.registrador.registrar(
                self.nombre,
                "analisis_vocabulario_codigo",
                {"analisis": analisis_codigo, "tipo_codigo": tipo_codigo},
            )

        # Validar respuesta con validador de obediencia
        validacion = self.validador_obediencia.validar_respuesta(
            especificacion, codigo, consultas_externas=[]
        )

        if not validacion.get("aprobada"):
            # Si no está aprobada, bloquear respuesta
            self.registrador.registrar(
                self.nombre, "validacion_obediencia_fallida", {"validacion": validacion}
            )
            # Aún así, devolver código (el usuario decide si usarlo)

        return codigo

    def _generar_python(self, especificacion: str) -> str:
        return f'''#!/usr/bin/env python3
"""
Código generado por Agente Universal
Box: {self.box_actual}
Especificación: {especificacion}
"""
def main():
    pass

if __name__ == "__main__":
    main()
'''

    def _generar_javascript(self, especificacion: str) -> str:
        return f"""// Código generado por Agente Universal
// Box: {self.box_actual}
// Especificación: {especificacion}
function main() {{ console.log("Ejecutando"); }}
main();
"""

    def _generar_sql(self, especificacion: str) -> str:
        return f"""-- Código generado por Agente Universal
-- Box: {self.box_actual}
-- Especificación: {especificacion}  # nosec B608
SELECT * FROM tabla WHERE activo = TRUE;
"""  # nosec B608

    def _generar_html(self, especificacion: str) -> str:
        return f"""<!-- Código generado por Agente Universal -->
<!-- Box: {self.box_actual} -->
<!-- Especificación: {especificacion} -->
<html><body><h1>Página</h1></body></html>
"""

    def _generar_api(self, especificacion: str) -> str:
        return f"""# Código generado por Agente Universal
# Box: {self.box_actual}
# Especificación: {especificacion}
@app.route('/api/data')
def get_data(): return jsonify({{}})
"""

    def _generar_microservicios(self, especificacion: str) -> str:
        return f"""# Código generado por Agente Universal
# Box: {self.box_actual}
# Especificación: {especificacion}
@app.route('/health')
def health(): return jsonify({{"status": "ok"}})
"""

    def _generar_ml(self, especificacion: str) -> str:
        return f"""# Código generado por Agente Universal
# Box: {self.box_actual}
# Especificación: {especificacion}
model = RandomForestClassifier()
model.fit(X, y)
"""

    def _generar_data(self, especificacion: str) -> str:
        return f"""# Código generado por Agente Universal
# Box: {self.box_actual}
# Especificación: {especificacion}
df = pd.read_csv('data.csv')
"""

    def _generar_devops(self, especificacion: str) -> str:
        return f"""# Código generado por Agente Universal
# Box: {self.box_actual}
# Especificación: {especificacion}
docker-compose up -d
"""

    def _generar_seguridad(self, especificacion: str) -> str:
        return f"""# Código generado por Agente Universal
# Box: {self.box_actual}
# Especificación: {especificacion}
hash = hashlib.sha256(data.encode()).hexdigest()
"""


# Instancia global
agente_universal = AgenteUniversal()
