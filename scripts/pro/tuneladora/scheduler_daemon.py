"""Scheduler daemon — punto de entrada systemd para TuneladoraScheduler."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading

from scripts.pro.tuneladora.plugins.dashboard import DashboardPlugin
from scripts.pro.tuneladora.scheduler import TuneladoraScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("ura.tuneladora.daemon")

scheduler: TuneladoraScheduler | None = None
_dashboard_thread: threading.Thread | None = None


def _shutdown(sig: int, frame: object) -> None:
    log.info("Senal %s recibida, deteniendo scheduler...", signal.Signals(sig).name)
    if scheduler:
        scheduler.stop()
    sys.exit(0)


async def main() -> None:
    global scheduler, _dashboard_thread  # noqa: PLW0603
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    scheduler = TuneladoraScheduler()
    scheduler.add_pipeline("health", interval_minutes=5, auto_execute_safe=True)
    scheduler.add_pipeline("cleanup", interval_minutes=60, auto_execute_safe=True)
    scheduler.add_pipeline("audit", interval_minutes=360, auto_execute_safe=False)
    scheduler.start()
    log.info("Tuneladora daemon iniciado con %d pipelines", scheduler.pipeline_count)

    # Dashboard en segundo plano
    try:
        dashboard = DashboardPlugin(None, port=9092)
        _dashboard_thread = threading.Thread(target=dashboard.start, daemon=True)
        _dashboard_thread.start()
        log.info("Dashboard iniciado en :9092")
    except Exception as e:
        log.warning("Dashboard no disponible: %s", e)

    try:
        while True:  # noqa: ASYNC110
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        _shutdown(signal.SIGTERM, None)


if __name__ == "__main__":
    asyncio.run(main())
