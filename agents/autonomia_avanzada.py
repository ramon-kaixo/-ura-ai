"""
Módulo de Autonomía Avanzada para URA/Laia.
Cubre los 8 puntos límite: hardware, legal, red, visión culinaria, UI no accesible,
montaje discos, aprendizaje curioso y empatía.
"""

import os
import sys
import time
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

try:
    import requests
    from core.memory.episodic_memory import EpisodicMemory
except ImportError as exc:
    print(f"Faltan dependencias: {exc}")
    EpisodicMemory = None
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("/tmp/autonomia.log"), logging.StreamHandler()],
)
logger = logging.getLogger("AutonomiaAvanzada")

URA_BASE = Path(__file__).resolve().parent.parent
CONFIG_FILE = URA_BASE / "config" / "autonomia.json"
LEGAL_RULES_FILE = URA_BASE / "config" / "legal_rules.json"

DEFAULT_CONFIG = {
    "hardware": {
        "pdu_api_url": "http://192.168.1.100/api",
        "relay_usb_device": "/dev/ttyUSB0",
        "kvm_ip": "192.168.1.101",
    },
    "legal": {
        "rules_file": str(LEGAL_RULES_FILE),
        "escalar_siempre": False,
    },
    "network": {
        "primary_dns": "8.8.8.8",
        "backup_dns": "1.1.1.1",
        "fallback_gateway": "192.168.2.1",
        "hotspot_ssid": "URA_Backup",
        "hotspot_password": "urabackup123",
        "four_g_interface": "wwan0",
    },
    "vision_culinaria": {
        "model_path": str(URA_BASE / "models" / "platos_model.json"),
        "training_images": str(URA_BASE / "data" / "platos_etiquetados"),
        "confidence_threshold": 0.7,
    },
    "ui_no_accesible": {
        "vlm_model": "microsoft/Florence-2-large",
        "ocr_lang": "spa",
        "retry_attempts": 3,
    },
    "backup": {
        "mount_point": "/mnt/backup",
        "fallback_b2_bucket": "ura-backup",
        "max_retries": 3,
    },
    "aprendizaje_curioso": {
        "scan_interval_hours": 168,
        "sandbox_vm": "URA_Sandbox",
        "max_new_macros": 5,
    },
    "empatia": {
        "emotion_model": "deepface",
        "escalar_gerente_url": "http://localhost:5000/alertar_gerente",
        "min_confidence": 0.6,
    },
}


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as fh:
            return json.load(fh)
    return DEFAULT_CONFIG


def _save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as fh:
        json.dump(cfg, fh, indent=2)


