#!/usr/bin/env python3
"""
Script para añadir métodos genéricos (procesar, ejecutar, consultar, responder) a los agentes.
"""

import re
from pathlib import Path

# Lista de 50 agentes a modificar
AGENTES = [
    # COCINA (6)
    "agente_cocina_espanola.py",
    "agente_cocina_navarra_temporada.py",
    "agente_gastronomo_musica.py",
    "agente_vocabulario_gastronomico.py",
    "agente_vocabulario_bar.py",
    "agente_media_recetas.py",
    # CONTABILIDAD/FINANZAS (5)
    "agente_administrativo_contable.py",
    "agente_contabilidad.py",
    "agente_facturas.py",
    "agente_banco.py",
    "agente_vocabulario_financiero.py",
    # MARKETING (5)
    "agente_marketing.py",
    "agente_creativo_marketing.py",
    "agente_marketing_temporada_navarra.py",
    "agente_galeria_videos.py",
    "agente_galeria_fotos.py",
    # LEGAL/RRHH (6)
    "agente_juridico.py",
    "agente_laboral.py",
    "agente_rrhh.py",
    "agente_camaras.py",
    "agente_vocabulario_legal.py",
    "agente_policia_v2.py",
    # SISTEMA (7)
    "agente_tailscale.py",
    "agente_automatizador.py",
    "agente_conectividad.py",
    "agente_red_telefonia.py",
    "agente_operativo_hardware.py",
    "agente_scheduler.py",
    "agente_gobierno.py",
    # DOCUMENTOS (8)
    "agente_documentos_pdf.py",
    "agente_documentos_texto.py",
    "agente_documentos_word.py",
    "agente_documentos_excel.py",
    "agente_documentos_presentaciones.py",
    "agente_orquestador_documentacion.py",
    "agente_archivist.py",
    "agente_librarian.py",
    # COMUNICACIÓN (3)
    "agente_email.py",
    "agente_notificaciones.py",
    "agente_conversacion.py",
    # IA/CONOCIMIENTO (8)
    "agente_investigador_ia.py",
    "agente_conciencia.py",
    "agente_memoria.py",
    "agente_lenguaje.py",
    "agente_vocabulario.py",
    "agente_vocabulario_codigo.py",
    "agente_vocabulario_tecnico.py",
    "agente_vision.py",
    # GUI (1)
    "agente_gui.py",
    # ASESORÍA (1)
    "agente_asesor.py",
]


def agregar_metodos_genericos(archivo: Path):
    """Añade métodos genéricos a un agente si no los tiene."""
    contenido = archivo.read_text()

    # Verificar si ya tiene los métodos
    if "def procesar(self" in contenido:
        print(f"  ✓ {archivo.name} ya tiene métodos genéricos")
        return False

    # Buscar la última definición de método
    # Patrón: buscar def ...(...):
    metodos = re.findall(r"^    def \w+\(", contenido, re.MULTILINE)

    if not metodos:
        print(f"  ✗ {archivo.name} no tiene métodos")
        return False

    # Extraer nombre de la clase
    clase_match = re.search(r"class (\w+):", contenido)
    if not clase_match:
        print(f"  ✗ {archivo.name} no tiene clase")
        return False

    nombre_clase = clase_match.group(1)
    nombre_clase.replace("Agente", "").replace("Agent", "").lower()

    # Generar métodos genéricos
    metodos_genericos = f'''
    def procesar(self, texto: str) -> str:
        """Procesar consulta para {nombre_clase}."""
        texto_lower = texto.lower()
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

    # Buscar el final de la clase (antes de if __name__ == "__main__")
    if "__main__" in contenido:
        # Insertar antes de if __name__
        contenido = contenido.replace(
            'if __name__ == "__main__":', metodos_genericos + '\nif __name__ == "__main__":'
        )
    else:
        # Añadir al final
        contenido += metodos_genericos

    archivo.write_text(contenido)
    print(f"  ✓ {archivo.name} métodos añadidos")
    return True


def main():
    agents_dir = Path("/Users/ramonesnaola/URA/ura_ia_1972/agents")
    modificados = 0

    for agente in AGENTES:
        archivo = agents_dir / agente
        if archivo.exists():
            if agregar_metodos_genericos(archivo):
                modificados += 1
        else:
            print(f"  ✗ {agente} no encontrado")

    print(f"\nTotal: {modificados} agentes modificados")


if __name__ == "__main__":
    main()
