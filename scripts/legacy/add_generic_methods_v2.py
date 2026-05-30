#!/usr/bin/env python3
"""
Script mejorado para añadir métodos genéricos a los agentes.
Maneja archivos sin clase (crea wrapper) y con clase (añade métodos).
"""

from pathlib import Path

# Lista de agentes que necesitan corrección manual
AGENTES_SIN_CLASE = [
    "agente_vocabulario_gastronomico.py",
    "agente_vocabulario_bar.py",
    "agente_media_recetas.py",
    "agente_vocabulario_financiero.py",
    "agente_galeria_videos.py",
    "agente_galeria_fotos.py",
    "agente_vocabulario_legal.py",
    "agente_documentos_pdf.py",
    "agente_documentos_texto.py",
    "agente_documentos_word.py",
    "agente_documentos_excel.py",
    "agente_documentos_presentaciones.py",
    "agente_orquestador_documentacion.py",
    "agente_vocabulario_tecnico.py",
    "agente_vision.py",
]

AGENTES_SIN_CLASE_NOMBRE = {
    "agente_vocabulario_gastronomico.py": "AgenteVocabularioGastronomico",
    "agente_vocabulario_bar.py": "AgenteVocabularioBar",
    "agente_media_recetas.py": "AgenteMediaRecetas",
    "agente_vocabulario_financiero.py": "AgenteVocabularioFinanciero",
    "agente_galeria_videos.py": "AgenteGaleriaVideos",
    "agente_galeria_fotos.py": "AgenteGaleriaFotos",
    "agente_vocabulario_legal.py": "AgenteVocabularioLegal",
    "agente_documentos_pdf.py": "AgenteDocumentosPDF",
    "agente_documentos_texto.py": "AgenteDocumentosTexto",
    "agente_documentos_word.py": "AgenteDocumentosWord",
    "agente_documentos_excel.py": "AgenteDocumentosExcel",
    "agente_documentos_presentaciones.py": "AgenteDocumentosPresentaciones",
    "agente_orquestador_documentacion.py": "AgenteOrquestadorDocumentacion",
    "agente_vocabulario_tecnico.py": "AgenteVocabularioTecnico",
    "agente_vision.py": "AgenteVision",
}


def agregar_clase_wrapper(archivo: Path, nombre_clase: str):
    """Añade una clase wrapper a archivos que solo tienen funciones."""
    contenido = archivo.read_text()

    # Verificar si ya tiene clase
    if "class " in contenido:
        print(f"  ✓ {archivo.name} ya tiene clase")
        return False

    # Buscar if __name__ == "__main__"
    if "__main__" in contenido:
        # Insertar clase antes de if __name__
        wrapper = f'''
class {nombre_clase}:
    """Wrapper para {nombre_clase}."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para {nombre_clase}."""
        return f"Agente {nombre_clase} procesando: {{texto}}"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para {nombre_clase}."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para {nombre_clase}."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para {nombre_clase}."""
        return self.procesar(texto)

'''
        contenido = contenido.replace(
            'if __name__ == "__main__":', wrapper + 'if __name__ == "__main__":'
        )
    else:
        # Añadir al final
        wrapper = f'''
class {nombre_clase}:
    """Wrapper para {nombre_clase}."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para {nombre_clase}."""
        return f"Agente {nombre_clase} procesando: {{texto}}"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para {nombre_clase}."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para {nombre_clase}."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para {nombre_clase}."""
        return self.procesar(texto)

'''
        contenido += wrapper

    archivo.write_text(contenido)
    print(f"  ✓ {archivo.name} clase wrapper añadida")
    return True


def main():
    agents_dir = Path("/Users/ramonesnaola/URA/ura_ia_1972/agents")
    modificados = 0

    for agente in AGENTES_SIN_CLASE:
        archivo = agents_dir / agente
        nombre_clase = AGENTES_SIN_CLASE_NOMBRE.get(
            agente,
            "Agente" + agente.replace("agente_", "").replace(".py", "").title().replace("_", ""),
        )

        if archivo.exists():
            if agregar_clase_wrapper(archivo, nombre_clase):
                modificados += 1
        else:
            print(f"  ✗ {agente} no encontrado")

    print(f"\nTotal: {modificados} agentes modificados")


if __name__ == "__main__":
    main()
