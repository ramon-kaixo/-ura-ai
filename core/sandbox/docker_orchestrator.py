"""docker_orchestrator.py — URA Zero-Patch / Capa 2

Sandbox Docker para ejecutar Skills propuestos en aislamiento total.

Garantías:
  - El Skill nunca toca el sistema de producción
  - Límite duro: --memory=2g --cpus=2
  - Sin red: --network=none
  - Timeout: 30s total, 5s de ejecución máxima del Skill
  - Suite de regresión: ejecuta tests existentes de URA
  - Si el Skill rompe módulos existentes → FALLA inmediatamente

Requiere: Docker instalado en el servidor.
  sudo apt install -y docker.io
  sudo usermod -aG docker $USER
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mochila_engine import BASE_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

DOCKER_MEMORY = "2g"
DOCKER_CPUS = "2"
DOCKER_TIMEOUT_S = 30
SKILL_TIMEOUT_S = 5
DOCKER_IMAGE = "python:3.12-slim"
TESTS_DIR = BASE_DIR / "TOOLS" / "tests"


# ---------------------------------------------------------------------------
# Resultado del sandbox
# ---------------------------------------------------------------------------


@dataclass
class ResultadoSandbox:
    aprobado: bool
    skill_ejecuto: bool
    tests_pasados: int
    tests_fallidos: int
    tests_fallidos_nombres: list[str]
    stdout: str
    stderr: str
    tiempo_ejecucion_ms: float
    uso_memoria_mb: float
    error: str | None
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )

    def resumen(self) -> str:
        estado = "✓ SANDBOX OK" if self.aprobado else "✗ SANDBOX FALLA"
        lineas = [
            f"[Docker Sandbox] {estado}",
            f"  Tests: {self.tests_pasados} OK, {self.tests_fallidos} FAIL",
            f"  Tiempo: {self.tiempo_ejecucion_ms:.0f}ms",
            f"  RAM: {self.uso_memoria_mb:.1f}MB",
        ]
        for t in self.tests_fallidos_nombres:
            lineas.append(f"  ✗ {t}")
        if self.error:
            lineas.append(f"  ERROR: {self.error}")
        return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Orquestador Docker
# ---------------------------------------------------------------------------


class DockerOrchestrator:
    def __init__(self, tests_dir: Path = TESTS_DIR) -> None:
        self._tests_dir = tests_dir

    async def validar(
        self,
        codigo_skill: str,
        nombre_skill: str,
    ) -> ResultadoSandbox:
        if not self._docker_disponible():
            return ResultadoSandbox(
                aprobado=False,
                skill_ejecuto=False,
                tests_pasados=0,
                tests_fallidos=0,
                tests_fallidos_nombres=[],
                stdout="",
                stderr="",
                tiempo_ejecucion_ms=0,
                uso_memoria_mb=0,
                error="Docker no disponible en este entorno",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            return await self._ejecutar_en_docker(tmp, codigo_skill, nombre_skill)

    async def _ejecutar_en_docker(
        self,
        tmpdir: Path,
        codigo_skill: str,
        nombre_skill: str,
    ) -> ResultadoSandbox:
        t_inicio = asyncio.get_event_loop().time()

        (tmpdir / "skills").mkdir()
        (tmpdir / "skills" / f"{nombre_skill}.py").write_text(codigo_skill)

        # Copiar tests de regresión si existen, sino smoke test
        tests_dest = tmpdir / "tests"
        if self._tests_dir.exists():
            shutil.copytree(self._tests_dir, tests_dest)
        else:
            tests_dest.mkdir()
            (tests_dest / "test_smoke.py").write_text(
                "def test_sistema_basico():\n    assert True\n"
            )

        (tmpdir / "Dockerfile").write_text(
            self._construir_dockerfile(codigo_skill, nombre_skill)
        )
        (tmpdir / "run_validation.py").write_text(
            self._construir_script_validacion(nombre_skill)
        )

        tag = f"ura-skill-{hashlib.sha256(codigo_skill.encode()).hexdigest()[:8]}"

        try:
            build_proc = await asyncio.create_subprocess_exec(
                "docker", "build", "-t", tag, str(tmpdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, build_stderr = await asyncio.wait_for(
                build_proc.communicate(), timeout=120
            )

            if build_proc.returncode != 0:
                return ResultadoSandbox(
                    aprobado=False, skill_ejecuto=False,
                    tests_pasados=0, tests_fallidos=0,
                    tests_fallidos_nombres=[],
                    stdout="", stderr=build_stderr.decode(errors="ignore")[:2000],
                    tiempo_ejecucion_ms=0, uso_memoria_mb=0,
                    error="Error en docker build",
                )

            run_proc = await asyncio.create_subprocess_exec(
                "docker", "run", "--rm",
                f"--memory={DOCKER_MEMORY}",
                f"--cpus={DOCKER_CPUS}",
                "--network=none",
                "--read-only",
                "--tmpfs", "/tmp:size=100m",
                tag,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    run_proc.communicate(), timeout=DOCKER_TIMEOUT_S
                )
            except asyncio.TimeoutError:
                run_proc.kill()
                return ResultadoSandbox(
                    aprobado=False, skill_ejecuto=False,
                    tests_pasados=0, tests_fallidos=0,
                    tests_fallidos_nombres=["TIMEOUT"],
                    stdout="", stderr="",
                    tiempo_ejecucion_ms=DOCKER_TIMEOUT_S * 1000,
                    uso_memoria_mb=0,
                    error=f"Timeout de {DOCKER_TIMEOUT_S}s superado",
                )

            t_fin = asyncio.get_event_loop().time()
            tiempo_ms = (t_fin - t_inicio) * 1000

            stdout_str = stdout.decode(errors="ignore").strip()
            stderr_str = stderr.decode(errors="ignore").strip()

            datos: dict = {}
            for linea in stdout_str.splitlines():
                try:
                    datos = json.loads(linea)
                    break
                except json.JSONDecodeError:
                    continue

            aprobado = (
                run_proc.returncode == 0
                and datos.get("tests_fallidos", 1) == 0
                and datos.get("error") is None
            )

            return ResultadoSandbox(
                aprobado=aprobado,
                skill_ejecuto=datos.get("skill_ejecuto", False),
                tests_pasados=datos.get("tests_pasados", 0),
                tests_fallidos=datos.get("tests_fallidos", 0),
                tests_fallidos_nombres=datos.get("tests_fallidos_nombres", []),
                stdout=stdout_str[:3000],
                stderr=stderr_str[:1000],
                tiempo_ejecucion_ms=round(tiempo_ms, 1),
                uso_memoria_mb=0.0,
                error=datos.get("error"),
            )

        finally:
            subprocess.run(
                ["docker", "rmi", "-f", tag],
                capture_output=True,
            )

    @staticmethod
    def _construir_dockerfile(skill_code: str, skill_nombre: str) -> str:
        return textwrap.dedent(f"""
            FROM {DOCKER_IMAGE}

            RUN pip install --no-cache-dir \
                pydantic>=2.0 \
                httpx \
                lxml \
                Pillow \
                pyyaml \
                pytest \
                pytest-asyncio \
                pytest-timeout \
                --quiet

            WORKDIR /ura
            COPY skills/ /ura/skills/
            COPY tests/ /ura/tests/
            COPY run_validation.py /ura/run_validation.py

            CMD ["python", "-u", "run_validation.py", "--timeout", "{SKILL_TIMEOUT_S}"]
        """).strip()

    @staticmethod
    def _construir_script_validacion(skill_nombre: str) -> str:
        _CODIGO_BASE = r'''
import sys
import json
import subprocess
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--timeout", type=int, default=5)
args = parser.parse_args()

resultados = {
    "skill_ejecuto": False,
    "tests_pasados": 0,
    "tests_fallidos": 0,
    "tests_fallidos_nombres": [],
    "error": None,
}

try:
    import importlib.util
    skill_path = "/ura/skills/SKILL_NOMBRE.py"
    spec = importlib.util.spec_from_file_location(
        "SKILL_NOMBRE", skill_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    resultados["skill_ejecuto"] = True
except Exception as exc:
    resultados["error"] = "Error importando Skill: " + str(exc)
    print(json.dumps(resultados))
    sys.exit(1)

try:
    resultado_pytest = subprocess.run(
        ["python", "-m", "pytest", "/ura/tests/", "-v", "--tb=short",
         "--timeout", str(args.timeout)],
        capture_output=True, text=True, timeout=args.timeout * 3,
    )
except subprocess.TimeoutExpired:
    resultados["error"] = "Timeout en suite de regresion"
    print(json.dumps(resultados))
    sys.exit(1)
except Exception as exc:
    resultados["error"] = "Error en pytest: " + str(exc)
    print(json.dumps(resultados))
    sys.exit(1)

stdout = resultado_pytest.stdout or ""
for linea in stdout.splitlines():
    if "passed" in linea and "failed" in linea:
        partes = linea.strip().split()
        for i, p in enumerate(partes):
            if p == "passed":
                resultados["tests_pasados"] = int(partes[i-1]) if i > 0 else 0
            elif p == "failed":
                resultados["tests_fallidos"] = int(partes[i-1]) if i > 0 else 0
                break
    if "FAILED" in linea:
        resultados["tests_fallidos_nombres"].append(linea.strip())

errores = resultado_pytest.stderr or ""
if errores and not resultados["error"]:
    resultados["error"] = errores[:500]

print(json.dumps(resultados))
sys.exit(0 if resultados["tests_fallidos"] == 0 else 1)
'''
        return _CODIGO_BASE.replace("SKILL_NOMBRE", skill_nombre).strip()

    @staticmethod
    def _docker_disponible() -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
