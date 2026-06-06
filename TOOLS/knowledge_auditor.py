"""knowledge_auditor.py — Trazabilidad completa de cada artefacto."""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from mochila_engine import BASE_DIR, MochilaEngine

RETRO_DIR = BASE_DIR / "05_RETROALIMENTACION"
AUDIT_LOG = RETRO_DIR / "audit_log.jsonl"
PROVENANCE_DIR = RETRO_DIR / "provenance"


@dataclass
class ProvenanceEntry:
    mochila_id: str; sha256: str; url_origen: str; dominio: str
    nombre_coleccion: str; tipo_pipeline: str; timestamp_ingesta: str
    fases_completadas: list[str]; score_fiabilidad: float; score_originalidad: float
    score_sesgo: float; requiere_revision: bool; keywords_detectadas: list[str]


class KnowledgeAuditor:
    def __init__(self):
        PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

    def registrar(self, mochila: MochilaEngine) -> ProvenanceEntry:
        from urllib.parse import urlparse
        dominio = urlparse(mochila.url).netloc.lower().removeprefix("www.")
        fb = mochila.feedback
        prov = ProvenanceEntry(mochila_id=mochila.id, sha256=mochila.hashes.get("sha256", ""),
            url_origen=mochila.url, dominio=dominio, nombre_coleccion=mochila.nombre_coleccion,
            tipo_pipeline=mochila.tipo_pipeline, timestamp_ingesta=mochila.timestamp_creacion,
            fases_completadas=list(mochila.fases_completadas),
            score_fiabilidad=fb.get("score_fiabilidad", 0), score_originalidad=fb.get("score_originalidad", 0),
            score_sesgo=fb.get("score_sesgo", 0.5), requiere_revision=fb.get("requiere_revision", False),
            keywords_detectadas=fb.get("keywords_detectadas", []))
        sha8 = prov.sha256[:8] if prov.sha256 else prov.mochila_id[:8]
        with open(PROVENANCE_DIR / f"{sha8}.json", "w") as f:
            json.dump(asdict(prov), f, ensure_ascii=False, indent=2)
        with open(AUDIT_LOG, "a") as f:
            json.dump({"ts": _now_iso(), "mochila_id": prov.mochila_id, "url": prov.url_origen,
                       "dominio": prov.dominio, "score_fid": round(prov.score_fiabilidad, 4),
                       "fases": len(prov.fases_completadas), "rev": prov.requiere_revision}, f)
            f.write("\n")
        return prov

    def leer_recientes(self, n: int = 50) -> list[dict]:
        if not AUDIT_LOG.exists(): return []
        lineas = AUDIT_LOG.read_text().strip().splitlines()
        return [json.loads(l) for l in lineas[-n:]]


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).isoformat()
