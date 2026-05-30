#!/usr/bin/env python3
"""
Puente Cascade → Sandbox Docker Obligatorio
Todo código que toca Cascade debe pasar por sandbox antes de aplicarse
"""

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CascadeSandboxBridge:
    """Puente obligatorio de Cascade a sandbox Docker"""

    def __init__(self):
        self.ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")
        self.sandbox_path = Path("/Users/ramonesnaola/Desktop/URA_App/v10.0_SANDBOX")
        self.pending_changes = self.ura_app_path / "pending_changes"
        self.approved_changes = self.ura_app_path / "approved_changes"
        self.log_file = self.ura_app_path / "logs" / "cascade_sandbox.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.pending_changes.mkdir(exist_ok=True)
        self.approved_changes.mkdir(exist_ok=True)

    def log(self, mensaje, nivel="INFO"):
        """Registrar en log"""
        timestamp = datetime.now().isoformat()
        with open(self.log_file, "a") as f:
            f.write(f"{timestamp} - {nivel} - {mensaje}\n")
        logger.log(getattr(logging, nivel), mensaje)

    def enviar_cambio_a_sandbox(
        self, archivo: str, contenido: str, tipo: str = "codigo", emergencia: bool = False
    ) -> bool:
        """Enviar cambio a sandbox para aprobación"""
        self.log(f"Enviando cambio a sandbox: {archivo} ({tipo})")

        # Opción de emergencia para saltar sandbox
        if emergencia:
            self.log("⚠️ MODO EMERGENCIA - Saltando sandbox", "WARNING")
            ura_file = self.ura_app_path / archivo
            ura_file.parent.mkdir(parents=True, exist_ok=True)

            with open(ura_file, "w") as f:
                f.write(contenido)

            self.log(f"Cambio aplicado en modo emergencia: {archivo}")
            return True

        try:
            # Guardar cambio pendiente
            cambio_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            cambio_file = (
                self.pending_changes / f"{cambio_id}_{tipo}_{archivo.replace('/', '_')}.json"
            )

            cambio = {
                "id": cambio_id,
                "archivo": archivo,
                "tipo": tipo,
                "contenido": contenido,
                "timestamp": datetime.now().isoformat(),
                "estado": "pendiente",
                "origen": "cascade",
            }

            with open(cambio_file, "w") as f:
                json.dump(cambio, f, indent=2)

            # Copiar a sandbox
            sandbox_file = self.sandbox_path / archivo
            sandbox_file.parent.mkdir(parents=True, exist_ok=True)

            with open(sandbox_file, "w") as f:
                f.write(contenido)

            # Mostrar tiempo estimado
            tiempo_estimado = self._estimar_tiempo_prueba()
            self.log(f"Tiempo estimado de prueba: {tiempo_estimado} segundos")

            # Reiniciar sandbox
            self.log("Reiniciando sandbox para probar cambio...")
            self._reiniciar_sandbox()

            # Ejecutar pruebas
            self.log("Ejecutando pruebas en sandbox...")
            pruebas_ok = self._ejecutar_pruebas_sandbox()

            if pruebas_ok:
                # Aprobar cambio
                cambio["estado"] = "aprobado"
                cambio["aprobado_timestamp"] = datetime.now().isoformat()

                # Mover a approved_changes
                approved_file = self.approved_changes / cambio_file.name
                shutil.move(str(cambio_file), str(approved_file))

                # Aplicar cambio en URA_App
                ura_file = self.ura_app_path / archivo
                ura_file.parent.mkdir(parents=True, exist_ok=True)

                with open(ura_file, "w") as f:
                    f.write(contenido)

                self.log(f"Cambio APROBADO y aplicado: {archivo}")
                return True
            else:
                # Rechazar cambio
                cambio["estado"] = "rechazado"
                cambio["rechazado_timestamp"] = datetime.now().isoformat()
                cambio["razon"] = "Pruebas fallaron"

                with open(cambio_file, "w") as f:
                    json.dump(cambio, f, indent=2)

                # NOTIFICACIÓN cuando sandbox rechaza
                self._enviar_notificacion_rechazo(archivo, cambio["razon"])
                self.log(f"Cambio RECHAZADO: {archivo} - Pruebas fallaron", "ERROR")
                return False

        except Exception as e:
            self.log(f"Error enviando cambio a sandbox: {e}", "ERROR")
            return False

    def _reiniciar_sandbox(self) -> bool:
        """Reiniciar sandbox"""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    "docker-compose-completo.yml",
                    "restart",
                    "ura-sandbox",
                ],
                cwd="/Users/ramonesnaola/Desktop/URA_App",
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        except:
            return False

    def _ejecutar_pruebas_sandbox(self) -> bool:
        """Ejecutar pruebas en sandbox"""
        try:
            # Ejecutar pruebas exhaustivas
            result = subprocess.run(
                ["python3", "-m", "pytest", "tests/test_exhaustivos.py", "-v"],
                cwd=str(self.sandbox_path),
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode == 0
        except:
            return False

    def _estimar_tiempo_prueba(self) -> int:
        """Estimar tiempo de prueba en segundos"""
        # Basado en experiencia: ~90 segundos para pruebas completas
        return 90

    def _enviar_notificacion_rechazo(self, archivo: str, razon: str):
        """Enviar notificación cuando sandbox rechaza código"""
        notificacion = {
            "timestamp": datetime.now().isoformat(),
            "tipo": "rechazo_sandbox",
            "archivo": archivo,
            "razon": razon,
            "mensaje": f"⛔ Sandbox rechazó código: {archivo}\nRazón: {razon}",
        }

        notificaciones_file = self.ura_app_path / "notifications" / "sandbox_notifications.json"
        notificaciones_file.parent.mkdir(parents=True, exist_ok=True)

        notificaciones = []
        if notificaciones_file.exists():
            with open(notificaciones_file) as f:
                notificaciones = json.load(f)

        notificaciones.append(notificacion)

        with open(notificaciones_file, "w") as f:
            json.dump(notificaciones, f, indent=2)

        self.log(f"🔔 Notificación enviada: {notificacion['mensaje']}", "WARNING")

    def obtener_estado_cambios(self) -> Dict:
        """Obtener estado de cambios pendientes y aprobados"""
        estado = {"pendientes": [], "aprobados": [], "rechazados": []}

        for archivo in self.pending_changes.glob("*.json"):
            with open(archivo) as f:
                cambio = json.load(f)
                estado["pendientes"].append(cambio)

        for archivo in self.approved_changes.glob("*.json"):
            with open(archivo) as f:
                cambio = json.load(f)
                if cambio["estado"] == "aprobado":
                    estado["aprobados"].append(cambio)
                else:
                    estado["rechazados"].append(cambio)

        return estado


# Instancia global
cascade_sandbox_bridge = CascadeSandboxBridge()

if __name__ == "__main__":
    bridge = CascadeSandboxBridge()
    estado = bridge.obtener_estado_cambios()

    print("=== ESTADO DE CAMBIOS ===")
    print(f"Pendientes: {len(estado['pendientes'])}")
    print(f"Aprobados: {len(estado['aprobados'])}")
    print(f"Rechazados: {len(estado['rechazados'])}")
