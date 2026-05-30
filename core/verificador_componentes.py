#!/usr/bin/env python3
"""
Verificador de Componentes URA
Verifica que todos los componentes funcionen correctamente
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import redis
import requests

PROJECT_DIR = Path(__file__).parent.parent
DB_PATH = PROJECT_DIR / "board.db"


class VerificadorComponentes:
    """Verificador de componentes del sistema"""

    def __init__(self):
        self.db_path = DB_PATH

    def verificar_base_datos(self) -> dict:
        """Verifica base de datos"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT 1")
            conn.close()
            return {"componente": "bd", "estado": "saludable"}
        except Exception as e:
            return {"componente": "bd", "estado": "fallo", "error": str(e)}

    def verificar_redis(self) -> dict:
        """Verifica Redis"""
        try:
            r = redis.Redis(host="localhost", port=6379, decode_responses=True)
            r.ping()
            return {"componente": "redis", "estado": "saludable"}
        except Exception as e:
            return {"componente": "redis", "estado": "fallo", "error": str(e)}

    def verificar_ollama(self) -> dict:
        """Verifica Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                return {"componente": "ollama", "estado": "saludable"}
            return {"componente": "ollama", "estado": "fallo", "error": "HTTP error"}
        except Exception as e:
            return {"componente": "ollama", "estado": "fallo", "error": str(e)}

    def verificar_grafana(self) -> dict:
        """Verifica Grafana"""
        try:
            response = requests.get("http://localhost:3000/api/health", timeout=5)
            if response.status_code == 200:
                return {"componente": "grafana", "estado": "saludable"}
            return {"componente": "grafana", "estado": "fallo", "error": "HTTP error"}
        except Exception as e:
            return {"componente": "grafana", "estado": "fallo", "error": str(e)}

    def verificar_prometheus(self) -> dict:
        """Verifica Prometheus"""
        try:
            response = requests.get("http://localhost:9090/-/healthy", timeout=5)
            if response.status_code == 200:
                return {"componente": "prometheus", "estado": "saludable"}
            return {"componente": "prometheus", "estado": "fallo", "error": "HTTP error"}
        except Exception as e:
            return {"componente": "prometheus", "estado": "fallo", "error": str(e)}

    def verificar_archivos_core(self) -> dict:
        """Verifica archivos core"""
        core_dir = PROJECT_DIR / "core"
        archivos = list(core_dir.glob("*.py"))

        return {
            "componente": "archivos_core",
            "estado": "saludable" if len(archivos) > 0 else "fallo",
            "cantidad": len(archivos),
        }

    def verificar_todos(self) -> dict:
        """Verifica todos los componentes"""
        resultados = [
            self.verificar_base_datos(),
            self.verificar_redis(),
            self.verificar_ollama(),
            self.verificar_grafana(),
            self.verificar_prometheus(),
            self.verificar_archivos_core(),
        ]

        saludables = sum(1 for r in resultados if r["estado"] == "saludable")

        return {
            "timestamp": datetime.now().isoformat(),
            "total_componentes": len(resultados),
            "saludables": saludables,
            "fallos": len(resultados) - saludables,
            "detalles": resultados,
        }


if __name__ == "__main__":
    verificador = VerificadorComponentes()

    resultado = verificador.verificar_todos()

    print("=" * 50)
    print("VERIFICACIÓN DE COMPONENTES")
    print("=" * 50)

    print("\n📊 Resumen:")
    print(f"   Saludables: {resultado['saludables']}/{resultado['total_componentes']}")
    print(f"   Fallos: {resultado['fallos']}")

    print("\n🔍 Detalles:")
    for r in resultado["detalles"]:
        emoji = "✅" if r["estado"] == "saludable" else "❌"
        print(f"   {emoji} {r['componente']}: {r['estado']}")
