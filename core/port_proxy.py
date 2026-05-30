#!/usr/bin/env python3
"""
URA - Sistema de Proxy Local para Puertos (Inteligente)

Sistema para manejar puertos conflictivos usando socat:

¿QUÉ ES PROXY LOCAL?
Un proxy local es un intermediario que redirige el tráfico de un puerto
a otro puerto diferente. Esto permite que programas externos que no pueden
cambiar su puerto configurado sigan funcionando aunque el puerto esté ocupado.

EJEMPLO:
- Programa externo quiere puerto 8080
- Puerto 8080 está ocupado
- Creamos proxy: 8080 → 8081
- Programa se conecta a 8080, pero el tráfico va a 8081
- El programa no sabe que está usando 8081

TIPOS DE PROGRAMAS:
- PROPIOS: URA puede cambiar su configuración → solo cambiar puerto
- EXTERNOS: No se pueden modificar → crear proxy con socat
"""

import argparse
import json
import logging
import shutil
import socket
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

# Ruta del archivo de configuración
CONFIG_PATH = Path(__file__).parent.parent / "config" / "port_proxy.json"


@dataclass
class ProxyRule:
    """Regla de proxy"""

    app_name: str
    app_type: str  # "own" or "external"
    original_port: int
    target_port: int
    enabled: bool
    created_at: str
    socat_pid: int | None = None


class PortProxy:
    """Sistema inteligente de proxy de puertos usando socat"""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        self.proxy_rules: dict[str, ProxyRule] = {}
        self._check_socat_available()

    def _check_socat_available(self) -> bool:
        """Verificar si socat está instalado"""
        if not shutil.which("socat"):
            logger.error("socat no está instalado. Instala con: brew install socat")
            return False
        return True

    def _load_config(self) -> dict:
        """Cargar configuración desde archivo"""
        try:
            with open(self.config_path) as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {self.config_path}")
            return self._default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando configuración: {e}")
            return self._default_config()

    def _default_config(self) -> dict:
        """Configuración por defecto"""
        return {"version": "1.0", "proxy_enabled": True, "rules": []}

    def _save_config(self) -> bool:
        """Guardar configuración en archivo"""
        try:
            self.config["rules"] = [asdict(rule) for rule in self.proxy_rules.values()]
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False

    def add_proxy_rule(
        self, app_name: str, app_type: str, original_port: int, target_port: int
    ) -> bool:
        """Añadir regla de proxy"""
        rule = ProxyRule(
            app_name=app_name,
            app_type=app_type,
            original_port=original_port,
            target_port=target_port,
            enabled=True,
            created_at=datetime.now().isoformat(),
        )

        self.proxy_rules[app_name] = rule
        return self._save_config()

    def remove_proxy_rule(self, app_name: str) -> bool:
        """Eliminar regla de proxy"""
        if app_name in self.proxy_rules:
            del self.proxy_rules[app_name]
            return self._save_config()
        return False

    def get_proxy_rules(self) -> list[ProxyRule]:
        """Obtener todas las reglas de proxy"""
        return list(self.proxy_rules.values())

    def handle_own_app(self, app_name: str, original_port: int, new_port: int) -> bool:
        """
        Manejar programa propio: cambiar puerto en configuración

        Para programas de URA que podemos modificar, simplemente cambiamos
        el puerto en sus archivos de configuración.
        """
        try:
            # Importar port_registry para actualizar configuración
            from port_registry import PortRegistry

            registry = PortRegistry()

            # Actualizar puerto en configuración
            if app_name in registry.config["registered_ports"]:
                registry.config["registered_ports"][app_name]["port"] = new_port
                registry.config["registered_ports"][app_name]["last_check"] = (
                    datetime.now().isoformat()
                )
                registry._save_config()

                logger.info(
                    f"Programa propio {app_name}: puerto cambiado de {original_port} a {new_port}"
                )
                return True
            else:
                # Registrar si no existe
                registry.register_port(app_name, new_port)
                logger.info(f"Programa propio {app_name}: registrado en puerto {new_port}")
                return True

        except Exception as e:
            logger.error(f"Error manejando programa propio {app_name}: {e}")
            return False

    def _start_socat_proxy(self, original_port: int, target_port: int) -> int | None:
        """
        Iniciar proxy usando socat (método robusto)

        socat es una herramienta profesional de red que puede crear proxies
        TCP/UDP de forma eficiente y confiable.

        Comando: socat TCP-LISTEN:original_port,fork,reuseaddr TCP:localhost:target_port
        """
        try:
            # Verificar que puerto original está libre
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.bind(("localhost", original_port))
                test_socket.close()
            except OSError:
                logger.error(f"Puerto {original_port} ya está en uso, no se puede crear proxy")
                return None

            # Iniciar socat
            cmd = [
                "socat",
                f"TCP-LISTEN:{original_port},fork,reuseaddr",
                f"TCP:localhost:{target_port}",
            ]

            process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
            )

            # Esperar un momento para verificar que inició
            time.sleep(0.5)

            if process.poll() is None:
                logger.info(
                    f"Proxy socat iniciado: {original_port} → {target_port} (PID: {process.pid})"
                )
                return process.pid
            else:
                logger.error(f"socat falló al iniciar (exit code: {process.returncode})")
                return None

        except Exception as e:
            logger.error(f"Error iniciando socat: {e}")
            return None

    def _stop_socat_proxy(self, pid: int) -> bool:
        """Detener proceso socat"""
        try:
            process = psutil.Process(pid)
            process.terminate()
            process.wait(timeout=5)
            logger.info(f"Proxy socat detenido (PID: {pid})")
            return True
        except psutil.NoSuchProcess:
            logger.warning(f"Proceso {pid} no existe")
            return True
        except psutil.TimeoutExpired:
            try:
                process.kill()
                logger.warning(f"Proxy socat forzado a terminar (PID: {pid})")
                return True
            except Exception:
                return False
        except Exception as e:
            logger.error(f"Error deteniendo proxy: {e}")
            return False

    def start_proxy(self, app_name: str) -> bool:
        """
        Iniciar proxy para una aplicación

        - PROPIOS: Cambiar configuración (sin proxy)
        - EXTERNOS: Crear proxy con socat
        """
        if app_name not in self.proxy_rules:
            logger.error(f"No hay regla de proxy para {app_name}")
            return False

        rule = self.proxy_rules[app_name]

        if not rule.enabled:
            logger.warning(f"Proxy para {app_name} está desactivado")
            return False

        if rule.app_type == "own":
            # Para programas propios, solo cambiar configuración
            return self.handle_own_app(app_name, rule.original_port, rule.target_port)

        elif rule.app_type == "external":
            # Para programas externos, crear proxy con socat
            if rule.socat_pid:
                # Verificar si sigue corriendo
                try:
                    psutil.Process(rule.socat_pid)
                    logger.warning(f"Proxy para {app_name} ya está activo (PID: {rule.socat_pid})")
                    return True
                except psutil.NoSuchProcess:
                    rule.socat_pid = None

            # Iniciar nuevo proxy con socat
            pid = self._start_socat_proxy(rule.original_port, rule.target_port)
            if pid:
                rule.socat_pid = pid
                self._save_config()
                logger.info(
                    f"Proxy iniciado para {app_name}: {rule.original_port} → {rule.target_port}"
                )
                return True
            else:
                return False

        return False

    def stop_proxy(self, app_name: str) -> bool:
        """Detener proxy para una aplicación"""
        if app_name not in self.proxy_rules:
            return False

        rule = self.proxy_rules[app_name]

        if rule.app_type == "external" and rule.socat_pid:
            success = self._stop_socat_proxy(rule.socat_pid)
            if success:
                rule.socat_pid = None
                self._save_config()
                logger.info(f"Proxy detenido para {app_name}")
                return True

        return False

    def stop_all_proxies(self):
        """Detener todos los proxies"""
        for app_name, rule in self.proxy_rules.items():
            if rule.app_type == "external" and rule.socat_pid:
                self.stop_proxy(app_name)

    def get_active_proxies(self) -> list[str]:
        """Obtener lista de proxies activos"""
        active = []
        for app_name, rule in self.proxy_rules.items():
            if rule.app_type == "external" and rule.socat_pid:
                try:
                    psutil.Process(rule.socat_pid)
                    active.append(app_name)
                except psutil.NoSuchProcess:
                    rule.socat_pid = None
        return active


