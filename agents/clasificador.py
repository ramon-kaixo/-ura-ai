#!/usr/bin/env python3
"""
Clasificador - La puerta de entrada al sistema URA
Sin él nada entra al sistema
"""

import hashlib
from datetime import datetime

CLASIFICACIONES = {
    "CRITICO": [
        "banco",
        "pago",
        "factura",
        "transferencia",
        "password",
        "dni",
        "tarjeta",
        "credito",
        "hipoteca",
        "cripto",
        "binance",
        "kraken",
        "coinbase",
    ],
    "SENSIBLE": [
        "documento",
        "contrato",
        "legal",
        "fiscal",
        "contabilidad",
        "nomina",
        "curriculum",
        "medico",
        "salud",
    ],
    "PUBLICO": ["receta", "imagen", "video", "audio", "libro", "articulo", "nota", "juego"],
    "SISTEMA": ["config", "log", "backup", "script", "code"],
}


class Clasificador:
    """El clasificador decide qué tipo de contenido es cada cosa"""

    def __init__(self):
        self.historial = []
        self.contador = 0

    def clasificar(self, texto: str, contexto: str = "") -> dict:
        """Clasifica el contenido y devuelve el nivel de seguridad"""

        self.contador += 1
        ahora = datetime.now().isoformat()

        texto_lower = texto.lower() + " " + contexto.lower()

        nivel = "PUBLICO"
        etiquetas = []

        for nivel_name, palabras in CLASIFICACIONES.items():
            for palabra in palabras:
                if palabra in texto_lower:
                    if nivel_name == "CRITICO":
                        nivel = "CRITICO"
                    elif nivel_name == "SENSIBLE" and nivel != "CRITICO":
                        nivel = "SENSIBLE"
                    etiquetas.append(palabra)
                    break

        hash_contenido = hashlib.sha256(texto.encode()).hexdigest()[:16]

        resultado = {
            "id": f"CLS-{self.contador:06d}",
            "timestamp": ahora,
            "nivel": nivel,
            "etiquetas": list(set(etiquetas)),
            "hash": hash_contenido,
            "resumen": f"{nivel}:{len(texto)} chars",
        }

        self.historial.append(resultado)

        return resultado

    def puede_pasar(self, nivel: str, nivel_requerido: str) -> bool:
        """Determina si puede pasar a la siguiente zona"""

        orden = {"PUBLICO": 0, "SISTEMA": 1, "SENSIBLE": 2, "CRITICO": 3}

        return orden.get(nivel, 0) <= orden.get(nivel_requerido, 0)

    def estadisticas(self) -> dict:
        """Devuelve estadísticas del clasificador"""

        return {
            "total_procesado": self.contador,
            "por_nivel": {
                "CRITICO": len([h for h in self.historial if h["nivel"] == "CRITICO"]),
                "SENSIBLE": len([h for h in self.historial if h["nivel"] == "SENSIBLE"]),
                "PUBLICO": len([h for h in self.historial if h["nivel"] == "PUBLICO"]),
                "SISTEMA": len([h for h in self.historial if h["nivel"] == "SISTEMA"]),
            },
        }


_clasificador = None


def get_clasificador() -> Clasificador:
    global _clasificador
    if _clasificador is None:
        _clasificador = Clasificador()
    return _clasificador


if __name__ == "__main__":
    cls = get_clasificador()

    pruebas = [
        ("Voy a transferir 500€ al banco", "pago"),
        ("Contrato de trabajo.pdf", "documento legal"),
        ("Receta de paella.txt", "cocina"),
        ("Contraseña de mi banco.txt", "password banco"),
        ("Script de backup.py", "sistema"),
    ]

    print("=" * 60)
    print("🚪 CLASIFICADOR - PUERTA DE ENTRADA")
    print("=" * 60)

    for texto, contexto in pruebas:
        resultado = cls.clasificar(texto, contexto)
        print(f"\n📝 {texto}")
        print(f"   → Nivel: {resultado['nivel']}")
        print(f"   → Etiquetas: {resultado['etiquetas']}")
        print(f"   → Hash: {resultado['hash']}")

    print("\n" + "=" * 60)
    stats = cls.estadisticas()
    print(f"📊 Total procesado: {stats['total_procesado']}")
    print(f"   CRITICO: {stats['por_nivel']['CRITICO']}")
    print(f"   SENSIBLE: {stats['por_nivel']['SENSIBLE']}")
    print(f"   PUBLICO: {stats['por_nivel']['PUBLICO']}")
    print(f"   SISTEMA: {stats['por_nivel']['SISTEMA']}")
