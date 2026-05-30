#!/usr/bin/env python3
"""
Instalador Automático de Servicios URA
Instala y configura servicios automáticamente
"""

import subprocess
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent


class InstaladorServicios:
    """Instalador automático de servicios"""

    def __init__(self):
        self.project_dir = PROJECT_DIR

    def verificar_docker(self) -> bool:
        """Verifica si Docker está instalado y corriendo"""
        try:
            subprocess.run(["docker", "version"], capture_output=True, check=True)
            return True
        except:
            return False

    def verificar_redis(self) -> bool:
        """Verifica si Redis está corriendo"""
        try:
            subprocess.run(["redis-cli", "ping"], capture_output=True, check=True)
            return True
        except:
            return False

    def iniciar_redis(self) -> bool:
        """Inicia Redis"""
        try:
            subprocess.run(["redis-server", "--daemonize yes"], check=True)
            time.sleep(2)
            return self.verificar_redis()
        except Exception as e:
            print(f"❌ Error iniciando Redis: {e}")
            return False

    def iniciar_postgresql_docker(self, nombre: str = "ura_postgres") -> bool:
        """Inicia PostgreSQL en Docker"""
        try:
            # Verificar si contenedor existe
            result = subprocess.run(
                ["docker", "ps", "-a", "-q", "-f", f"name={nombre}"], capture_output=True, text=True
            )

            if result.stdout.strip():
                # Contenedor existe, iniciarlo
                subprocess.run(["docker", "start", nombre], check=True)
            else:
                # Crear nuevo contenedor
                subprocess.run(
                    [
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        nombre,
                        "-e",
                        "POSTGRES_PASSWORD=ura_password",
                        "-e",
                        "POSTGRES_DB=ura_db",
                        "-p",
                        "5432:5432",
                        "postgres:15",
                    ],
                    check=True,
                )

            time.sleep(5)
            return True
        except Exception as e:
            print(f"❌ Error iniciando PostgreSQL: {e}")
            return False

    def iniciar_grafana_docker(self, nombre: str = "ura_grafana") -> bool:
        """Inicia Grafana en Docker"""
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "-q", "-f", f"name={nombre}"], capture_output=True, text=True
            )

            if result.stdout.strip():
                subprocess.run(["docker", "start", nombre], check=True)
            else:
                subprocess.run(
                    ["docker", "run", "-d", "--name", nombre, "-p", "3000:3000", "grafana/grafana"],
                    check=True,
                )

            time.sleep(5)
            return True
        except Exception as e:
            print(f"❌ Error iniciando Grafana: {e}")
            return False

    def iniciar_prometheus_docker(self, nombre: str = "ura_prometheus") -> bool:
        """Inicia Prometheus en Docker"""
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "-q", "-f", f"name={nombre}"], capture_output=True, text=True
            )

            if result.stdout.strip():
                subprocess.run(["docker", "start", nombre], check=True)
            else:
                subprocess.run(
                    ["docker", "run", "-d", "--name", nombre, "-p", "9090:9090", "prom/prometheus"],
                    check=True,
                )

            time.sleep(5)
            return True
        except Exception as e:
            print(f"❌ Error iniciando Prometheus: {e}")
            return False

    def iniciar_ollama_docker(self, nombre: str = "ura_ollama") -> bool:
        """Inicia Ollama en Docker"""
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "-q", "-f", f"name={nombre}"], capture_output=True, text=True
            )

            if result.stdout.strip():
                subprocess.run(["docker", "start", nombre], check=True)
            else:
                subprocess.run(
                    [
                        "docker",
                        "run",
                        "-d",
                        "--name",
                        nombre,
                        "-p",
                        "11434:11434",
                        "-v",
                        "ollama:/root/.ollama",
                        "ollama/ollama",
                    ],
                    check=True,
                )

            time.sleep(5)
            return True
        except Exception as e:
            print(f"❌ Error iniciando Ollama: {e}")
            return False

    def iniciar_todos_servicios(self) -> dict:
        """Inicia todos los servicios"""
        resultados = {}

        print("🚀 Iniciando servicios...")

        # Redis
        print("   Redis...")
        resultados["redis"] = self.iniciar_redis()

        # PostgreSQL
        print("   PostgreSQL...")
        resultados["postgresql"] = self.iniciar_postgresql_docker()

        # Grafana
        print("   Grafana...")
        resultados["grafana"] = self.iniciar_grafana_docker()

        # Prometheus
        print("   Prometheus...")
        resultados["prometheus"] = self.iniciar_prometheus_docker()

        # Ollama
        print("   Ollama...")
        resultados["ollama"] = self.iniciar_ollama_docker()

        return resultados


if __name__ == "__main__":
    instalador = InstaladorServicios()
    resultados = instalador.iniciar_todos_servicios()

    print("\n📊 Resultados:")
    for servicio, estado in resultados.items():
        emoji = "✅" if estado else "❌"
        print(f"   {emoji} {servicio}: {estado}")