def main():
    """Punto de entrada CLI"""
    parser = argparse.ArgumentParser(description="URA - Sistema de Proxy de Puertos")
    parser.add_argument(
        "--add",
        nargs=4,
        metavar=("APP", "TYPE", "ORIG", "TARGET"),
        help="Añadir regla (own/external)",
    )
    parser.add_argument("--remove", type=str, metavar="APP", help="Eliminar regla")
    parser.add_argument("--list", action="store_true", help="Listar reglas")
    parser.add_argument("--start", type=str, metavar="APP", help="Iniciar proxy")
    parser.add_argument("--stop", type=str, metavar="APP", help="Detener proxy")
    parser.add_argument("--stop-all", action="store_true", help="Detener todos los proxies")
    parser.add_argument("--active", action="store_true", help="Listar proxies activos")
    parser.add_argument("--verbose", action="store_true", help="Modo verboso")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    proxy = PortProxy()

    if args.add:
        app_name, app_type, orig_port, target_port = args.add
        success = proxy.add_proxy_rule(app_name, app_type, int(orig_port), int(target_port))
        if success:
            print(f"✅ Regla añadida: {app_name} ({app_type}) {orig_port} → {target_port}")
        else:
            print("❌ Error añadiendo regla")

    elif args.remove:
        success = proxy.remove_proxy_rule(args.remove)
        if success:
            print(f"✅ Regla eliminada: {args.remove}")
        else:
            print("❌ Error eliminando regla")

    elif args.list:
        rules = proxy.get_proxy_rules()
        print(f"\n=== REGLAS DE PROXY ({len(rules)}) ===")
        for rule in rules:
            status = "✅" if rule.enabled else "❌"
            print(f"{status} {rule.app_name} ({rule.app_type})")
            print(f"   {rule.original_port} → {rule.target_port}")
            print(f"   Creado: {rule.created_at}")

    elif args.start:
        success = proxy.start_proxy(args.start)
        if success:
            print(f"✅ Proxy iniciado: {args.start}")
        else:
            print("❌ Error iniciando proxy")

    elif args.stop:
        success = proxy.stop_proxy(args.stop)
        if success:
            print(f"✅ Proxy detenido: {args.stop}")
        else:
            print("❌ Error deteniendo proxy")

    elif args.stop_all:
        proxy.stop_all_proxies()
        print("✅ Todos los proxies detenidos")

    elif args.active:
        active = proxy.get_active_proxies()
        print(f"\n=== PROXIES ACTIVOS ({len(active)}) ===")
        for app in active:
            print(f"- {app}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
