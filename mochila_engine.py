"""mochila_engine.py — v4.3"""

from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime, timezone
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
    __slots__ = ("f", "ti", "tf", "d", "ok", "er", "dt")

    def __init__(s, f):
        s.f = f
        s.ti = _now()
        s.tf = None
        s.d = None
        s.ok = False
        s.er = None
        s.dt = {}

    def fin(s, ok=True, er=None):
        s.tf = _now()
        s.d = (datetime.fromisoformat(s.tf) - datetime.fromisoformat(s.ti)).total_seconds() * 1000
        s.ok = ok
        s.er = er

    def ad(s):
        return {"f": str(s.f), "ti": s.ti, "tf": s.tf, "d": s.d, "ok": s.ok, "er": s.er, **s.dt}


class MochilaEngine:
    def __init__(s, e):
        s._e = e
        s._p = None

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
    def id(s):
        return s._e["id"]

    @property
    def url(s):
        return s._e["url"]

    @property
    def tipo(s):
        return TipoPipeline(s._e["tp"])

    @property
    def hashes(s):
        return s._e["h"]

    @property
    def calidad(s):
        return s._e["c"]

    @property
    def red(s):
        return s._e["r"]

    def fc(s, f):
        return str(f) in s._e["fc"]

    def fase(s, f, z=False):
        return _FC(s, f)

    def _rc(s, c):
        k = str(c.f)
        s._e["cc"][k] = c.ad()
        if c.ok and k not in s._e["fc"]:
            s._e["fc"].append(k)
        s._tm()

    def reg_r(s, **k):
        s._e["r"].update(k)
        s._tm()

    def reg_h(s, **k):
        s._e["h"].update(k)
        s._tm()

    def reg_c(s, **k):
        s._e["c"].update(k)
        s._tm()

    def reg_co(s, **k):
        s._e["co"].update(k)
        s._tm()

    def reg_e(s, **k):
        s._e["es"].update(k)
        s._tm()

    def reg_i(s, **k):
        s._e["in"].update(k)
        s._tm()

    def reg_f(s, **k):
        s._e["fb"].update(k)
        s._tm()

    def mc(s):
        s._e["st"] = str(EstadoMochila.COMPLETADA)
        s._tm()

    def guardar(s, p=None):
        d = p or s._p
        if d is None:
            raise ValueError("no path")
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(json.dumps(s._e, ensure_ascii=False, indent=2))
        return d

    def ad(s):
        return dict(s._e)

    def cks(s):
        return hashlib.sha256(json.dumps(s._e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _tm(s):
        s._e["tm"] = _now()

    @staticmethod
    def _rd(nc, mid):
        return MOCHILAS_DIR / f"{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}_{nc}" / f"mochila_{mid[:8]}.json"

    def __repr__(s):
        return f"Mochila(id={s.id[:8]}...,tipo={s.tipo})"


class _FC:
    def __init__(s, m, f):
        s._m = m
        s._f = f
        s._c = None

    async def __aenter__(s):
        s._c = CB(s._f)
        return s._c

    async def __aexit__(s, t, v, b):
        if t:
            s._c.fin(False, str(v))
            s._m._rc(s._c)
            return True
        s._c.fin(True)
        s._m._rc(s._c)
        return False


def _now():
    return datetime.now(tz=timezone.utc).isoformat()
