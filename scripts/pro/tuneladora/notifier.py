"""Notificador de fallos del pipeline de la tuneladora.

Multi-canal (fire-and-forget, nunca bloquea el pipeline):
  1. Log destacado en data/tuneladora_reports/FAILURES.log
  2. Memoria episódica (EpisodeStore — API real: store(Episode))
  3. Terminal (rojo, solo si es TTY)
  4. Systemd journal (systemd-cat, si disponible)

Uso:
    from scripts.pro.tuneladora.notifier import notificar_fallo
    notificar_fallo(reporte_dict)

NOTA (decisión anti-duplicado): este módulo NO se registra en plugin_registry
a pesar de tener entry point CLI. El runner lo invoca directamente en _finish;
registrarlo como plugin haría que la fase "post" del registry lo ejecutara
una segunda vez (notificación duplicada).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("tuneladora.notifier")

REPORT_DIR = Path("data/tuneladora_reports")
FAILURE_LOG = Path("data/tuneladora_reports/FAILURES.log")


def notificar_fallo(reporte: dict, report_dir: Path | None = None) -> bool:
    """Notifica un fallo del pipeline por todos los canales disponibles.

    Retorna True si se ejecutó al menos un canal (sin contar terminal).
    """
    msg = _construir_mensaje(reporte)
    notificado = False

    try:
        _notificar_log(msg, report_dir)
        notificado = True
    except OSError as exc:
        logger.warning("canal log falló: %s", exc)

    try:
        _notificar_memoria(msg, reporte)
        notificado = True
    except Exception as exc:
        logger.warning("canal memoria falló: %s", exc)

    _notificar_terminal(msg)

    try:
        _notificar_systemd(msg)
    except Exception as exc:
        logger.warning("canal systemd falló: %s", exc)

    return notificado


def _construir_mensaje(reporte: dict) -> str:
    verdict = reporte.get("verdict", "UNKNOWN")
    summary = reporte.get("summary", "Sin resumen")
    files = reporte.get("files", [])
    timestamp = reporte.get("timestamp", "N/A")

    return (
        f"[FAIL] Tuneladora pipeline FAILED\n"
        f"Timestamp: {timestamp}\n"
        f"Verdict: {verdict}\n"
        f"Archivos: {len(files)}\n"
        f"Resumen: {summary}"
    )


def _notificar_log(msg: str, report_dir: Path | None = None) -> None:
    log_path = report_dir / "FAILURES.log" if report_dir else FAILURE_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now(UTC).isoformat()} | {msg}\n")


def _notificar_memoria(msg: str, reporte: dict) -> None:
    from motor.intelligence.memory.episodic import Episode, EpisodeStore

    store = EpisodeStore()
    store.store(
        Episode(
            session_id="tuneladora",
            source="pipeline",
            payload=msg,
            tags=["pipeline_fallo", "tuneladora"],
            metadata={
                "verdict": reporte.get("verdict"),
                "mode": reporte.get("mode"),
            },
        )
    )


def _notificar_terminal(msg: str, stream=None) -> None:
    import sys

    stream = stream or sys.stderr
    if stream.isatty():
        print(f"\033[91m{msg}\033[0m", file=stream)


def _notificar_systemd(msg: str) -> None:
    import subprocess

    try:
        subprocess.run(
            ["systemd-cat", "-t", "tuneladora", "-p", "err"],
            input=msg.encode(),
            check=False,
            timeout=10,
        )
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.debug("systemd-cat no disponible: %s", exc)


def _main() -> None:
    """CLI: notifica el último reporte FAIL si existe."""
    import sys

    if not REPORT_DIR.exists():
        print("No hay reportes", file=sys.stderr)
        raise SystemExit(1)
    files = sorted(REPORT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print("No hay reportes", file=sys.stderr)
        raise SystemExit(1)
    reporte = json.loads(files[0].read_text(encoding="utf-8"))
    if reporte.get("verdict") != "FAIL":
        print(f"Último verdict: {reporte.get('verdict')} — sin fallo que notificar")
        raise SystemExit(0)
    notificar_fallo(reporte)
    raise SystemExit(0)


if __name__ == "__main__":
    _main()
