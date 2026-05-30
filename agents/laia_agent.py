import json
import logging
import os
import subprocess
import time
from typing import Any

import numpy as np

from core.safety import Safety
from core.action_executor import ActionExecutor
from core.screen_reader import ScreenReader
from core.explorer import Explorer
from core.planner import TaskPlanner
from core.planner_react import ReActPlanner
from core.governance import Governance
from core.memory.semantic_brain import SemanticBrain
from core.memory.episodic_memory import EpisodicMemory
from core.vision.state_verifier import StateVerifier
from core.api_connector import APIConnector
from core.confidence.uncertainty import ConfidenceEstimator
from core.feedback.latent_reward import LatentReward
from agents.laia_tuneladora_agent import TuneladoraBridge
from agents.dialogue_manager import DialogueManager

logger = logging.getLogger(__name__)

FRIGATE_URL = os.getenv("FRIGATE_URL", "http://localhost:5000")
AUTONOMIA_URL = os.getenv("AUTONOMIA_URL", "http://localhost:5105")
MODEL_CODIFICACION = os.getenv("MODEL_CODIFICACION", "qwen3:32b")
GX10_URL = os.getenv("GX10_URL", "http://10.164.1.99:11434/api/chat")


class LaiaAgent:
    def __init__(self) -> None:
        self.safety = Safety()
        self.executor = ActionExecutor(self.safety)
        self.reader = ScreenReader(use_vlm=True)
        self.explorer = Explorer(self.executor, self.reader)
        self.planner = TaskPlanner()
        self.react_planner = ReActPlanner(self)
        self.governance = Governance()
        self.tuneladora = TuneladoraBridge()
        self.brain = SemanticBrain()
        self.episodic_memory = EpisodicMemory()
        self.verifier = StateVerifier()
        self.api_connectors: dict[str, APIConnector] = {}
        self._stt_model: Any = None
        self.ultima_accion_contexto: str = ""
        self.confidence = ConfidenceEstimator()
        self.latent = LatentReward()
        self.dialogue = DialogueManager()
        self.user_id = "gerente_principal"

    def _get_stt_model(self) -> Any:
        if self._stt_model is None:
            from faster_whisper import WhisperModel

            self._stt_model = WhisperModel("base", device="cpu", compute_type="int8")
        return self._stt_model

    def _stt(self, audio: np.ndarray) -> str:
        model = self._get_stt_model()
        segs, _ = model.transcribe(audio, language="es")
        return " ".join(s.text for s in segs).strip()

    def _tts(self, texto: str) -> None:
        subprocess.run(["say", texto], check=False)

    def ejecutar_con_manual(self, tarea: str, app_name: str = "TPV") -> bool:
        conf = self.confidence.calcular_confianza(tarea, app_name)
        if conf < 0.7:
            self._tts(f"No estoy segura (confianza {conf:.0%}). Procedo con {tarea}?")
            time.sleep(5)
        instruccion = self.brain.obtener_contexto_manual(tarea, app_name)
        if instruccion:
            prompt = (
                f"Tarea: {tarea}\n"
                f"Instruccion del manual: {instruccion}\n"
                f"Genera una lista de acciones en JSON (formato: "
                f'[{{"action":"click", "target":"texto"}}, {{"action":"write", "text":"..."}}]) '
                f"Solo devuelve el JSON, sin explicaciones."
            )
            try:
                respuesta = self._llm_plan(prompt)
                pasos = json.loads(respuesta)
                for paso in pasos:
                    if paso["action"] == "click":
                        bbox = self.reader.find_element_by_text(paso["target"])
                        if bbox:
                            self.executor.click_with_retry(bbox[0], bbox[1])
                        else:
                            self.reader.find_element_by_text(paso["target"])
                    elif paso["action"] == "write":
                        self.executor.write(paso["text"])
                exito = True
            except Exception as exc:
                logger.error("Error ejecutando con manual: %s", exc)
                exito = self.planner.plan(tarea) != [
                    {"action": "fail", "reason": "no se pudo planificar"}
                ]
        else:
            exito = False
        accion_id = f"{int(time.time())}_{tarea[:20]}"
        self.latent.registrar_accion(accion_id, tarea, {"app": app_name, "confianza": conf})
        self.confidence.registrar_resultado(tarea, exito)
        return exito

    def _llm_plan(self, prompt: str) -> str:
        import requests

        resp = requests.post(
            f"{GX10_URL}/api/generate",
            json={"model": MODEL_CODIFICACION, "prompt": prompt, "stream": False},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["response"]

    def process_command(self, natural_language_command: str) -> bool:
        cmd = natural_language_command.lower()
        self.ultima_accion_contexto = cmd
        if cmd.startswith("ura,") or cmd.startswith("ura "):
            cmd = cmd[4:].strip()
            respuesta = self.dialogue.generate_response(self.user_id, cmd)
            self._tts(respuesta)
            return True
        if "lanza buzo" in cmd:
            buzo = cmd.split("lanza buzo")[-1].strip()
            result = self.tuneladora.lanzar_buzo(buzo)
            return result["returncode"] == 0
        if "reparar red" in cmd:
            result = self.call_autonomia("red/autorepair")
            return result.get("success", False)
        if "montar disco" in cmd or "montar backup" in cmd:
            result = self.call_autonomia("backup/mount")
            return result.get("success", False)
        if "limpieza" in cmd or "rutinas" in cmd:
            franja = "servicio_comidas" if "comidas" in cmd else "general"
            if "limpieza" in cmd:
                self.call_autonomia("limpieza/seguimiento", {"zona": franja})
            else:
                self.call_autonomia("limpieza/rutinas", {"franja": franja})
            return True
        if "mejora continua" in cmd or "comportamientos" in cmd:
            if "comportamientos" in cmd:
                self.call_autonomia("mejora/comportamientos")
            else:
                self.call_autonomia("mejora/informe")
            return True
        if "consumo" in cmd and "empleado" in cmd:
            self.call_autonomia("consumo/empleados", {"empleado_id": "general"})
            return True
        if "planifica" in cmd:
            objetivo = cmd.split("planifica")[-1].strip()
            return self.react_planner.ejecutar_objetivo(objetivo, "TPV")
        if cmd.startswith("+1") or cmd.startswith("-1"):
            delta = 1 if cmd.startswith("+1") else -1
            self.episodic_memory.registrar_suceso(
                f"Feedback {'positivo' if delta > 0 else 'negativo'} para {self.ultima_accion_contexto}",
                {"reward": delta},
            )
            return True
        if "explora" in cmd:
            app = cmd.split("explora")[-1].strip() or None
            from core.discovery.fuzzer import UIFuzzer

            fuzzer = UIFuzzer()
            resultado = fuzzer.explorar_aplicacion(app_path=app, tiempo_maximo=120)
            self._tts(f"Exploracion completada. Se encontraron {len(resultado)} estados.")
            return True
        if "clima" in cmd or "tiempo" in cmd:
            from core.weather.cached_weather import CachedWeather

            weather = CachedWeather()
            today = weather.get_weather()
            self._tts(
                f"Precipitacion {today.get('precipitacion', 0)}, temperatura maxima {today.get('temp_max', 20)}"
            )
            return True
        if "macro" in cmd and "aprender" in cmd:
            return self.explorer.learn_macro("ejemplo", cmd)
        if "macro" in cmd and "ejecutar" in cmd:
            return self.explorer.run_macro("ejemplo")
        if "clic en" in cmd:
            target = cmd.split("clic en")[-1].strip()
            bbox = self.reader.find_element_by_text(target)
            if bbox:
                cx = (bbox[0] + bbox[2]) // 2
                cy = (bbox[1] + bbox[3]) // 2
                self.executor.click(cx, cy)
                return True
        if "escribe" in cmd:
            text = cmd.split("escribe")[-1].strip()
            self.executor.write(text)
            return True
        return False

    def call_autonomia(self, endpoint: str, data: dict | None = None) -> dict:
        import requests

        url = f"{AUTONOMIA_URL}/{endpoint}"
        try:
            resp = requests.post(url, json=data, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("Autonomia API fallo en %s: %s", endpoint, exc)
            return {"success": False, "error": str(exc)}

    def execute_planned_task(self, goal: str) -> bool:
        if self.governance.should_ask_human(goal):
            if not self.safety.confirm_action(f"Tarea de riesgo: {goal}. ¿Continuar?"):
                return False
        plan = self.planner.plan(goal)
        return self.planner.execute_plan(plan, self.executor, self.reader)

    def query_frigate_events(
        self,
        label: str = "person",
        after: int | None = None,
        before: int | None = None,
        zone: str | None = None,
    ) -> list[dict]:
        import requests

        url = f"{FRIGATE_URL}/api/events?label={label}"
        if after:
            url += f"&after={after}"
        if before:
            url += f"&before={before}"
        if zone:
            url += f"&zone={zone}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        events = resp.json()
        unique_ids = {e.get("id", "") for e in events}
        logger.info("Frigate: %d eventos, %d unicos", len(events), len(unique_ids))
        return [{"id": uid, "label": label} for uid in unique_ids]

    def run_repl(self) -> None:
        self._tts("Asistente iniciado. Diga URA para activar, salir para terminar.")
        print("Laia agent ready. Di 'URA' para activar, 'salir' para terminar.")
        import sounddevice as sd

        TASA = 16000
        while not self.safety.is_panic():
            print("   🎤 Escuchando...")
            audio = sd.rec(int(5 * TASA), samplerate=TASA, channels=1)
            sd.wait()
            audio = audio.flatten().astype(np.float32)
            texto = self._stt(audio)
            print(f"   📝 {texto}")
            if "ura" not in texto.lower():
                continue
            if "salir" in texto.lower():
                break
            self._tts("Que necesita")
            audio2 = sd.rec(int(6 * TASA), samplerate=TASA, channels=1)
            sd.wait()
            audio2 = audio2.flatten().astype(np.float32)
            orden = self._stt(audio2)
            if not orden:
                continue
            resultado = self.execute_planned_task(orden)
            self._tts("Hecho" if resultado else "No entendi")
