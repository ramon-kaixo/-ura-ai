"""mochila_engine.py — v4.3."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
MOCHILAS_DIR = BASE_DIR / "04_METADATOS"
RETROALIMENTACION_DIR = BASE_DIR / "05_RETROALIMENTACION"
TOOLS_DIR = BASE_DIR / "TOOLS"


class FaseID(StrEnum):
    F1_ROUTER = "F1_ROUTER"
    F2_CRAWLER = "F2_CRAWLER"
    F3_REFINERIA = "F3_REFINERIA"
    ISCANNER = "ISCANNER"
    F4_ESTETICA = "F4_ESTETICA"
    F5_INDEX = "F5_INDEX"
    F6_FEEDBACK = "F6_FEEDBACK"


class EstadoMochila(StrEnum):
    NUEVA = "NUEVA"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADA = "COMPLETADA"
    FALLIDA = "FALLIDA"
    DESCARTADA = "DESCARTADA"
    HIJA = "HIJA"


class TipoPipeline(StrEnum):
    IMAGEN = "IMAGEN"
    TEXTO = "TEXTO"
    SVG = "SVG"
    PDF = "PDF"
    HTML = "HTML"
    MIXTO = "MIXTO"


class CB:
    __slots__ = ("d", "dt", "er", "f", "ok", "tf", "ti")

    def __init__(self, f: Callable[..., Any]) -> None:
        self.f = f
        self.ti = _now()
        self.tf: str | None = None
        self.d: float | None = None
        self.ok = False
        self.er = None
        self.dt: dict[str, Any] = {}

    def fin(self, ok: bool = True, er: Any = None) -> None:
        self.tf = _now()
        if self.tf is None or self.ti is None:
            return
        self.d = (datetime.fromisoformat(self.tf) - datetime.fromisoformat(self.ti)).total_seconds() * 1000
        self.ok = ok
        self.er = er

    def ad(self) -> dict[str, Any]:
        return {"f": str(self.f), "ti": self.ti, "tf": self.tf, "d": self.d, "ok": self.ok, "er": self.er, **self.dt}


class MochilaEngine:
    def __init__(self, e: dict[str, Any]) -> None:
        self._e = e
        self._p: Path | None = None

    @classmethod
    def nueva(
        cls, url: str, tipo: Any = TipoPipeline.IMAGEN, pid: str | None = None, nc: str = "sin_nombre"
    ) -> MochilaEngine:
        i = str(uuid.uuid4())
        e: dict[str, Any] = {
            "v": "4.3",
            "id": i,
            "p": pid,
            "st": str(EstadoMochila.HIJA if pid else EstadoMochila.NUEVA),
            "tp": str(tipo),
            "url": url,
            "nc": nc,
            "tc": _now(),
            "tm": _now(),
            "fc": [],
            "fp": list(FaseID),
            "cc": {},
            "he": [],
            "hi": [],
            "r": {},
            "h": {},
            "c": {},
            "co": {},
            "es": {},
            "in": {},
            "fb": {},
        }
        m = cls(e)
        m._p = cls._rd(nc, i)
        return m

    @classmethod
    def cargar(cls, p: Path) -> MochilaEngine:
        return cls(json.loads(p.read_text()))

    @property
    def id(self) -> str:
        return str(self._e["id"])

    @property
    def url(self) -> str:
        return str(self._e["url"])

    @property
    def tipo(self) -> Any:
        return TipoPipeline(self._e["tp"])

    @property
    def hashes(self) -> dict[str, Any]:
        return dict(self._e["h"])

    @property
    def calidad(self) -> dict[str, Any]:
        return dict(self._e["c"])

    @property
    def red(self) -> dict[str, Any]:
        return dict(self._e["r"])

    def fc(self, f: Any) -> bool:
        return str(f) in self._e["fc"]

    def fase(self, f: Any, z: bool = False) -> _FC:
        return _FC(self, f)

    def _rc(self, c: CB) -> None:
        k = str(c.f)
        self._e["cc"][k] = c.ad()
        if c.ok and k not in self._e["fc"]:
            self._e["fc"].append(k)
        self._tm()

    def reg_r(self, **k: Any) -> None:
        self._e["r"].update(k)
        self._tm()

    def reg_h(self, **k: Any) -> None:
        self._e["h"].update(k)
        self._tm()

    def reg_c(self, **k: Any) -> None:
        self._e["c"].update(k)
        self._tm()

    def reg_co(self, **k: Any) -> None:
        self._e["co"].update(k)
        self._tm()

    def reg_e(self, **k: Any) -> None:
        self._e["es"].update(k)
        self._tm()

    def reg_i(self, **k: Any) -> None:
        self._e["in"].update(k)
        self._tm()

    def reg_f(self, **k: Any) -> None:
        self._e["fb"].update(k)
        self._tm()

    def mc(self) -> None:
        self._e["st"] = str(EstadoMochila.COMPLETADA)
        self._tm()

    def guardar(self, p: Path | None = None) -> Path:
        d = p or self._p
        if d is None:
            msg = "no path"
            raise ValueError(msg)
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(json.dumps(self._e, ensure_ascii=False, indent=2))
        return d

    def ad(self) -> dict[str, Any]:
        return dict(self._e)

    def cks(self) -> str:
        return hashlib.sha256(json.dumps(self._e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _tm(self) -> None:
        self._e["tm"] = _now()

    @staticmethod
    def _rd(nc: str, mid: str) -> Path:
        return MOCHILAS_DIR / f"{datetime.now(tz=UTC).strftime('%Y-%m-%d')}_{nc}" / f"mochila_{mid[:8]}.json"

    def __repr__(self) -> str:
        return f"Mochila(id={self.id[:8]}...,tipo={self.tipo})"


class _FC:
    def __init__(self, m: MochilaEngine, f: Any) -> None:
        self._m = m
        self._f = f
        self._c: CB | None = None

    async def __aenter__(self) -> CB:
        self._c = CB(self._f)
        return self._c

    async def __aexit__(self, t: object, v: object, b: object) -> bool:
        assert self._c is not None
        if t:
            self._c.fin(False, str(v))
            self._m._rc(self._c)
            return True
        self._c.fin(True)
        self._m._rc(self._c)
        return False


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()
