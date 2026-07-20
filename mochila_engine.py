"""mochila_engine.py — v4.3."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

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

    def __init__(self, f) -> None:
        self.f = f
        self.ti = _now()
        self.tf = None
        self.d = None
        self.ok = False
        self.er = None
        self.dt = {}

    def fin(self, ok=True, er=None) -> None:
        self.tf = _now()
        self.d = (datetime.fromisoformat(self.tf) - datetime.fromisoformat(self.ti)).total_seconds() * 1000
        self.ok = ok
        self.er = er

    def ad(self):
        return {"f": str(self.f), "ti": self.ti, "tf": self.tf, "d": self.d, "ok": self.ok, "er": self.er, **self.dt}


class MochilaEngine:
    def __init__(self, e) -> None:
        self._e = e
        self._p = None

    @classmethod
    def nueva(cls, url, tipo=TipoPipeline.IMAGEN, pid=None, nc="sin_nombre"):
        i = str(uuid.uuid4())
        e = {
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
    def cargar(cls, p):
        return cls(json.loads(p.read_text()))

    @property
    def id(self):
        return self._e["id"]

    @property
    def url(self):
        return self._e["url"]

    @property
    def tipo(self):
        return TipoPipeline(self._e["tp"])

    @property
    def hashes(self):
        return self._e["h"]

    @property
    def calidad(self):
        return self._e["c"]

    @property
    def red(self):
        return self._e["r"]

    def fc(self, f):
        return str(f) in self._e["fc"]

    def fase(self, f, z=False):
        return _FC(self, f)

    def _rc(self, c) -> None:
        k = str(c.f)
        self._e["cc"][k] = c.ad()
        if c.ok and k not in self._e["fc"]:
            self._e["fc"].append(k)
        self._tm()

    def reg_r(self, **k) -> None:
        self._e["r"].update(k)
        self._tm()

    def reg_h(self, **k) -> None:
        self._e["h"].update(k)
        self._tm()

    def reg_c(self, **k) -> None:
        self._e["c"].update(k)
        self._tm()

    def reg_co(self, **k) -> None:
        self._e["co"].update(k)
        self._tm()

    def reg_e(self, **k) -> None:
        self._e["es"].update(k)
        self._tm()

    def reg_i(self, **k) -> None:
        self._e["in"].update(k)
        self._tm()

    def reg_f(self, **k) -> None:
        self._e["fb"].update(k)
        self._tm()

    def mc(self) -> None:
        self._e["st"] = str(EstadoMochila.COMPLETADA)
        self._tm()

    def guardar(self, p=None):
        d = p or self._p
        if d is None:
            msg = "no path"
            raise ValueError(msg)
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(json.dumps(self._e, ensure_ascii=False, indent=2))
        return d

    def ad(self):
        return dict(self._e)

    def cks(self):
        return hashlib.sha256(json.dumps(self._e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _tm(self) -> None:
        self._e["tm"] = _now()

    @staticmethod
    def _rd(nc, mid):
        return MOCHILAS_DIR / f"{datetime.now(tz=UTC).strftime('%Y-%m-%d')}_{nc}" / f"mochila_{mid[:8]}.json"

    def __repr__(self) -> str:
        return f"Mochila(id={self.id[:8]}...,tipo={self.tipo})"


class _FC:
    def __init__(self, m, f) -> None:
        self._m = m
        self._f = f
        self._c = None

    async def __aenter__(self):
        self._c = CB(self._f)
        return self._c

    async def __aexit__(self, t, v, b):
        if t:
            self._c.fin(False, str(v))
            self._m._rc(self._c)  # noqa: SLF001
            return True
        self._c.fin(True)
        self._m._rc(self._c)  # noqa: SLF001
        return False


def _now():
    return datetime.now(tz=UTC).isoformat()
