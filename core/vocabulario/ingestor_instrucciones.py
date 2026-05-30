#!/usr/bin/env python3
"""
Ingestor de Instrucciones - URA App
Lee instrucciones de herramientas y programas para llenar biblioteca de vocabulario
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path


class IngestorInstrucciones:
    """Ingesta instrucciones de herramientas y programas"""

    def __init__(self):
        self.nombre = "ingestor_instrucciones"
        self.biblioteca_path = Path("/Users/ramonesnaola/URA/ura_ia_1972/biblioteca/vocabulario")
        self.biblioteca_path.mkdir(parents=True, exist_ok=True)

        # Mapeo de herramientas a comandos de ayuda
        self.comandos_ayuda = {
            "black": "black --help",
            "isort": "isort --help",
            "ruff": "ruff --help",
            "mypy": "mypy --help",
            "bandit": "bandit --help",
            "pylint": "pylint --help",
            "ollama": "ollama --help",
            "redis-cli": "redis-cli --help",
        }

    def obtener_ayuda_herramienta(self, herramienta: str) -> str | None:
        """Obtener ayuda de una herramienta"""
        comando = self.comandos_ayuda.get(herramienta)
        if not comando:
            return None

        try:
            result = subprocess.run(comando.split(), capture_output=True, text=True, timeout=30)
            return result.stdout
        except:
            return None

    def extraer_vocabulario(self, ayuda: str, herramienta: str) -> dict:
        """Extraer vocabulario técnico de la ayuda"""
        lineas = ayuda.split("\n")
        terminos_tecnicos = []
        comandos = []

        for linea in lineas:
            # Extraer opciones (ej: --line-length)
            if "--" in linea and len(linea) < 100:
                partes = linea.strip().split()
                for parte in partes:
                    if parte.startswith("--"):
                        termino = parte.replace("--", "").replace("=", "")
                        if len(termino) > 2:
                            terminos_tecnicos.append(
                                {
                                    "termino": termino,
                                    "contexto": f"Opción de {herramienta}",
                                    "ejemplo": parte,
                                }
                            )

            # Extraer comandos de ejemplo
            if herramienta in linea.lower() and len(linea) < 100:
                comandos.append(linea.strip())

        return {
            "fuente": f"instrucciones_{herramienta}",
            "tipo": "herramienta",
            "herramienta": herramienta,
            "terminos_tecnicos": terminos_tecnicos[:20],  # Limitar a 20
            "comandos": comandos[:10],
            "fecha_ingreso": datetime.now().isoformat(),
            "procesado_por": "ingestor_instrucciones",
        }

    def guardar_vocabulario(self, vocabulario: dict, departamento: str):
        """Guardar vocabulario en biblioteca del departamento"""
        departamento_path = self.biblioteca_path / departamento
        departamento_path.mkdir(parents=True, exist_ok=True)

        herramienta = vocabulario["herramienta"]
        archivo = departamento_path / f"{herramienta}_vocabulario.json"

        archivo.write_text(json.dumps(vocabulario, indent=2, ensure_ascii=False))

    def procesar_herramienta(self, herramienta: str, departamento: str):
        """Procesar una herramienta completa"""
        print(f"Procesando {herramienta} para {departamento}...")

        ayuda = self.obtener_ayuda_herramienta(herramienta)
        if not ayuda:
            print(f"  No se pudo obtener ayuda de {herramienta}")
            return

        vocabulario = self.extraer_vocabulario(ayuda, herramienta)
        self.guardar_vocabulario(vocabulario, departamento)

        print(f"  ✅ {len(vocabulario['terminos_tecnicos'])} términos extraídos")

    def procesar_departamento(self, departamento: str, herramientas: list[str]):
        """Procesar todas las herramientas de un departamento"""
        print(f"\n=== PROCESANDO DEPARTAMENTO: {departamento.upper()} ===")

        for herramienta in herramientas:
            self.procesar_herramienta(herramienta, departamento)

    def procesar_codigo(self):
        """Procesar departamento de código"""
        herramientas_codigo = ["black", "isort", "ruff", "mypy", "bandit", "pylint"]
        self.procesar_departamento("codigo", herramientas_codigo)


# Instancia global
ingestor_instrucciones = IngestorInstrucciones()

if __name__ == "__main__":
    ingestor = IngestorInstrucciones()

    print("=" * 60)
    print("📚 INGESTOR DE INSTRUCCIONES")
    print("=" * 60)

    # Procesar departamento de código
    ingestor.procesar_codigo()

    print("\n✅ Ingestión completada")
