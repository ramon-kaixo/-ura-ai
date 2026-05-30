#!/usr/bin/env python3
"""
Agente Operativo y Hardware para Bar - URA System
Gestiona cajas registradoras, mantenimiento, seguridad y red
"""

import logging

logger = logging.getLogger(__name__)
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil

sys.path.append("..")
from utils.agent_base_stability import AgentStabilityBase


class AgenteOperativoHardware(AgentStabilityBase):
    """Agente especializado en hardware y operaciones del bar"""

    def __init__(self):
        super().__init__("agente_operativo_hardware")
        self.terminales = {}
        self.cajas_registradoras = {}
        self.camaras_seguridad = {}
        self.red_config = {}
        self.mantenimiento_log = []
        self.config_dir = Path("config/hardware")
        self.logs_dir = Path("logs/hardware")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Cargar configuración existente
        self._load_config()

    def procesar(self, texto: str) -> str:
        """Procesar consulta sobre hardware y operaciones."""
        texto_lower = texto.lower()

        if "terminal" in texto_lower or "caja" in texto_lower:
            return "Puedo monitorizar y gestionar terminales y cajas registradoras del sistema"

        if "cámara" in texto_lower or "seguridad" in texto_lower:
            return "Puedo gestionar cámaras de seguridad y videovigilancia"

        if "mantenimiento" in texto_lower or "rendimiento" in texto_lower:
            return "Puedo realizar mantenimiento proactivo y monitorear rendimiento del sistema"

        if "red" in texto_lower or "conexión" in texto_lower:
            return "Puedo gestionar configuración de red y conectividad del sistema"

        return "Agente operativo y hardware disponible. Funciones: terminales, cámaras, mantenimiento, red"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción específica sobre hardware y operaciones."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información sobre hardware y operaciones."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta sobre hardware y operaciones."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteOperativoHardware.

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos clave

        Returns:
            Dict con {"success": bool, "response": str, "error": str}
        """
        try:
            texto = args[0] if args else kwargs.get("texto", "")
            if not texto:
                return {"success": False, "response": "", "error": "No se proporcionó texto"}

            response = self.procesar(texto)
            return {"success": True, "response": response, "error": ""}
        except Exception as e:
            return {"success": False, "response": "", "error": str(e)}

    def get_agent_capabilities(self) -> dict[str, Any]:
        """Devuelve las capacidades del agente"""
        return {
            "monitorizar_terminales": {
                "descripcion": "Monitorizar estado de terminales",
                "parametros": [],
                "retorno": "Dict[str, Any]",
            },
            "gestionar_camaras": {
                "descripcion": "Gestionar cámaras de seguridad",
                "parametros": [],
                "retorno": "Dict[str, Any]",
            },
            "mantenimiento_proactivo": {
                "descripcion": "Realizar mantenimiento proactivo",
                "parametros": [],
                "retorno": "Dict[str, Any]",
            },
        }

    def _load_config(self):
        """Cargar configuración de hardware"""
        try:
            config_file = self.config_dir / "hardware_config.json"
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                    self.terminales = config.get("terminales", {})
                    self.cajas_registradoras = config.get("cajas_registradoras", {})
                    self.camaras_seguridad = config.get("camaras_seguridad", {})
                    self.red_config = config.get("red_config", {})
        except Exception as e:
            print(f"Error loading hardware config: {e}")

    def _save_config(self):
        """Guardar configuración de hardware"""
        try:
            config = {
                "terminales": self.terminales,
                "cajas_registradoras": self.cajas_registradoras,
                "camaras_seguridad": self.camaras_seguridad,
                "red_config": self.red_config,
            }

            config_file = self.config_dir / "hardware_config.json"
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving hardware config: {e}")

    def registrar_terminal(self, nombre: str, ip: str, tipo: str, ubicacion: str) -> dict[str, Any]:
        """Registrar nuevo terminal en el sistema"""
        terminal_id = f"TERM_{int(time.time())}"

        terminal = {
            "id": terminal_id,
            "nombre": nombre,
            "ip": ip,
            "tipo": tipo,  # "caja", "cocina", "bar", "admin"
            "ubicacion": ubicacion,
            "estado": "activo",
            "fecha_registro": time.time(),
            "ultimo_heartbeat": time.time(),
            "specs": self._get_system_specs(),
            "software": self._get_installed_software(),
            "mantenimiento_programado": False,
        }

        self.terminales[terminal_id] = terminal
        self._save_config()

        # Si es caja registradora, configurarla específicamente
        if tipo == "caja":
            self._configurar_caja_registradora(terminal_id)

        return terminal

    def _get_system_specs(self) -> dict[str, Any]:
        """Obtener especificaciones del sistema"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "disk_total": psutil.disk_usage("/").total,
            }
        except Exception as e:
            return {"error": str(e)}

    def _get_installed_software(self) -> list[str]:
        """Obtener software instalado relevante"""
        software = []

        # Software común para bares
        programas_buscar = ["firefox", "chrome", "safari", "excel", "word", "pos", "cashier"]

        try:
            # En macOS, usar system_profiler
            result = subprocess.run(
                ["system_profiler", "SPApplicationsDataType", "-json"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                apps_data = json.loads(result.stdout)
                for app in apps_data.get("SPApplicationsDataType", []):
                    app_name = app.get("_name", "").lower()
                    if any(prog in app_name for prog in programas_buscar):
                        software.append(app.get("_name", ""))
        except Exception as e:
            logger.warning(f"Error silencioso en operativo_hardware.scan_software: {e}")
            # fallback: continuar

        return software

    def _configurar_caja_registradora(self, terminal_id: str):
        """Configurar terminal como caja registradora"""
        self.terminales[terminal_id]

        caja_config = {
            "terminal_id": terminal_id,
            "impresora_ticket": {
                "modelo": "Epson TM-T88",
                "conexion": "USB",
                "estado": "conectada",
            },
            "lector_codigos": {"modelo": "Honeywell", "conexion": "USB", "estado": "conectado"},
            "cajon_dinero": {"modelo": "APG", "conexion": "USB", "estado": "conectado"},
            "pantalla_cliente": {
                "tipo": "LCD",
                "conexion": "VGA",
                "resolucion": "1024x768",
                "estado": "activa",
            },
            "software_pos": {"nombre": "URA POS System", "version": "1.0.0", "estado": "activo"},
        }

        self.cajas_registradoras[terminal_id] = caja_config
        self._save_config()

    def monitorizar_terminales(self) -> dict[str, Any]:
        """Monitorizar estado de todos los terminales"""
        estado_general = {
            "total_terminales": len(self.terminales),
            "activos": 0,
            "inactivos": 0,
            "problemas": 0,
            "detalles": [],
        }

        current_time = time.time()

        for terminal_id, terminal in self.terminales.items():
            # Verificar heartbeat (simulado)
            tiempo_sin_heartbeat = current_time - terminal.get("ultimo_heartbeat", 0)
            estado = "activo" if tiempo_sin_heartbeat < 300 else "inactivo"  # 5 minutos

            if estado == "activo":
                estado_general["activos"] += 1
            else:
                estado_general["inactivos"] += 1

            # Obtener specs actuales
            specs_actuales = self._get_system_specs()

            # Detectar problemas
            problemas = []
            if specs_actuales.get("cpu_percent", 0) > 80:
                problemas.append("CPU alta")
            if specs_actuales.get("memory_percent", 0) > 85:
                problemas.append("Memoria alta")
            if specs_actuales.get("disk_percent", 0) > 90:
                problemas.append("Disco lleno")

            if problemas:
                estado_general["problemas"] += 1

            terminal_detail = {
                "id": terminal_id,
                "nombre": terminal["nombre"],
                "ubicacion": terminal["ubicacion"],
                "estado": estado,
                "problemas": problemas,
                "specs": specs_actuales,
                "ultimo_heartbeat": terminal.get("ultimo_heartbeat", 0),
            }

            estado_general["detalles"].append(terminal_detail)

        return estado_general

    def mantenimiento_proactivo(self) -> dict[str, Any]:
        """Ejecutar mantenimiento proactivo del sistema"""
        tareas_realizadas = []

        # 1. Limpieza de archivos temporales
        limpieza_result = self._limpiar_archivos_temporales()
        if limpieza_result["archivos_eliminados"] > 0:
            tareas_realizadas.append(
                {
                    "tarea": "Limpieza de archivos temporales",
                    "resultado": f"Eliminados {limpieza_result['archivos_eliminados']} archivos",
                    "espacio_liberado": f"{limpieza_result['espacio_liberado']} MB",
                }
            )

        # 2. Actualización de software
        actualizacion_result = self._verificar_actualizaciones()
        if actualizacion_result["actualizaciones_pendientes"] > 0:
            tareas_realizadas.append(
                {
                    "tarea": "Verificación de actualizaciones",
                    "resultado": f"{actualizacion_result['actualizaciones_pendientes']} actualizaciones pendientes",
                    "detalles": actualizacion_result["detalles"],
                }
            )

        # 3. Optimización de disco
        optimizacion_result = self._optimizar_disco()
        if optimizacion_result["optimizado"]:
            tareas_realizadas.append(
                {
                    "tarea": "Optimización de disco",
                    "resultado": "Disco optimizado",
                    "espacio_recuperado": f"{optimizacion_result['espacio_recuperado']} MB",
                }
            )

        # 4. Verificación de seguridad
        seguridad_result = self._verificar_seguridad()
        tareas_realizadas.append(
            {"tarea": "Verificación de seguridad", "resultado": seguridad_result}
        )

        # Registrar mantenimiento
        mantenimiento_entry = {
            "timestamp": time.time(),
            "tareas": tareas_realizadas,
            "tipo": "mantenimiento_proactivo",
        }

        self.mantenimiento_log.append(mantenimiento_entry)
        self._save_mantenimiento_log()

        return {
            "fecha": datetime.now().isoformat(),
            "tareas_realizadas": len(tareas_realizadas),
            "detalles": tareas_realizadas,
        }

    def _limpiar_archivos_temporales(self) -> dict[str, Any]:
        """Limpiar archivos temporales"""
        archivos_eliminados = 0
        espacio_liberado = 0

        # Directorios temporales comunes
        temp_dirs = [Path("/tmp"), Path.home() / "Library/Caches", Path.home() / ".cache"]

        for temp_dir in temp_dirs:
            if temp_dir.exists():
                try:
                    for file_path in temp_dir.rglob("*"):
                        if file_path.is_file():
                            # Solo eliminar archivos más antiguos de 7 días
                            file_age = time.time() - file_path.stat().st_mtime
                            if file_age > 7 * 24 * 3600:  # 7 días
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                archivos_eliminados += 1
                                espacio_liberado += file_size
                except Exception:
                    continue

        return {
            "archivos_eliminados": archivos_eliminados,
            "espacio_liberado": round(espacio_liberado / 1024 / 1024, 2),  # MB
        }

    def _verificar_actualizaciones(self) -> dict[str, Any]:
        """Verificar actualizaciones pendientes"""
        actualizaciones_pendientes = 0
        detalles = []

        # Simular verificación de actualizaciones
        # En producción, esto usaría brew en macOS

        # Verificar actualizaciones de Python
        try:
            result = subprocess.run(["pip", "list", "--outdated"], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                for line in lines[2:]:  # Saltar encabezado
                    if line.strip():
                        actualizaciones_pendientes += 1
                        detalles.append(f"Python package: {line.strip()}")
        except Exception as e:
            logger.warning(f"Error silencioso en operativo_hardware.check_updates: {e}")
            # fallback: continuar

        return {
            "actualizaciones_pendientes": actualizaciones_pendientes,
            "detalles": detalles[:5],  # Limitar a 5 actualizaciones
        }

    def _optimizar_disco(self) -> dict[str, Any]:
        """Optimizar espacio en disco"""
        espacio_recuperado = 0
        optimizado = False

        try:
            # Limpiar cache de pip
            result = subprocess.run(["pip", "cache", "purge"], capture_output=True, text=True)
            if result.returncode == 0:
                optimizado = True
                espacio_recuperado += 50  # Estimación

        except Exception as e:
            logger.warning(f"Error silencioso en operativo_hardware.optimize: {e}")
            # fallback: continuar

        return {"optimizado": optimizado, "espacio_recuperado": espacio_recuperado}

    def _verificar_seguridad(self) -> str:
        """Verificar estado de seguridad"""
        checks = []

        # Verificar firewall
        try:
            result = subprocess.run(["sudo", "pfctl", "-s", "info"], capture_output=True, text=True)
            if result.returncode == 0:
                checks.append("Firewall: Activo")
            else:
                checks.append("Firewall: Inactivo")
        except Exception:
            checks.append("Firewall: No se puede verificar")

        # Verificar cámaras
        if self.camaras_seguridad:
            checks.append(f"Cámaras: {len(self.camaras_seguridad)} configuradas")
        else:
            checks.append("Cámaras: No configuradas")

        # Verificar red
        red_status = self._verificar_estado_red()
        checks.append(f"Red: {red_status}")

        return " | ".join(checks)

    def _verificar_estado_red(self) -> str:
        """Verificar estado de la red"""
        try:
            # Verificar conexión a internet
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return "Conectada"
        except Exception:
            return "Desconectada"

    def gestionar_camaras_seguridad(self) -> dict[str, Any]:
        """Gestionar sistema de cámaras de seguridad"""
        estado_camaras = {
            "total_camaras": len(self.camaras_seguridad),
            "activas": 0,
            "inactivas": 0,
            "detalles": [],
        }

        for camera_id, camera in self.camaras_seguridad.items():
            # Simular estado de cámara
            estado = "activa" if camera.get("estado", "activo") == "activo" else "inactiva"

            if estado == "activa":
                estado_camaras["activas"] += 1
            else:
                estado_camaras["inactivas"] += 1

            camera_detail = {
                "id": camera_id,
                "nombre": camera.get("nombre", f"Cámara {camera_id}"),
                "ubicacion": camera.get("ubicacion", "Sin especificar"),
                "estado": estado,
                "ultima_revision": camera.get("ultima_revision", time.time()),
            }

            estado_camaras["detalles"].append(camera_detail)

        return estado_camaras

    def gestionar_red_wifi(self) -> dict[str, Any]:
        """Gestionar red Wi-Fi del bar"""
        # Simular configuración de red
        red_info = {
            "ssid": "Bar_Clientes",
            "ssid_staff": "Bar_Staff",
            "clientes_conectados": 15,
            "staff_conectados": 8,
            "ancho_banda_total": "100 Mbps",
            "ancho_banda_usado": "45 Mbps",
            "seguridad": "WPA3",
            "estado": "Activa",
        }

        # Verificar calidad de señal
        calidad_señal = self._verificar_calidad_señal()
        red_info["calidad_señal"] = calidad_señal

        return red_info

    def _verificar_calidad_señal(self) -> dict[str, str]:
        """Verificar calidad de señal Wi-Fi"""
        # Simular verificación de calidad
        return {
            "recepcion": "Excelente",
            "interferencias": "Bajas",
            "cobertura": "Completa",
            "estabilidad": "Alta",
        }

    def _save_mantenimiento_log(self):
        """Guardar log de mantenimiento"""
        try:
            log_file = self.logs_dir / "mantenimiento.json"
            with open(log_file, "w") as f:
                json.dump(self.mantenimiento_log, f, indent=2)
        except Exception as e:
            print(f"Error saving maintenance log: {e}")

    def get_reporte_hardware(self) -> dict[str, Any]:
        """Generar reporte completo de hardware"""
        terminales_estado = self.monitorizar_terminales()
        mantenimiento_reciente = self.mantenimiento_log[-5:] if self.mantenimiento_log else []

        return {
            "timestamp": time.time(),
            "terminales": terminales_estado,
            "cajas_registradoras": len(self.cajas_registradoras),
            "camaras": self.gestionar_camaras_seguridad(),
            "red": self.gestionar_red_wifi(),
            "mantenimiento_reciente": mantenimiento_reciente,
            "proximo_mantenimiento": self._calcular_proximo_mantenimiento(),
        }

    def monitorizar_terminales(self) -> dict[str, Any]:
        """Monitorizar estado de terminales y cajas registradoras"""
        self.log_reasoning_step("TERMINAL_MONITORING_START", {})

        # Obtener métricas del sistema
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Simular terminales del bar
        terminales_simulados = {
            "terminal_1": {
                "id": "terminal_1",
                "nombre": "Caja Principal",
                "estado": "activo",
                "cpu": cpu_percent + 5,
                "memoria": memory.percent + 2,
                "disco": disk.percent,
                "conectado": True,
                "ultima_comunicacion": time.time(),
                "alertas": [],
            },
            "terminal_2": {
                "id": "terminal_2",
                "nombre": "Caja Secundaria",
                "estado": "activo",
                "cpu": cpu_percent - 3,
                "memoria": memory.percent - 1,
                "disco": disk.percent,
                "conectado": True,
                "ultima_comunicacion": time.time(),
                "alertas": [],
            },
            "terminal_3": {
                "id": "terminal_3",
                "nombre": "Terminal Cocina",
                "estado": "inactivo",
                "cpu": 0,
                "memoria": 0,
                "disco": 0,
                "conectado": False,
                "ultima_comunicacion": time.time() - 3600,
                "alertas": ["Sin conexión"],
            },
        }

        # Detectar alertas
        alertas_sistema = []
        if cpu_percent > 80:
            alertas_sistema.append("CPU alta")
        if memory.percent > 85:
            alertas_sistema.append("Memoria alta")
        if disk.percent > 90:
            alertas_sistema.append("Disco casi lleno")

        # Contar terminales activos
        terminales_activos = len(
            [t for t in terminales_simulados.values() if t["estado"] == "activo"]
        )
        terminales_con_alertas = len([t for t in terminales_simulados.values() if t["alertas"]])

        resultado = {
            "timestamp": time.time(),
            "terminales_totales": len(terminales_simulados),
            "terminales_activos": terminales_activos,
            "terminales_con_alertas": terminales_con_alertas,
            "sistema": {
                "cpu_percent": cpu_percent,
                "memoria_percent": memory.percent,
                "disco_percent": disk.percent,
                "memoria_disponible_gb": memory.available / (1024**3),
                "disco_libre_gb": disk.free / (1024**3),
            },
            "alertas_sistema": alertas_sistema,
            "terminales_detalle": terminales_simulados,
            "recomendaciones": self._generar_recomendaciones_mantenimiento(
                cpu_percent, memory.percent, disk.percent
            ),
        }

        self.log_reasoning_step(
            "TERMINAL_MONITORING_COMPLETE",
            {"terminales_activos": terminales_activos, "alertas_detectadas": len(alertas_sistema)},
            0.9,
        )

        return resultado

    def _generar_recomendaciones_mantenimiento(
        self, cpu: float, memoria: float, disco: float
    ) -> list[str]:
        """Generar recomendaciones de mantenimiento"""
        recomendaciones = []

        if cpu > 80:
            recomendaciones.append("Optimizar procesos de CPU")
        if memoria > 85:
            recomendaciones.append("Limpiar memoria cache")
        if disco > 90:
            recomendaciones.append("Liberar espacio en disco")

        if cpu < 50 and memoria < 60 and disco < 70:
            recomendaciones.append("Sistema funcionando optimamente")

        return recomendaciones

    def _calcular_proximo_mantenimiento(self) -> str:
        """Calcular próximo mantenimiento programado"""
        # Programar mantenimiento semanal
        proxima_fecha = datetime.now() + timedelta(days=7)
        return proxima_fecha.strftime("%Y-%m-%d %H:%M")

        """Responder pregunta sobre hardware y operaciones."""
        return self.procesar(texto)


# Instancia global
agente_operativo_hardware = AgenteOperativoHardware()

if __name__ == "__main__":
    # Ejemplo de uso
    agente = AgenteOperativoHardware()

    # Registrar terminal
    terminal = agente.registrar_terminal(
        nombre="Caja Principal", ip="192.168.1.100", tipo="caja", ubicacion="Zona Principal"
    )
    print(f"Terminal registrado: {terminal['id']}")

    # Monitorizar sistema
    estado = agente.monitorizar_terminales()
    print(f"Estado terminales: {estado['activos']} activos, {estado['inactivos']} inactivos")

    # Mantenimiento proactivo
    mantenimiento = agente.mantenimiento_proactivo()
    print(f"Tareas de mantenimiento: {mantenimiento['tareas_realizadas']}")

    # Reporte completo
    reporte = agente.get_reporte_hardware()
    print(f"Reporte hardware generado: {reporte['timestamp']}")
