#!/usr/bin/env python3
"""
Sistema de Automatización de Dependencias URA
Detecta, instala y configura todas las dependencias automáticamente
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent


class AutomatizadorDependencias:
    """Automatizador de dependencias"""

    def __init__(self):
        self.project_dir = PROJECT_DIR
        self.dependencias = {
            "python": {
                "paquetes": [
                    "psutil",
                    "redis",
                    "requests",
                    "flask",
                    "flask-cors",
                    "safety",
                    "pip-licenses",
                    "pytest",
                    "pytest-cov",
                ],
                "instalado": False,
            },
            "redis": {
                "comando": "redis-server",
                "instalado": False,
                "instalacion": "brew install redis",
            },
            "docker": {
                "comando": "docker",
                "instalado": False,
                "instalacion": "brew install docker",
            },
        }

    def verificar_paquete_python(self, paquete: str) -> bool:
        """Verifica si un paquete Python está instalado"""
        try:
            __import__(paquete)
            return True
        except ImportError:
            return False

    def verificar_comando_sistema(self, comando: str) -> bool:
        """Verifica si un comando del sistema está instalado"""
        try:
            subprocess.run(["which", comando], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def instalar_paquete_python(self, paquete: str) -> bool:
        """Instala paquete Python"""
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", paquete],
                capture_output=True,
                check=True,
                timeout=300,
            )
            return True
        except Exception as e:
            print(f"❌ Error instalando {paquete}: {e}")
            return False

    def detectar_dependencias_faltantes(self) -> dict[str, list[str]]:
        """Detecta dependencias faltantes"""
        faltantes = {"python": [], "sistema": []}

        # Paquetes Python
        for paquete in self.dependencias["python"]["paquetes"]:
            if not self.verificar_paquete_python(paquete):
                faltantes["python"].append(paquete)

        # Comandos del sistema
        for nombre, info in self.dependencias.items():
            if nombre != "python" and "comando" in info:
                if not self.verificar_comando_sistema(info["comando"]):
                    faltantes["sistema"].append(nombre)

        return faltantes

    def instalar_dependencias_faltantes(
        self, faltantes: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        """Instala dependencias faltantes"""
        instalados = {"python": [], "sistema": []}
        errores = []

        # Instalar paquetes Python
        for paquete in faltantes["python"]:
            if self.instalar_paquete_python(paquete):
                instalados["python"].append(paquete)
            else:
                errores.append(paquete)

        # Comandos del sistema (requieren intervención manual)
        for nombre in faltantes["sistema"]:
            info = self.dependencias[nombre]
            print(f"⚠️ {nombre} requiere instalación manual: {info['instalacion']}")

        return {
            "instalados": instalados,
            "requieren_instalacion_manual": faltantes["sistema"],
            "errores": errores,
        }

    def generar_script_instalacion(self) -> str:
        """Genera script de instalación para dependencias del sistema"""
        script = """#!/bin/bash
# Script de instalación de dependencias del sistema URA

echo "Instalando dependencias del sistema..."

# Redis
if ! command -v redis-server &> /dev/null; then
    echo "Instalando Redis..."
    brew install redis
fi

# Docker
if ! command -v docker &> /dev/null; then
    echo "Instalando Docker..."
    brew install docker
fi

echo "✅ Dependencias del sistema instaladas"
"""
        return script

    def ejecutar_instalacion_automatica(self) -> dict:
        """Ejecuta instalación automática completa"""
        print("=" * 50)
        print("AUTOMATIZACIÓN DE DEPENDENCIAS URA")
        print("=" * 50)

        # Detectar faltantes
        faltantes = self.detectar_dependencias_faltantes()

        print("\n🔍 Dependencias faltantes:")
        print(f"   Python: {len(faltantes['python'])}")
        print(f"   Sistema: {len(faltantes['sistema'])}")

        # Instalar automáticamente
        resultado = self.instalar_dependencias_faltantes(faltantes)

        print("\n✅ Instalados automáticamente:")
        for p in resultado["instalados"]["python"]:
            print(f"   - {p}")

        print("\n⚠️ Requieren instalación manual:")
        for s in resultado["requieren_instalacion_manual"]:
            info = self.dependencias[s]
            print(f"   - {s}: {info['instalacion']}")

        # Generar script de instalación manual
        script = self.generar_script_instalacion()
        script_path = self.project_dir / "install_system_deps.sh"
        with open(script_path, "w") as f:
            f.write(script)

        print(f"\n📄 Script de instalación generado: {script_path}")

        return resultado


if __name__ == "__main__":
    automatizador = AutomatizadorDependencias()
    resultado = automatizador.ejecutar_instalacion_automatica()
    print(f"\n📊 Resultado: {json.dumps(resultado, indent=2)}")
