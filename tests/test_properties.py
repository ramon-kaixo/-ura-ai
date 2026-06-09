"""Property-based tests using hypothesis for URA core modules."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
from hypothesis import given, assume, strategies as st, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, precondition, invariant

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memoria_fallos import MemoriaFallos, MAX_FALLOS, UMBRAL_PATRON
from memoria_movimiento import MemoriaMovimiento, TIEMPO_MAX
from mochila_engine import MochilaEngine, TipoPipeline, EstadoMochila, FaseID

# ── helpers ──────────────────────────────────────────────────────────

_tipos = st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_")
_urls = st.sampled_from([
    "https://ejemplo.com/img.jpg",
    "http://foo.bar/path/to/page.html",
    "https://sub.domain.org/a/b/c?q=1&r=2",
])

# ═══════════════════════════════════════════════════════════════════
# memoria_fallos — property-based tests
# ═══════════════════════════════════════════════════════════════════

@given(st.lists(st.tuples(_tipos, st.text(max_size=50)), min_size=0, max_size=30))
def test_fifo_bound(registros):
    m = MemoriaFallos("test", max_fallos=5)
    for t, msg in registros:
        m.registrar(t, msg)
    assert len(m.fallos_recientes()) <= 5
    assert m.resumen()["n_fallos"] == len(m.fallos_recientes())


@given(st.lists(st.tuples(_tipos, st.text(max_size=50)), min_size=0, max_size=30))
def test_contar_matches_fallos_recientes(registros):
    m = MemoriaFallos("test", max_fallos=10)
    for t, msg in registros:
        m.registrar(t, msg)
    for f in m.fallos_recientes():
        assert m.contar(f.tipo) == sum(
            1 for x in m.fallos_recientes() if x.tipo == f.tipo
        )


@given(st.lists(st.tuples(_tipos, st.text(max_size=50)), min_size=3, max_size=20))
def test_pattern_threshold(registros):
    m = MemoriaFallos("test", max_fallos=20, umbral_patron=3)
    for t, msg in registros:
        m.registrar(t, msg)
    for t in set(t for t, _ in registros):
        assert m.es_patron(t) == (m.contar(t) >= 3)


@given(st.lists(st.tuples(_tipos, st.text(max_size=50)), min_size=0, max_size=15))
def test_hay_patron_activo(registros):
    m = MemoriaFallos("test", umbral_patron=3)
    for t, msg in registros:
        m.registrar(t, msg)
    patron = m.hay_patron_activo()
    if patron is not None:
        assert m.es_patron(patron)
    else:
        assert all(not m.es_patron(t) for t in set(t for t, _ in registros))


@given(st.lists(st.tuples(_tipos, st.text(max_size=50), st.one_of(st.none(), st.text(min_size=1, max_size=50))), min_size=0, max_size=10))
def test_arreglo_persistence(registros):
    m = MemoriaFallos("test", max_fallos=2)
    arreglos = {}
    for t, msg, a in registros:
        m.registrar(t, msg, arreglo=a)
        if a is not None:
            arreglos[t] = a
    for t, expected in arreglos.items():
        assert m.arreglo_conocido(t) == expected


@given(st.lists(st.tuples(_tipos, st.text(max_size=50)), min_size=0, max_size=10))
def test_resumen_schema(registros):
    m = MemoriaFallos("pieza_test")
    for t, msg in registros:
        m.registrar(t, msg)
    r = m.resumen()
    assert r["pieza"] == "pieza_test"
    assert r["n_fallos"] == len(m.fallos_recientes())
    assert isinstance(r["tipos"], dict)
    assert isinstance(r["arreglos"], list)


def test_empty_state():
    m = MemoriaFallos("test")
    assert m.fallos_recientes() == []
    assert m.hay_patron_activo() is None
    assert m.resumen()["n_fallos"] == 0


@given(st.lists(_tipos, min_size=6, max_size=15))
def test_fifo_eviction(tipos_lista):
    m = MemoriaFallos("test", max_fallos=5)
    for i, t in enumerate(tipos_lista):
        m.registrar(t, str(i))
    assert len(m.fallos_recientes()) == min(len(tipos_lista), 5)
    recientes = [f.tipo for f in m.fallos_recientes()]
    assert len(set(recientes)) <= 5


# Stateful test: sequence of operations
class MemoriaFallosStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.m = MemoriaFallos("stateful", max_fallos=5, umbral_patron=3)
        self._total_ops = 0

    @rule(t=_tipos, msg=st.text(max_size=20))
    def registrar(self, t: str, msg: str) -> None:
        self.m.registrar(t, msg)
        self._total_ops += 1

    @invariant()
    def fifo_bound(self) -> None:
        assert len(self.m.fallos_recientes()) <= 5

    @invariant()
    def resumen_matches(self) -> None:
        assert self.m.resumen()["n_fallos"] == len(self.m.fallos_recientes())

    @invariant()
    def patron_implies_es_patron(self) -> None:
        p = self.m.hay_patron_activo()
        if p is not None:
            assert self.m.es_patron(p)

    @rule(t=_tipos)
    def check_contar(self, t: str) -> None:
        real = sum(1 for f in self.m.fallos_recientes() if f.tipo == t)
        assert self.m.contar(t) == real


TestMemoriaFallosStateful = MemoriaFallosStateMachine.TestCase


# ═══════════════════════════════════════════════════════════════════
# memoria_movimiento — property-based tests
# ═══════════════════════════════════════════════════════════════════

class RelojFalso:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def avanzar(self, s): self.t += s


@given(id_cubo=st.text(min_size=1, max_size=10), nodo=st.text(min_size=1, max_size=10))
def test_send_return_cleanup(id_cubo, nodo):
    m = MemoriaMovimiento("test")
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo(id_cubo, nodo)
    assert m.cubo_volvio(id_cubo) is True
    assert m.circulo_sano() is True


@given(id_cubo=st.text(min_size=1, max_size=10))
def test_double_volvio(id_cubo):
    m = MemoriaMovimiento("test")
    m.mandar_cubo(id_cubo, "nodo")
    assert m.cubo_volvio(id_cubo) is True
    assert m.cubo_volvio(id_cubo) is False


@given(id_cubo=st.text(min_size=1, max_size=10), nodo=st.text(min_size=1, max_size=10))
def test_volvio_unknown(id_cubo, nodo):
    m = MemoriaMovimiento("test")
    m.mandar_cubo(id_cubo, nodo)
    assert m.cubo_volvio("__nope__" + id_cubo) is False


@given(
    id_cubos=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=6, unique=True),
    nodos=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=6),
)
def test_circulo_sano_equivalence(id_cubos, nodos):
    assume(len(id_cubos) == len(nodos))
    m = MemoriaMovimiento("test")
    r = RelojFalso(); m._reloj = r
    for idc, nd in zip(id_cubos, nodos):
        m.mandar_cubo(idc, nd)
    r.avanzar(TIEMPO_MAX + 1)
    assert m.circulo_sano() == (len(m.cubos_sin_volver()) == 0)
    assert sorted(m.nodos_atascados()) == sorted(
        c.nodo_destino for c in m.cubos_sin_volver()
    )


@given(id_cubo=st.text(min_size=1, max_size=10), nodo=st.text(min_size=1, max_size=10))
def test_resumen_schema_movimiento(id_cubo, nodo):
    m = MemoriaMovimiento("test")
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo(id_cubo, nodo)
    res = m.resumen()
    assert res["nodo"] == "test"
    assert res["en_viaje"] >= 1
    assert "atascados" in res
    assert "nodos" in res


def test_fresh_cubos_not_stale():
    m = MemoriaMovimiento("test", tiempo_max_s=30)
    r = RelojFalso(); m._reloj = r
    m.mandar_cubo("c1", "n1")
    m.mandar_cubo("c2", "n2")
    r.avanzar(10)
    assert m.circulo_sano() is True
    assert m.cubos_sin_volver() == []


class MemoriaMovimientoStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.m = MemoriaMovimiento("stateful")
        self.r = RelojFalso()
        self.m._reloj = self.r
        self._sent: set[str] = set()

    @rule(id_cubo=st.text(min_size=1, max_size=10), nodo=st.text(min_size=1, max_size=10))
    def send(self, id_cubo: str, nodo: str) -> None:
        self.m.mandar_cubo(id_cubo, nodo)
        self._sent.add(id_cubo)

    @rule(id_cubo=st.text(min_size=1, max_size=10))
    def return_cube(self, id_cubo: str) -> None:
        self.m.cubo_volvio(id_cubo)

    @rule(s=st.integers(min_value=0, max_value=100))
    def advance_time(self, s: int) -> None:
        self.r.avanzar(s)

    @invariant()
    def resumen_consistent(self) -> None:
        r = self.m.resumen()
        assert isinstance(r["en_viaje"], int)
        assert isinstance(r["atascados"], list)
        assert r["nodo"] == "stateful"


TestMemoriaMovimientoStateful = MemoriaMovimientoStateMachine.TestCase


# ═══════════════════════════════════════════════════════════════════
# mochila_engine — property-based tests
# ═══════════════════════════════════════════════════════════════════

@given(url=_urls)
def test_uuid_uniqueness(url):
    m1 = MochilaEngine.nueva(url, TipoPipeline.IMAGEN)
    m2 = MochilaEngine.nueva(url, TipoPipeline.IMAGEN)
    assert m1.id != m2.id


@given(url=_urls)
def test_cks_determinism(url):
    m = MochilaEngine.nueva(url, TipoPipeline.TEXTO)
    assert m.cks() == m.cks()


@given(url=_urls)
def test_json_roundtrip(url):
    import tempfile, os
    d = tempfile.mkdtemp()
    try:
        p = Path(d) / "m.json"
        m = MochilaEngine.nueva(url, TipoPipeline.HTML)
        m.guardar(p)
        m2 = MochilaEngine.cargar(p)
        assert m2.id == m.id
        assert m2.url == url
        assert m2.tipo == TipoPipeline.HTML
    finally:
        import shutil; shutil.rmtree(d, ignore_errors=True)


@given(url=_urls)
def test_ad_contains_id(url):
    m = MochilaEngine.nueva(url, TipoPipeline.MIXTO)
    d = m.ad()
    assert "id" in d
    assert d["id"] == m.id
    assert "st" in d


def test_faseid_completeness():
    m = MochilaEngine.nueva("https://x.com/f", TipoPipeline.IMAGEN)
    for fase in FaseID:
        assert str(fase) in m._e["fp"]


@given(url=_urls)
def test_initial_state_is_nueva(url):
    m = MochilaEngine.nueva(url, TipoPipeline.SVG)
    assert m._e["st"] == str(EstadoMochila.NUEVA)


@given(url=_urls)
def test_initial_state_is_hija_when_pid(url):
    m = MochilaEngine.nueva(url, TipoPipeline.PDF, pid="parent-123")
    assert m._e["st"] == str(EstadoMochila.HIJA)
