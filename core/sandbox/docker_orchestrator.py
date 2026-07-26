"""docker_orchestrator.py — Capa 2: Sandbox Docker para Skills."""

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
from datetime import UTC, datetime
from pathlib import Path

from mochila_engine import BASE_DIR

logger = logging.getLogger(__name__)
log = logger
MEM = "2g"
CPU = "2"
TIMEOUT = 30
SKILL_TO = 5
IMG = "python:3.12-slim"
TD = BASE_DIR / "TOOLS" / "tests"


@dataclass
class ResultadoSandbox:
    ok: bool
    ejecuto: bool
    pasados: int
    fallidos: int
    fallos: list[str]
    stdout: str
    stderr: str
    tiempo_ms: float
    ram_mb: float
    error: str | None
    ts: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    def resumen(self):
        e = "OK" if self.ok else "FAIL"
        r = [f"[Sandbox] {e}"] + [f"  Tests: {self.pasados} OK, {self.fallidos} FAIL"] + [f"  {t}" for t in self.fallos]
        if self.error:
            r.append(f"  ERROR: {self.error}")
        return "\n".join(r)


class DockerOrchestrator:
    def __init__(self, td=TD) -> None:
        self._td = td

    async def validar(self, codigo, nombre):
        if not self._docker():
            return ResultadoSandbox(False, False, 0, 0, [], "", "", 0, 0, "Docker no disponible")
        with tempfile.TemporaryDirectory() as d:
            return await self._run(Path(d), codigo, nombre)

    async def _run(self, d, cod, nom):
        t0 = asyncio.get_event_loop().time()
        (d / "skills").mkdir()
        (d / "skills" / f"{nom}.py").write_text(cod)
        td = d / "tests"
        if self._td.exists():
            shutil.copytree(self._td, td)
        else:
            td.mkdir()
            (td / "ts.py").write_text("def t(): assert True")
        (d / "Dockerfile").write_text(self._df(cod, nom))
        (d / "rv.py").write_text(self._rv(nom))
        tag = f"us-{hashlib.sha256(cod.encode()).hexdigest()[:8]}"
        try:
            b = await asyncio.create_subprocess_exec("docker", "build", "-t", tag, str(d), stdout=-1, stderr=-1)
            _, be = await asyncio.wait_for(b.communicate(), 120)
            if b.returncode:
                return ResultadoSandbox(
                    False,
                    False,
                    0,
                    0,
                    [],
                    "",
                    be.decode(errors="ignore")[:2000],
                    0,
                    0,
                    "build fail",
                )
            rp = await asyncio.create_subprocess_exec(
                "docker",
                "run",
                "--rm",
                f"--memory={MEM}",
                f"--cpus={CPU}",
                "--network=none",
                "--read-only",
                "--tmpfs",
                "/tmp:64m",
                tag,
                stdout=-1,
                stderr=-1,
            )
            try:
                so, se = await asyncio.wait_for(rp.communicate(), TIMEOUT)
            except TimeoutError:
                rp.kill()
                return ResultadoSandbox(False, False, 0, 0, ["TIMEOUT"], "", "", TIMEOUT * 1000, 0, "timeout")
            t1 = asyncio.get_event_loop().time()
            ms = (t1 - t0) * 1000
            s2 = so.decode(errors="ignore").strip()
            s3 = se.decode(errors="ignore").strip()
            dt = {}
            for l in s2.splitlines():
                try:
                    dt = json.loads(l)
                    break
                except Exception as e:
                    log.warning("Docker error: %s", e)
            ok = rp.returncode == 0 and dt.get("fallos", 1) == 0 and dt.get("error") is None
            return ResultadoSandbox(
                ok,
                dt.get("ejecuto", False),
                dt.get("pasados", 0),
                dt.get("fallidos", 0),
                dt.get("fallos_nombres", []),
                s2[:3000],
                s3[:1000],
                round(ms, 1),
                0,
                dt.get("error"),
            )
        finally:
            subprocess.run(["docker", "rmi", "-f", tag], capture_output=True, check=False)  # noqa: ASYNC221

    @staticmethod
    def _df(c, n):
        return textwrap.dedent(f"""FROM {IMG}
RUN pip install -q pydantic httpx pytest pytest-asyncio
WORKDIR /ura
COPY skills/ /ura/skills/
COPY tests/ /ura/tests/
COPY rv.py /ura/rv.py
CMD ["python","-u","rv.py"]""")

    @staticmethod
    def _rv(n):
        return textwrap.dedent(f"""import sys,json,subprocess,importlib.util
r={{"ejecuto":False,"pasados":0,"fallidos":0,"fallos_nombres":[],"error":None}}
try:
sp=importlib.util.spec_from_file_location("{n}","/ura/skills/{n}.py")
m=importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)
r["ejecuto"]=True
except Exception as e: r["error"]=str(e); print(json.dumps(r)); sys.exit(1)
try:
    sr=subprocess.run(["python","-m","pytest","/ura/tests/","-v","--tb=short"],capture_output=True,text=True,timeout=15, check=False)
    for l in (sr.stdout or "").splitlines():
        if "passed" in l and "failed" in l:
            p=l.strip().split()
            for i,pi in enumerate(p):
                if pi=="passed": r["pasados"]=int(p[i-1]) if i else 0
elif pi=="failed": r["fallidos"]=int(p[i-1]) if i else 0
break
        if "FAILED" in l: r["fallos_nombres"].append(l.strip())
except Exception as e: r["error"]=str(e)
print(json.dumps(r))
sys.exit(0 if r["fallidos"]==0 else 1)
""")

    @staticmethod
    def _docker():
        try:
            return subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=False).returncode == 0
        except:  # noqa: E722
            return False
