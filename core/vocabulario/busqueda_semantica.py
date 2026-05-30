#!/usr/bin/env python3
"""
Búsqueda Semántica de Vocabulario - URA App
Encuentra términos relacionados usando similitud de cadenas
"""

import json
from difflib import get_close_matches
from pathlib import Path


class BusquedaSemantica:
    """Búsqueda semántica de términos"""

    def __init__(self):
        self.nombre = "busqueda_semantica"
        self.biblioteca_path = Path("/Users/ramonesnaola/URA/ura_ia_1972/biblioteca/vocabulario")
        self.terminos_indice = {}
        self._construir_indice()

    def _construir_indice(self):
        """Construir índice de todos los términos"""
        if not self.biblioteca_path.exists():
            return

        for directorio in self.biblioteca_path.iterdir():
            if not directorio.is_dir():
                continue

            for archivo in directorio.glob("*.json"):
                try:
                    datos = json.loads(archivo.read_text())
                    for item in datos.get("terminos_tecnicos", []):
                        termino = item.get("termino", "")
                        if termino:
                            self.terminos_indice[termino] = {
                                "contexto": item.get("contexto"),
                                "ejemplo": item.get("ejemplo"),
                                "herramienta": datos.get("herramienta"),
                                "departamento": directorio.name,
                            }
                except:
                    pass

    def buscar_relacionados(self, termino: str, n: int = 5) -> list:
        """Buscar términos relacionados usando similitud"""
        todos_terminos = list(self.terminos_indice.keys())
        coincidencias = get_close_matches(termino, todos_terminos, n=n, cutoff=0.3)

        resultados = []
        for coincidencia in coincidencias:
            datos = self.terminos_indice[coincidencia]
            resultados.append(
                {
                    "termino": coincidencia,
                    "similitud": self._calcular_similitud(termino, coincidencia),
                    "contexto": datos["contexto"],
                    "ejemplo": datos["ejemplo"],
                    "herramienta": datos["herramienta"],
                    "departamento": datos["departamento"],
                }
            )

        return sorted(resultados, key=lambda x: x["similitud"], reverse=True)

    def _calcular_similitud(self, a: str, b: str) -> float:
        """Calcular similitud entre dos strings"""
        from difflib import SequenceMatcher

        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def buscar_por_contexto(self, contexto: str) -> list:
        """Buscar términos por contexto"""
        resultados = []

        for termino, datos in self.terminos_indice.items():
            if contexto.lower() in datos["contexto"].lower():
                resultados.append(
                    {
                        "termino": termino,
                        "contexto": datos["contexto"],
                        "ejemplo": datos["ejemplo"],
                        "herramienta": datos["herramienta"],
                        "departamento": datos["departamento"],
                    }
                )

        return resultados


# Instancia global
busqueda_semantica = BusquedaSemantica()

if __name__ == "__main__":
    busqueda = BusquedaSemantica()

    print("=" * 60)
    print("🔍 BÚSQUEDA SEMÁNTICA DE VOCABULARIO")
    print("=" * 60)

    # Prueba de búsqueda
    print("\n🔍 Buscando 'formato'...")
    relacionados = busqueda.buscar_relacionados("formato")
    for r in relacionados[:5]:
        print(f"  {r['termino']} ({r['similitud']:.2f}) - {r['herramienta']}")

    print("\n✅ Búsqueda semántica lista")
