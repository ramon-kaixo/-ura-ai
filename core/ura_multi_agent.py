#!/usr/bin/env python3
"""URA Multi-Agent System — Boilerplate de Arquitectura Autónoma.

📖 MANUAL DE USO RÁPIDO:
  python3 core/ura_multi_agent.py                     # Iniciar bucle principal
  python3 core/ura_multi_agent.py --modo orquestar    # Solo orquestar (decidir)
  python3 core/ura_multi_agent.py --modo reparar      # Solo reparar errores
  python3 core/ura_multi_agent.py --modo ciclo        # Ciclo completo (detectar→reparar→validar)

🔒 ARQUITECTURA:
  3 Agentes:
    ORQUESTADOR (Qwen 14B): Decide qué hacer según estado del sistema
    EJECUTOR (DeepSeek 6.7B): Refactoriza funciones grandes
    REPARADOR (auto_reglas + LLM): Repara errores en 3 niveles

  Bucle de auto-arreglo:
    DETECTAR → AISLAR → REPARAR (3 niveles) → VALIDAR → ACTUALIZAR

  Estado compartido: .nervioso/conciencia.json
  Telemetría: RAM, CPU, tokens, F821, modelos disponibles
"""

import contextlib
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("ura.multi_agent")

# ── Configuración ──────────────────────────────────────────────────────────

URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.164.1.99:11434")
SCRIPTS = URA_ROOT / "scripts/pro"
NERVIOSO = URA_ROOT / ".nervioso"
MAX_CICLO_S = 300  # Timeout global del ciclo de auto-mejora (5 minutos)

MODELOS = {
    "orquestador": "qwen2.5-coder:14b",
    "ejecutor": "deepseek-coder:6.7b",
    "reparador_rapido": "deepseek-coder:6.7b",
    "reparador_potente": "qwen3:32b-q8_0",
    "revisor": "qwen2.5-coder:14b-instruct-q8_0",
}

RUFF = str(URA_ROOT / ".venv/bin/ruff")


# ── 1. Telemetría ──────────────────────────────────────────────────────────


