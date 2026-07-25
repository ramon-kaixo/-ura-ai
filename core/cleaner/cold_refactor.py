"""cold_refactor.py — Capa 3: Deuda tecnica y tuneladora."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from mochila_engine import BASE_DIR

logger = logging.getLogger(__name__)
SD = BASE_DIR / "TOOLS" / "skills"
DQ = BASE_DIR / "05_RETROALIMENTACION" / "debt_queue.json"
DH = BASE_DIR / "05_RETROALIMENTACION" / "debt_history.jsonl"
RD = BASE_DIR / "05_RETROALIMENTACION" / "refactor_prompts"


@dataclass
class E:
    debt_id: str
    skill_nombre: str
    skill_path: str
    codigo_con_parche: str
    advertencias_originales: list[str]
    timestamp_creacion: str
    n_intentos: int = 0
    ultimo_intento: str | None = None
    resuelto: bool = False
    resolucion: str | None = None


class ColdRefactor:
<<<<<<< Updated upstream
    def __init__(self) -> None:
=======
    def __init__(s):
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
        DQ.parent.mkdir(parents=True, exist_ok=True)
        RD.mkdir(parents=True, exist_ok=True)
        SD.mkdir(parents=True, exist_ok=True)

<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    def registrar_deuda(self, did, nom, cod, adv):
        mc = f"# DEBT_ID: {did}\n" + cod
        sp = SD / f"{nom}.py"
        sp.write_text(mc, encoding="utf-8")
        self._a(E(did, nom, str(sp), mc, adv, self._n()))
        return sp

    def registrar_limpio(self, nom, cod):
=======
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
    def registrar_deuda(s, did, nom, cod, adv):
        mc = f"# DEBT_ID: {did}\n" + cod
        sp = SD / f"{nom}.py"
        sp.write_text(mc, encoding="utf-8")
        s._a(E(did, nom, str(sp), mc, adv, s._n()))
        return sp

    def registrar_limpio(s, nom, cod):
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
        sp = SD / f"{nom}.py"
        sp.write_text(cod, encoding="utf-8")
        return sp

<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    def _a(self, e) -> None:
        c = [x for x in self._l() if x["debt_id"] != e.debt_id]
        c.append(asdict(e))
        DQ.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")

    def _l(self):
=======
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
    def _a(s, e):
        c = [x for x in s._l() if x["debt_id"] != e.debt_id]
        c.append(asdict(e))
        DQ.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")

    def _l(s):
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
        if not DQ.exists():
            return []
        try:
            return json.loads(DQ.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load debt queue from %s", DQ)
            return []

<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    def estado_deuda(self):
        c = self._l()
        p = [e for e in c if not e.get("resuelto")]
        return {"total": len(c), "pend": len(p), "res": len(c) - len(p), "skills": [e["skill_nombre"] for e in p]}

    async def ejecutar_tuneladora(self):
        from core.guardians.ast_sentinel import ASTSentinel
        from core.sandbox.docker_orchestrator import DockerOrchestrator

        c = self._l()
=======
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
    def estado_deuda(s):
        c = s._l()
        p = [e for e in c if not e.get("resuelto")]
        return {"total": len(c), "pend": len(p), "res": len(c) - len(p), "skills": [e["skill_nombre"] for e in p]}

    async def ejecutar_tuneladora(s):
        from core.guardians.ast_sentinel import ASTSentinel
        from core.sandbox.docker_orchestrator import DockerOrchestrator

        c = s._l()
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
        p = [E(**e) for e in c if not e.get("resuelto") and e.get("n_intentos", 0) < 3]
        r = {"procesados": 0, "resueltos": 0, "reintentados": 0, "abandonados": 0}
        for e in p:
            r["procesados"] += 1
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
            li = await self._ref(e)
            if not li:
                e.n_intentos += 1
                e.ultimo_intento = self._n()
                self._a(e)
=======
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
            li = await s._ref(e)
            if not li:
                e.n_intentos += 1
                e.ultimo_intento = s._n()
                s._a(e)
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes
                r["reintentados"] += 1
                continue
            v = ASTSentinel().analizar(li, e.skill_nombre)
            if not v.ok:
                e.n_intentos += 1
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
                e.ultimo_intento = self._n()
                self._a(e)
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
                r["reintentados"] += 1
                continue
            sb = await DockerOrchestrator().validar(li, e.skill_nombre)
            if not sb.ok:
                e.n_intentos += 1
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
                e.ultimo_intento = self._n()
                self._a(e)
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
=======
                e.ultimo_intento = s._n()
                s._a(e)
>>>>>>> Stashed changes
                r["reintentados"] += 1
                continue
            Path(e.skill_path).write_text(li, encoding="utf-8")
            e.resuelto = True
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
            e.resolucion = self._n()
            self._a(e)
=======
            e.resolucion = s._n()
            s._a(e)
>>>>>>> Stashed changes
=======
            e.resolucion = s._n()
            s._a(e)
>>>>>>> Stashed changes
=======
            e.resolucion = s._n()
            s._a(e)
>>>>>>> Stashed changes
=======
            e.resolucion = s._n()
            s._a(e)
>>>>>>> Stashed changes
=======
            e.resolucion = s._n()
            s._a(e)
>>>>>>> Stashed changes
            r["resueltos"] += 1
        for e in c:
            if not e.get("resuelto") and e.get("n_intentos", 0) >= 3:
                r["abandonados"] += 1
        return r

<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    async def _ref(self, e):
=======
    async def _ref(s, e):
>>>>>>> Stashed changes
=======
    async def _ref(s, e):
>>>>>>> Stashed changes
=======
    async def _ref(s, e):
>>>>>>> Stashed changes
=======
    async def _ref(s, e):
>>>>>>> Stashed changes
=======
    async def _ref(s, e):
>>>>>>> Stashed changes
        try:
            import httpx

            async with httpx.AsyncClient(timeout=120) as cl:
                resp = await cl.post(
                    "http://127.0.0.1:4096/skill/refactor",
                    json={
                        "debt_id": e.debt_id,
                        "skill": e.skill_nombre,
                        "codigo": e.codigo_con_parche,
                        "advertencias": e.advertencias_originales,
                    },
                )
                if resp.status_code != 200:
                    return None
                return resp.json().get("codigo_limpio")
        except Exception as ex:
            logger.warning(f"Refactor: {ex}")
            return None

<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    def _n(self):
=======
    def _n(s):
>>>>>>> Stashed changes
=======
    def _n(s):
>>>>>>> Stashed changes
=======
    def _n(s):
>>>>>>> Stashed changes
=======
    def _n(s):
>>>>>>> Stashed changes
=======
    def _n(s):
>>>>>>> Stashed changes
        return datetime.now(tz=UTC).isoformat()
