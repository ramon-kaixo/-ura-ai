#!/usr/bin/env python3
"""
Gestión de Dependencias URA
Vulnerability scanning y updates
"""

import json
import subprocess
from pathlib import Path

REQUIREMENTS_PATH = Path(__file__).parent.parent / "requirements.txt"


class GestorDependencias:
    """Gestor de dependencias"""

    def __init__(self):
        self.requirements_path = REQUIREMENTS_PATH

    def obtener_dependencias(self) -> list[dict]:
        """Obtiene lista de dependencias"""
        if not self.requirements_path.exists():
            return []

        dependencias = []
        with open(self.requirements_path) as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#"):
                    # Parsear nombre y versión
                    if "==" in linea:
                        nombre, version = linea.split("==")
                    else:
                        nombre = linea
                        version = None

                    dependencias.append({"nombre": nombre, "version": version, "linea": linea})

        return dependencias

    def escanear_vulnerabilidades(self) -> dict:
        """Escanea vulnerabilidades usando safety"""
        try:
            result = subprocess.run(
                ["safety", "check", "-r", str(self.requirements_path), "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return {"vulnerabilidades": [], "seguro": True}

            try:
                vulnerabilidades = json.loads(result.stdout)
                return {"vulnerabilidades": vulnerabilidades, "seguro": False}
            except:
                return {"error": "Error parsing safety output"}
        except FileNotFoundError:
            return {"error": "Safety no instalado", "instalar": "pip install safety"}
        except Exception as e:
            return {"error": str(e)}

    def verificar_actualizaciones(self) -> dict:
        """Verifica actualizaciones disponibles"""
        try:
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            try:
                actualizaciones = json.loads(result.stdout)
                return {"actualizaciones": actualizaciones}
            except:
                return {"actualizaciones": []}
        except Exception as e:
            return {"error": str(e)}

    def generar_grafo_dependencias(self) -> dict:
        """Genera grafo de dependencias"""
        dependencias = self.obtener_dependencias()

        nodos = [d["nombre"] for d in dependencias]
        aristas = []  # Simplificado - requeriría pipdeptree

        return {"nodos": nodos, "aristas": aristas, "total_dependencias": len(dependencias)}

    def verificar_licencias(self) -> dict:
        """Verifica compliance de licencias"""
        try:
            result = subprocess.run(
                ["pip-licenses", "--format=json"], capture_output=True, text=True, timeout=30
            )

            try:
                licencias = json.loads(result.stdout)
                return {"licencias": licencias}
            except:
                return {"licencias": []}
        except FileNotFoundError:
            return {"error": "pip-licenses no instalado", "instalar": "pip install pip-licenses"}
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    print("=" * 50)
    print("GESTIÓN DE DEPENDENCIAS")
    print("=" * 50)

    gestor = GestorDependencias()

    # Dependencias
    deps = gestor.obtener_dependencias()
    print(f"\n📦 Dependencias: {len(deps)}")
    for d in deps[:10]:
        print(f"   - {d['nombre']} {d['version'] or ''}")

    # Vulnerabilidades
    vuln = gestor.escanear_vulnerabilidades()
    print("\n🔒 Vulnerabilidades:")
    if "vulnerabilidades" in vuln:
        print(f"   Seguro: {vuln['seguro']}")
    else:
        print(f"   {vuln.get('error', 'Error')}")

    # Actualizaciones
    actualizaciones = gestor.verificar_actualizaciones()
    if "actualizaciones" in actualizaciones:
        print(f"\n📈 Actualizaciones disponibles: {len(actualizaciones['actualizaciones'])}")

    print("\n✅ Gestión de dependencias OK")
