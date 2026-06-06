"""Coordinator de Ingesta — Orquestador de data_scraper + data_analyzer.

Corrutina del ura-supervisor.
Ejecuta la recolección de datos externos y su procesamiento analítico.
"""
import logging
log = logging.getLogger("ingest.coordinator")

async def collect_and_process() -> None:
    """Ejecuta scraper + analyzer en secuencia."""
    from core.modules.ingest.data_scraper import collect_snapshot as _scrape
    from core.modules.ingest.data_analyzer import process_raw_files as _analyze
    try:
        await _scrape()
        log.debug("ingest: scrape OK → analyze...")
        await _analyze()
        log.debug("ingest: analyze OK")
    except Exception as e:
        log.warning("ingest: error en ciclo: %s", e)

def get_ingest_status() -> dict:
    """Retorna métricas de ingesta."""
    from core.modules.ingest.data_analyzer import get_analytics_summary
    analytics = get_analytics_summary()
    return {
        "sources": len(set(a["source"] for a in analytics)),
        "metrics": len(analytics),
        "db_path": str(Path(__file__).parent.parent.parent / "data" / "processed" / "analytics.db"),
    }

from pathlib import Path