class Telemetria:
    """Sistema de telemetría en tiempo real."""

    @staticmethod
    def hardware() -> dict:
        """Estado del hardware."""
        metrics = {"timestamp": datetime.now(UTC).isoformat()}
        try:
            import psutil

            vm = psutil.virtual_memory()
            metrics["ram_total_mb"] = vm.total // (1024 * 1024)
            metrics["ram_libre_mb"] = vm.available // (1024 * 1024)
            metrics["ram_pct"] = vm.percent
            metrics["cpu_pct"] = psutil.cpu_percent(interval=0.1)
        except ImportError:
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if "MemAvailable" in line:
                            metrics["ram_libre_mb"] = int(line.split()[1]) // 1024
                        elif "MemTotal" in line:
                            metrics["ram_total_mb"] = int(line.split()[1]) // 1024
            except Exception as e:
                log.warning(f"Error leyendo /proc/meminfo: {e}")
                metrics["ram_libre_mb"] = 8192
                metrics["ram_total_mb"] = 121920
        return metrics

    @staticmethod
    def red() -> dict:
        """Estado de la red y servicios."""
        status = {}
        # Model Router
        try:
            r = subprocess.run(
                [
                    "curl",
                    "-s",
                    "--max-time",
                    "2",
                    f"{os.environ.get('MODEL_ROUTER_URL', 'http://10.164.1.99:11435')}/health",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            status["model_router"] = "ok" if r.returncode == 0 and "ok" in r.stdout else "down"
        except Exception:
            log.exception("Error checking model router health")
            status["model_router"] = "down"

        # Ollama
        try:
            r = subprocess.run(
                ["curl", "-s", "--max-time", "2", f"{OLLAMA_URL}/api/tags"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                status["ollama"] = f"{len(data.get('models', []))} modelos"
            else:
                status["ollama"] = "down"
        except Exception:
            log.exception("Error checking Ollama health")
            status["ollama"] = "down"

        return status

    @staticmethod
    def llm_stats() -> dict:
        """Estadísticas de uso del LLM."""
        config_path = NERVIOSO / "chunk_config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            return {
                "chunk_actual": data.get("chunk_actual", 8192),
                "modelo": data.get("modelo", "?"),
                "historico_ajustes": len(data.get("historico", [])),
            }
        return {"chunk_actual": 8192, "modelo": "?", "historico_ajustes": 0}

    @staticmethod
    def f821_count() -> int:
        """Cuenta F821 en el código."""
        try:
            r = subprocess.run(
                [RUFF, "check", "--select", "F821", "."],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(URA_ROOT),
                check=False,
            )
            return r.stdout.count("F821")
        except Exception:
            log.exception("Error counting F821")
            return -1

    def reporte_completo(self) -> dict:
        """Reporte unificado de telemetría."""
        return {
            "hardware": self.hardware(),
            "red": self.red(),
            "llm": self.llm_stats(),
            "f821": self.f821_count(),
        }


# ── 2. Estado Compartido (Conciencia) ──────────────────────────────────────


class Conciencia:
    """Memoria unificada del sistema. Archivo: .nervioso/conciencia.json."""

    PATH = NERVIOSO / "conciencia.json"
    _lock = threading.Lock()

    @classmethod
    def leer(cls) -> dict:
        if cls.PATH.exists():
            try:
                return json.loads(cls.PATH.read_text())
            except Exception:
                log.exception("Error reading conciencia.json")
                pass  # noqa: S110
        return cls._nuevo()

    @classmethod
    def _nuevo(cls) -> dict:
        return {
            "estado_general": "ok",
            "nivel_error": 0,
            "procesos": {
                "orquestador": {"estado": "idle"},
                "ejecutor": {"estado": "idle"},
                "reparador": {"estado": "idle"},
            },
            "contexto_global": {
                "ciclo_actual": 0,
                "progreso": "0/0",
                "errores_acumulados": [],
                "arreglos_aplicados": [],
            },
        }

    @classmethod
    def escribir(cls, data: dict) -> None:
        with cls._lock:
            cls.PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = cls.PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            tmp.replace(cls.PATH)

    @classmethod
    def actualizar_proceso(cls, nombre: str, estado: str) -> None:
        data = cls.leer()
        data["procesos"][nombre] = {
            "estado": estado,
            "ultima_actualizacion": datetime.now(UTC).isoformat(),
        }
        cls.escribir(data)

    @classmethod
    def registrar_error(cls, nivel: int, mensaje: str) -> None:
        data = cls.leer()
        data["nivel_error"] = max(data["nivel_error"], nivel)
        data["contexto_global"]["errores_acumulados"].append(
            {
                "nivel": nivel,
                "mensaje": mensaje,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        if len(data["contexto_global"]["errores_acumulados"]) > 50:
            data["contexto_global"]["errores_acumulados"] = data["contexto_global"]["errores_acumulados"][-50:]
        cls.escribir(data)

    @classmethod
    def nivel_error(cls) -> int:
        return cls.leer().get("nivel_error", 0)


# ── 3. Agentes ─────────────────────────────────────────────────────────────


class AgenteOrquestador:
    """Decide qué acción tomar según el estado del sistema. Modelo: Qwen 14B."""

    MODELO = MODELOS["orquestador"]

    def decidir(self, telemetria: dict, conciencia: dict) -> tuple[str, str]:
        """Devuelve (accion, razon)."""
        ram = telemetria.get("hardware", {}).get("ram_pct", 0)
        f821 = telemetria.get("f821", 99)

        # Decisiones deterministas primero (sin LLM)
        if ram > 85:
            return "PAUSAR", f"RAM al {ram}%, esperando a que baje"

        if f821 > 10:
            return "REPARAR", f"{f821} F821 detectados, lanzando reparador"

        funciones_pendientes = self._contar_pendientes()
        if funciones_pendientes > 0 and ram < 85:
            return "REFACTORIZAR", f"{funciones_pendientes} funciones pendientes"

        return "ESPERAR", "Sistema estable, sin acciones necesarias"

    @staticmethod
    def _contar_pendientes() -> int:
        """Cuenta funciones grandes pendientes vía AST."""
        import ast

        total = 0
        try:
            for py_file in URA_ROOT.rglob("*.py"):
                p = str(py_file)
                if any(x in p for x in ["/.venv/", "/.git/", "/backups/", "/site-packages/"]):
                    continue
                try:
                    tree = ast.parse(py_file.read_text())
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if hasattr(node, "end_lineno") and node.end_lineno and node.lineno:
                                if node.end_lineno - node.lineno > 80:
                                    total += 1
                except Exception as e:
                    log.warning(f"Error parseando AST en {py_file}: {e}")
        except Exception as e:
            log.warning(f"Error contando funciones pendientes: {e}")
        return total


class AgenteEjecutor:
    """Refactoriza funciones grandes. Modelo: DeepSeek 6.7B."""

    MODELO = MODELOS["ejecutor"]

    def ejecutar(self, workers: int = 4, timeout: int = 3600) -> dict:
        """Lanza workers de refactorización."""
        resultados = {"ok": 0, "err": 0, "workers": []}
        workers_list = []

        for i in range(workers):
            env = os.environ.copy()
            env["REFACTOR_WORKER_ID"] = str(i)
            env["REFACTOR_WORKER_TOTAL"] = str(workers)
            env["REFACTOR_MODEL"] = self.MODELO
            env["REFACTOR_MODEL_FALLBACK"] = "qwen2.5-coder:14b"
            env["MIN_LINES"] = "80"
            env["OLLAMA_URL"] = OLLAMA_URL
            env["URA_ROOT"] = str(URA_ROOT)

            proc = subprocess.Popen(
                [sys.executable, "-u", str(SCRIPTS / "refactor_large_functions.py")],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(URA_ROOT),
            )
            workers_list.append(proc)

        for i, proc in enumerate(workers_list):
            dead_man = threading.Timer(300, lambda p=proc: p.kill())
            dead_man.daemon = True
            dead_man.start()
            try:
                out = proc.communicate(timeout=timeout)[0] or ""
                ok = out.count("✅ OK")
                err = out.count("❌ Error")
                resultados["ok"] += ok
                resultados["err"] += err
                resultados["workers"].append({"id": i + 1, "ok": ok, "err": err})
            except subprocess.TimeoutExpired:
                proc.kill()
                with contextlib.suppress(Exception):
                    proc.wait(timeout=5)
                resultados["workers"].append({"id": i + 1, "ok": 0, "err": 1, "timeout": True})
            finally:
                dead_man.cancel()
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except Exception:
                        log.exception("Error terminating worker process")
                        with contextlib.suppress(Exception):
                            proc.kill()

        return resultados


class AgenteReparador:
    """Repara errores en 3 niveles: determinista → LLM rápido → LLM potente."""

    def reparar(self, archivo: str, errores: list) -> tuple[bool, int, str]:
        """Intenta reparar un archivo. Retorna (reparado, nivel, mensaje)."""
        ruta = Path(archivo) if isinstance(archivo, str) else archivo
        if not ruta.exists():
            return False, -1, "Archivo no encontrado"

        # Backup de seguridad
        backup = ruta.with_suffix(".bak_repair")
        if not backup.exists():
            shutil.copy2(ruta, backup)

        # Nivel 1: Determinista (auto_reglas + ruff)
        reparado = self._nivel_1(ruta)
        if reparado:
            return True, 1, "Reparado por auto_reglas (determinista)"

        # Nivel 2: LLM rápido (DeepSeek 6.7B)
        reparado = self._nivel_2(ruta, "deepseek-coder:6.7b")
        if reparado:
            return True, 2, "Reparado por DeepSeek 6.7B (LLM rápido)"

        # Nivel 3: LLM potente (Qwen 32B)
        reparado = self._nivel_3(ruta)
        if reparado:
            return True, 3, "Reparado por OpenCode 32B (LLM potente)"

        return False, 0, "No se pudo reparar (watermark creado)"

    def _nivel_1(self, ruta: Path) -> bool:
        """Reparación determinista: auto_reglas + ruff."""
        try:
            subprocess.run(
                [sys.executable, str(SCRIPTS / "auto_reglas.py"), "--aplicar", str(ruta)],
                capture_output=True,
                timeout=15,
                cwd=str(URA_ROOT),
                check=False,
            )
            subprocess.run([RUFF, "check", "--fix", str(ruta)], capture_output=True, timeout=15, check=False)
            subprocess.run([RUFF, "format", str(ruta)], capture_output=True, timeout=10, check=False)
            # Verificar que compile
            compile(ruta.read_text(), str(ruta), "exec")
            return True
        except Exception:
            log.exception("Error in nivel_1 repair for %s", ruta)
            return False

    def _nivel_2(self, ruta: Path, modelo: str) -> bool:
        """Reparación con LLM rápido."""
        try:
            codigo = ruta.read_text()
            # Detectar F821 del archivo
            r = subprocess.run(
                [RUFF, "check", "--select", "F821", str(ruta)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if r.returncode == 0:
                return True  # Ya está limpio

            errores = r.stderr or r.stdout or ""
            prompt = (
                f"Repara los siguientes errores de Python SIN cambiar la lógica:\n\n"
                f"ERRORES:\n{errores[:2000]}\n\n"
                f"CODIGO:\n```python\n{codigo[:6000]}\n```\n\n"
                f"Devuelve SOLO el código reparado."
            )

            payload = json.dumps(
                {
                    "model": modelo,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 4096},
                },
            ).encode()
            import urllib.request

            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                fixed = json.loads(resp.read()).get("response", "")

            if fixed and "```" in fixed:
                fixed = fixed.split("```python")[1].split("```")[0] if "```python" in fixed else fixed.split("```")[1]

            ruta.write_text(fixed)
            compile(fixed, str(ruta), "exec")
            return True
        except Exception:
            log.exception("Error in nivel_2 repair for %s", ruta)
            return False

    def _nivel_3(self, ruta: Path) -> bool:
        """Reparación con OpenCode (puerto 8081, qwen3:32b-q8_0)."""
        try:
            codigo = ruta.read_text()
            r = subprocess.run(
                [RUFF, "check", "--select", "F821", str(ruta)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            payload = json.dumps(
                {
                    "model": "ollama/qwen3:32b-q8_0",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Eres un reparador de código Python. Solo devuelves código corregido.",
                        },
                        {
                            "role": "user",
                            "content": f"Repara SIN cambiar lógica:\n{r.stderr or ''}\n\n```python\n{codigo[:6000]}\n```",
                        },
                    ],
                    "temperature": 0.0,
                },
            ).encode()
            import urllib.request

            req = urllib.request.Request(
                "http://localhost:8081/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                fixed = json.loads(resp.read())["choices"][0]["message"]["content"]

            if fixed and "```" in fixed:
                fixed = fixed.split("```python")[1].split("```")[0] if "```python" in fixed else fixed.split("```")[1]

            ruta.write_text(fixed)
            compile(fixed, str(ruta), "exec")
            return True
        except Exception:
            log.exception("Error in nivel_3 repair for %s", ruta)
            return False


# ── 4. Bucle de Auto-Arreglo ───────────────────────────────────────────────


class SelfHealingLoop:
    """Bucle completo: DETECTAR → AISLAR → REPARAR → VALIDAR → ACTUALIZAR."""

    def __init__(self) -> None:
        self.orquestador = AgenteOrquestador()
        self.ejecutor = AgenteEjecutor()
        self.reparador = AgenteReparador()
        self.telemetria = Telemetria()
        self._fallos_consecutivos = 0

    def ejecutar(self, archivo: str | None = None) -> dict:
        """Ejecuta un ciclo completo."""
        inicio = time.monotonic()
        reporte = {"timestamp": datetime.now(UTC).isoformat(), "pasos": []}

        # 1. Telemetría + conciencia
        tele = self.telemetria.reporte_completo()
        conciencia = Conciencia.leer()

        # 2. Orquestador decide
        accion, razon = self.orquestador.decidir(tele, conciencia)
        reporte["accion"] = accion
        reporte["razon"] = razon
        reporte["pasos"].append({"paso": "orquestar", "accion": accion, "razon": razon})

        # 3. Ejecutar acción
        if accion == "REFACTORIZAR":
            Conciencia.actualizar_proceso("ejecutor", "activo")
            result = self.ejecutor.ejecutar(workers=4)
            reporte["refactor"] = result
            Conciencia.actualizar_proceso("ejecutor", "idle")

        elif accion == "REPARAR":
            Conciencia.actualizar_proceso("reparador", "activo")
            # Encontrar archivos con F821
            try:
                r = subprocess.run(
                    [RUFF, "check", "--select", "F821", "--output-format", "json", "."],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(URA_ROOT),
                    check=False,
                )
                data = json.loads(r.stdout)
                files = {x["filename"] for x in data if "/.venv/" not in x.get("filename", "")}
                for f in list(files)[:5]:
                    reparado, nivel, msg = self.reparador.reparar(f, [])
                    reporte["pasos"].append(
                        {
                            "paso": "reparar",
                            "archivo": f,
                            "reparado": reparado,
                            "nivel": nivel,
                            "mensaje": msg,
                        },
                    )
            except Exception as e:
                reporte["pasos"].append({"paso": "reparar", "error": str(e)})
            Conciencia.actualizar_proceso("reparador", "idle")

        elif accion == "PAUSAR":
            reporte["pasos"].append({"paso": "pausar", "mensaje": "RAM saturada"})
            time.sleep(30)

        # 4. Post-ciclo: ruff fix + auto-reglas
        subprocess.run(
            [RUFF, "check", "--fix", "."],
            capture_output=True,
            timeout=60,
            cwd=str(URA_ROOT),
            check=False,
        )
        subprocess.run(
            [sys.executable, str(SCRIPTS / "auto_reglas.py"), "--generar"],
            capture_output=True,
            timeout=15,
            cwd=str(URA_ROOT),
            check=False,
        )

        # 5. Actualizar conciencia
        f821_final = self.telemetria.f821_count()
        Conciencia.actualizar_proceso("orquestador", "idle")

        # Timeout global check
        if time.monotonic() - inicio > MAX_CICLO_S:
            reporte["resultado"] = "TIMEOUT"
            reporte["razon"] = f"Sobrepasado {MAX_CICLO_S}s limite"
            self._fallos_consecutivos += 1
            return reporte

        # Track fallos for circuit breaker
        if reporte.get("resultado") in ("ROLLBACK", "TIMEOUT"):
            self._fallos_consecutivos += 1
        else:
            self._fallos_consecutivos = 0

        reporte["f821_final"] = f821_final
        reporte["tiempo_total_s"] = round(time.monotonic() - inicio, 1)
        reporte["ram_final_mb"] = self.telemetria.hardware().get("ram_libre_mb", 0)

        return reporte


# ── 5. Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="URA Multi-Agent System")
    parser.add_argument(
        "--modo",
        choices=["orquestar", "reparar", "ciclo"],
        default="ciclo",
        help="Modo de operación",
    )
    parser.add_argument("--archivo", help="Archivo a reparar (solo con --modo reparar)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    loop = SelfHealingLoop()

    if args.modo == "reparar" and args.archivo:
        reparador = AgenteReparador()
        reparado, nivel, _msg = reparador.reparar(args.archivo, [])
        if args.json:
            pass
        else:
            {1: "🔧", 2: "🤖", 3: "🧠"}.get(nivel, "❌")
        sys.exit(0 if reparado else 1)

    elif args.modo == "orquestar":
        tele = Telemetria().reporte_completo()
        conciencia = Conciencia.leer()
        _accion, _razon = AgenteOrquestador().decidir(tele, conciencia)

    else:  # ciclo completo
        loop.ejecutar()
        if args.json:
            pass
        else:
            pass


if __name__ == "__main__":
    main()