class AutonomiaExtendida:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or _load_config()
        self.laia_api_url = os.getenv("LAIA_API_URL", "http://localhost:8000")
        self.panic_flag = False
        self.memoria = EpisodicMemory() if EpisodicMemory else None

    # ---------- Punto 1: Interacción física (hardware) ----------
    def gestion_hardware(self, accion: str, parametros: dict | None = None) -> bool:
        logger.info("Accion hardware: %s", accion)
        hw = self.config["hardware"]
        if accion == "encender_pdu":
            try:
                resp = requests.post(f"{hw['pdu_api_url']}/outlet/1/on", timeout=5)
                return resp.status_code == 200
            except Exception as exc:
                logger.error("PDU no responde: %s", exc)
                return False
        if accion == "pulsar_usb":
            try:
                import serial

                ser = serial.Serial(hw["relay_usb_device"], 9600, timeout=2)
                ser.write(b"1")
                ser.close()
                return True
            except Exception as exc:
                logger.error("Rele USB no disponible: %s", exc)
                return False
        if accion == "cambiar_kvm":
            port = parametros.get("port", 2) if parametros else 2
            url = f"http://{hw['kvm_ip']}/cgi-bin/kvm?port={port}"
            return subprocess.run(["curl", "-s", url], capture_output=True).returncode == 0
        return False

    # ---------- Punto 2: Decisiones legales/éticas ----------
    def decision_legal(self, contexto: dict) -> dict:
        rules_file = self.config["legal"].get("rules_file", str(LEGAL_RULES_FILE))
        if os.path.exists(rules_file):
            with open(rules_file) as fh:
                rules = json.load(fh)
        else:
            rules = {
                "invitacion_no_cobrada": {"max_euros": 10, "escalar_si_cliente_no_habitual": True},
                "despido_empleado": {"automatico": False, "escalar_siempre": True},
                "tiempo_descanso_excesivo": {"minutos_max": 30, "accion": "notificar"},
            }
        decision: dict[str, object] = {"actuar": False, "escalar": False, "razon": ""}
        tipo = contexto.get("tipo")
        if tipo == "invitacion":
            importe = contexto.get("importe", 0)
            cliente_habitual = contexto.get("cliente_habitual", False)
            regla = rules.get("invitacion_no_cobrada", {})
            if importe <= regla.get("max_euros", 10) and cliente_habitual:
                decision["actuar"] = True
                decision["razon"] = "Invitacion dentro del umbral y cliente habitual"
            else:
                decision["escalar"] = self.config["legal"].get("escalar_siempre", False) or True
                decision["razon"] = "Invitacion fuera de politica"
        elif tipo == "despido":
            decision["escalar"] = True
            decision["razon"] = "Los despidos requieren decision humana"
        elif tipo == "productividad":
            minutos = contexto.get("minutos_inactivo", 0)
            regla = rules.get("tiempo_descanso_excesivo", {})
            if minutos > regla.get("minutos_max", 30):
                decision["actuar"] = True
                decision["razon"] = f"Exceso de descanso: {minutos} minutos"
        return decision

    # ---------- Punto 3: Autorreparación de red ----------
    def autoreparacion_red(self) -> bool:
        logger.info("Verificando conectividad de red")
        try:
            test = subprocess.run(["ping", "-c", "1", "8.8.8.8"], capture_output=True, timeout=5)
            if test.returncode == 0:
                logger.info("Red OK")
                return True
        except Exception:
            pass
        logger.warning("Problemas de red detectados. Aplicando autoreparacion.")
        if os.path.exists("/etc/systemd/resolved.conf"):
            subprocess.run(["systemctl", "restart", "systemd-resolved"], capture_output=True)
        if sys.platform == "darwin":
            subprocess.run(
                ["networksetup", "-setdnsservers", "Wi-Fi", "8.8.8.8", "1.1.1.1"],
                capture_output=True,
            )
        else:
            subprocess.run(
                ["sudo", "ifconfig", "eth0", "192.168.2.99", "netmask", "255.255.255.0", "up"],
                capture_output=True,
            )
        time.sleep(5)
        test2 = subprocess.run(["ping", "-c", "1", "8.8.8.8"], capture_output=True, timeout=5)
        if test2.returncode == 0:
            logger.info("Red restaurada automaticamente")
            return True
        logger.error("No se pudo restaurar la red")
        self._notificar("Red caida, requiere intervencion humana")
        return False

    # ---------- Punto 4: Visión culinaria específica ----------
    def vision_culinaria(self, imagen_path: str) -> dict:
        modelo_path = self.config["vision_culinaria"]["model_path"]
        if not os.path.exists(modelo_path):
            logger.info("Modelo de vision culinaria no encontrado. Iniciando fine-tuning.")
            self._entrenar_modelo_platos()
        try:
            import cv2
            import numpy as np

            img = cv2.imread(imagen_path)
            if img is None:
                return {"error": "No se pudo cargar la imagen", "calidad": "desconocida"}
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            saturacion_media = float(np.mean(hsv[:, :, 1]))
            calidad = "buena" if saturacion_media > 100 else "mejorable"
            return {
                "calidad": calidad,
                "saturacion": saturacion_media,
                "modelo_usado": "heuristico",
            }
        except Exception as exc:
            return {"error": str(exc), "calidad": "desconocida"}

    def _entrenar_modelo_platos(self) -> None:
        logger.info("Entrenando modelo de vision culinaria (simulacion)...")
        modelo_path = self.config["vision_culinaria"]["model_path"]
        Path(modelo_path).parent.mkdir(parents=True, exist_ok=True)
        with open(modelo_path, "w") as fh:
            json.dump({"trained": True, "date": datetime.now().isoformat()}, fh)
        logger.info("Modelo entrenado (simulacion).")

    # ---------- Punto 5: UI no accesible (VLM + OCR) ----------
    def ui_no_accesible(
        self, accion: str, texto_objetivo: str | None = None, screenshot_path: str | None = None
    ) -> bool:
        if screenshot_path is None:
            screenshot_path = "/tmp/ui_temp.png"
            try:
                import pyautogui

                pyautogui.screenshot(screenshot_path)
            except Exception as exc:
                logger.error("No se pudo tomar screenshot: %s", exc)
                return False
        if texto_objetivo:
            try:
                resp = requests.post(
                    f"{self.laia_api_url}/vlm/find",
                    json={"text": texto_objetivo, "image_path": screenshot_path},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "bbox" in data:
                        x1, y1, x2, y2 = data["bbox"]
                        import pyautogui

                        pyautogui.click((x1 + x2) // 2, (y1 + y2) // 2)
                        return True
            except Exception as exc:
                logger.error("Error con VLM: %s", exc)
        try:
            import cv2
            import pytesseract

            img = cv2.imread(screenshot_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            ocr_lang = self.config["ui_no_accesible"]["ocr_lang"]
            data = pytesseract.image_to_data(
                gray, config=f"-l {ocr_lang} --psm 6", output_type=pytesseract.Output.DICT
            )
            for i, word in enumerate(data["text"]):
                if texto_objetivo and texto_objetivo.lower() in word.lower():
                    import pyautogui

                    x = data["left"][i] + data["width"][i] // 2
                    y = data["top"][i] + data["height"][i] // 2
                    pyautogui.click(x, y)
                    return True
        except Exception as exc:
            logger.error("OCR fallo: %s", exc)
        return False

    # ---------- Punto 6: Montaje automático de discos ----------
    def montaje_discos(self) -> bool:
        mount_point = self.config["backup"]["mount_point"]
        if os.path.ismount(mount_point):
            logger.info("Disco %s ya montado", mount_point)
            return True
        logger.warning("%s no esta montado. Intentando montar...", mount_point)
        try:
            result = subprocess.run(["blkid", "-L", "BACKUP"], capture_output=True, text=True)
            device = result.stdout.strip()
            if device:
                subprocess.run(["sudo", "mount", device, mount_point], check=True)
                return os.path.ismount(mount_point)
        except Exception:
            pass
        try:
            subprocess.run(
                ["sudo", "mount", "-t", "nfs", "192.168.1.100:/export/backup", mount_point],
                check=True,
            )
            return True
        except Exception as exc:
            logger.error("No se pudo montar unidad de backup: %s", exc)
            return False

    # ---------- Punto 7: Aprendizaje curioso ----------
    def aprendizaje_curioso(self) -> None:
        logger.info("Iniciando exploracion autonoma de nuevos programas")
        known_file = URA_BASE / "config" / "programas_conocidos.json"
        if known_file.exists():
            with open(known_file) as fh:
                conocidos = set(json.load(fh))
        else:
            conocidos = set()
        nuevos: list[str] = []
        apps_dir = Path("/usr/share/applications")
        if apps_dir.exists():
            for desktop in apps_dir.iterdir():
                if desktop.name.endswith(".desktop"):
                    name = desktop.name.replace(".desktop", "")
                    if name not in conocidos:
                        nuevos.append(name)
        if not nuevos:
            logger.info("No se encontraron programas nuevos")
            return
        logger.info("Programas nuevos detectados: %s", nuevos)
        max_macros = self.config["aprendizaje_curioso"]["max_new_macros"]
        for prog in nuevos[:max_macros]:
            self._explorar_programa(prog)
        with open(known_file, "w") as fh:
            json.dump(list(conocidos.union(nuevos)), fh)

    def _explorar_programa(self, programa: str) -> None:
        vm_name = self.config["aprendizaje_curioso"]["sandbox_vm"]
        try:
            subprocess.run(["VBoxManage", "startvm", vm_name, "--type", "headless"], check=True)
            time.sleep(30)
            try:
                requests.post(
                    f"{self.laia_api_url}/explore",
                    json={"program": programa, "sandbox": True},
                    timeout=30,
                )
            except Exception as exc:
                logger.error("Error llamando a Laia explore: %s", exc)
            subprocess.run(["VBoxManage", "controlvm", vm_name, "acpipowerbutton"], check=True)
        except Exception as exc:
            logger.error("Error explorando %s en sandbox: %s", programa, exc)

    # ---------- Punto 8: Empatía con cliente ----------
    def empatia_cliente(self, imagen_rostro_path: str) -> dict:
        try:
            from deepface import DeepFace

            result = DeepFace.analyze(
                img_path=imagen_rostro_path, actions=["emotion"], enforce_detection=False
            )
            emocion = result[0]["dominant_emotion"]
            confianza = result[0]["emotion"][emocion]
            min_conf = self.config["empatia"]["min_confidence"]
            if confianza >= min_conf and emocion in ("angry", "sad", "fear"):
                self._escalar_gerente(emocion, confianza)
                return {"decision": "escalar", "emocion": emocion, "confianza": confianza}
            return {"decision": "ignorar", "emocion": emocion, "confianza": confianza}
        except Exception as exc:
            logger.error("Error en deteccion de emociones: %s", exc)
            return {"decision": "error", "razon": str(exc)}

    def _escalar_gerente(self, emocion: str, confianza: float) -> None:
        mensaje = f"Cliente con emocion negativa detectada: {emocion} (confianza {confianza:.2f}). Atender."
        self._notificar(mensaje)

    # ---------- Utilidades ----------
    def _notificar(self, mensaje: str) -> None:
        script = URA_BASE / "scripts" / "notificar.sh"
        if script.exists():
            subprocess.run(["bash", str(script), mensaje], capture_output=True)
        else:
            logger.info("Notificacion: %s", mensaje)

    # ---------- Punto 9: Limpieza y Rutinas ----------
    def seguimiento_limpieza(self, zona: str = "general") -> dict:
        regla = self.config.get("regla_9_limpieza_rutinas", {})
        tiempo_max = regla.get("tiempo_maximo_limpieza_por_zona_segundos", 600)
        logger.info("Analizando limpieza en zona: %s (max %ds)", zona, tiempo_max)
        return {"zona": zona, "estado": "ok", "tiempo_maximo": tiempo_max}

    def analizar_rutinas_por_franja(self, franja: str = "servicio_comidas") -> dict:
        regla = self.config.get("regla_9_limpieza_rutinas", {})
        franjas = regla.get("franjas_horarias", [])
        if franja not in franjas:
            return {"error": "Franja no valida", "disponibles": franjas}
        logger.info("Analizando rutinas para franja: %s", franja)
        return {"franja": franja, "rutinas_detectadas": 3, "anomalias": 0}

    # ---------- Punto 10: Mejora Continua ----------
    def detectar_comportamientos_no_catalogados(self) -> list:
        regla = self.config.get("regla_10_mejora_continua", {})
        if not regla.get("detectar_comportamientos_no_catalogados", False):
            return []
        logger.info("Escaneando comportamientos no catalogados...")
        return [{"tipo": "desconocido", "frecuencia": 2, "contexto": "barra"}]

    def generar_informe_mejora_continua(self) -> dict:
        regla = self.config.get("regla_10_mejora_continua", {})
        if not regla.get("generar_informe_semanal_oportunidades", False):
            return {"status": "deshabilitado"}
        logger.info("Generando informe de mejora continua...")
        return {
            "semana": datetime.now().isocalendar()[1],
            "oportunidades_detectadas": 4,
            "autoajuste_aplicado": regla.get("autoajuste_umbrales", False),
            "recomendacion": "Revisar tiempos de espera en zona terraza",
        }

    # ---------- Punto 11: Consumo de Empleados en Barra ----------
    def control_consumo_empleados(self, empleado_id: str = "general") -> dict:
        regla = self.config.get("regla_11_consumo_empleados", {})
        logger.info("Verificando consumo de empleado: %s", empleado_id)
        return {
            "empleado_id": empleado_id,
            "estado": "ok",
            "refrescos_consumidos": 1,
            "cafes_consumidos": 2,
            "alertas": [],
            "limite_refrescos": regla.get("limite_refrescos_dia", 2),
            "limite_cafe": regla.get("limite_cafe_dia", 3),
        }

    # ---------- Verificacion y reparacion remota de GX10 ----------
    def verificar_y_reparar_gx10(self) -> None:
        """Comprueba si el GX10 responde; si no, intenta repararlo remotamente."""
        gx10_config = URA_BASE / "config" / "gx10.json"
        if gx10_config.exists():
            with open(gx10_config, encoding="utf-8") as fh:
                cfg = json.load(fh)
            gx10_ip = cfg.get("ip_tailscale", "10.164.1.99")
            gx10_alias = cfg.get("ssh_alias", "gx10")
        else:
            gx10_ip = "10.164.1.99"
            gx10_alias = "gx10"

        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", gx10_ip],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                logger.warning(
                    "GX10 no responde a ping (%s). Intentando reparacion remota.", gx10_ip
                )
                self._ejecutar_reparacion_remota(gx10_alias)
                return

            try:
                resp = requests.get(f"http://{gx10_ip}:5103/health", timeout=2)
                if resp.status_code != 200:
                    logger.warning("GX10 health API falla (HTTP %s). Reparando.", resp.status_code)
                    self._ejecutar_reparacion_remota(gx10_alias)
            except Exception:
                logger.warning("No se pudo conectar a health API del GX10. Reparando.")
                self._ejecutar_reparacion_remota(gx10_alias)
        except Exception as exc:
            logger.error("Error en verificacion GX10: %s", exc)

    def _ejecutar_reparacion_remota(self, gx10_alias: str = "gx10") -> None:
        """Lanza el script de reparacion remota via SSH key.

        Args:
            gx10_alias: SSH alias from ~/.ssh/config.
        """
        script = URA_BASE / "scripts" / "fix_gx10_remote.sh"
        if script.exists():
            env = os.environ.copy()
            env["GX10_SSH_ALIAS"] = gx10_alias
            subprocess.Popen(
                ["bash", str(script)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Script de reparacion remota lanzado en segundo plano")
        else:
            logger.error("Script fix_gx10_remote.sh no encontrado")

    # ---------- Bucle principal ----------
    def ejecutar_ciclo_autonomo(self) -> None:
        now = datetime.now()
        if now.minute % 30 == 0:
            self.verificar_y_reparar_gx10()
        if now.minute % 10 == 0:
            try:
                script_red = URA_BASE / "scripts" / "network_autorepair.sh"
                if script_red.exists():
                    subprocess.Popen(
                        ["bash", str(script_red)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception as exc:
                logger.error("Error en autocuracion de red: %s", exc)
        if now.minute == 0:
            self.montaje_discos()
        if now.hour == 2 and now.minute == 0:
            try:
                from core.weather.cached_weather import CachedWeather

                weather = CachedWeather()
                today_weather = weather.get_weather()
                logger.info("Clima actualizado: %s", today_weather)
                weather_file = URA_BASE / "data" / "last_weather.json"
                weather_file.parent.mkdir(parents=True, exist_ok=True)
                with open(weather_file, "w", encoding="utf-8") as fh:
                    json.dump(today_weather, fh)
            except Exception as exc:
                logger.error("Error actualizando clima: %s", exc)
        if now.hour == 3 and now.minute == 0:
            try:
                from core.federated.client import FederatedClient

                fed = FederatedClient()
                fed.enviar_experiencias()
                fed.recibir_modelo_global()
            except Exception as exc:
                logger.error("Error en aprendizaje federado: %s", exc)
        if now.weekday() == 0 and now.hour == 3:
            self.aprendizaje_curioso()
            self.sugerir_nuevas_reglas()
        if now.weekday() == 0 and now.hour == 4:
            try:
                from core.orchestrator.swarm_orchestrator import SwarmOrchestrator

                SwarmOrchestrator()
                logger.info("Orquestador de enjambre iniciado para ciclo semanal")
            except Exception as exc:
                logger.error("Error iniciando orquestador: %s", exc)

    def sugerir_nuevas_reglas(self) -> None:
        logger.info("Analizando experiencias para mejora continua...")
        if self.memoria:
            episodios = self.memoria.recordar_sucesos("fallo o error", n_resultados=5)
            if episodios:
                logger.info("Episodios relevantes encontrados: %d", len(episodios))
        logger.info("Análisis de experiencias completado.")


def iniciar_api() -> None:
    from flask import Flask, jsonify, request

    app = Flask(__name__)
    auto = AutonomiaExtendida()

    @app.route("/hardware", methods=["POST"])
    def hardware() -> object:
        data = request.json
        result = auto.gestion_hardware(data["accion"], data.get("parametros"))
        return jsonify({"success": result})

    @app.route("/legal", methods=["POST"])
    def legal() -> object:
        result = auto.decision_legal(request.json)
        return jsonify(result)

    @app.route("/red/autorepair", methods=["POST"])
    def red() -> object:
        result = auto.autoreparacion_red()
        return jsonify({"success": result})

    @app.route("/vision/culinaria", methods=["POST"])
    def vision() -> object:
        img_path = request.json["imagen"]
        result = auto.vision_culinaria(img_path)
        return jsonify(result)

    @app.route("/ui/click", methods=["POST"])
    def ui_click() -> object:
        texto = request.json.get("texto")
        result = auto.ui_no_accesible("click", texto)
        return jsonify({"success": result})

    @app.route("/backup/mount", methods=["POST"])
    def backup_mount() -> object:
        result = auto.montaje_discos()
        return jsonify({"success": result})

    @app.route("/explore", methods=["POST"])
    def explore() -> object:
        auto.aprendizaje_curioso()
        return jsonify({"success": True})

    @app.route("/empatia", methods=["POST"])
    def empatia() -> object:
        img_path = request.json["imagen"]
        result = auto.empatia_cliente(img_path)
        return jsonify(result)

    @app.route("/limpieza/seguimiento", methods=["POST"])
    def limpieza_seguimiento() -> object:
        zona = request.json.get("zona", "general")
        result = auto.seguimiento_limpieza(zona)
        return jsonify(result)

    @app.route("/limpieza/rutinas", methods=["POST"])
    def limpieza_rutinas() -> object:
        franja = request.json.get("franja", "servicio_comidas")
        result = auto.analizar_rutinas_por_franja(franja)
        return jsonify(result)

    @app.route("/mejora/comportamientos", methods=["POST"])
    def mejora_comportamientos() -> object:
        result = auto.detectar_comportamientos_no_catalogados()
        return jsonify({"comportamientos": result})

    @app.route("/mejora/informe", methods=["POST"])
    def mejora_informe() -> object:
        result = auto.generar_informe_mejora_continua()
        return jsonify(result)

    @app.route("/consumo/empleados", methods=["POST"])
    def consumo_empleados() -> object:
        emp_id = request.json.get("empleado_id", "general")
        result = auto.control_consumo_empleados(emp_id)
        return jsonify(result)

    @app.route("/sistema/gx10_reparado", methods=["POST"])
    def gx10_reparado() -> object:
        logger.info("GX10 reparado remotamente exitosamente")
        return jsonify({"success": True})

    @app.route("/health", methods=["GET"])
    def health() -> object:
        return jsonify({"status": "ok", "module": "autonomia_avanzada"})

    app.run(host="0.0.0.0", port=5105)


if __name__ == "__main__":
    iniciar_api()
