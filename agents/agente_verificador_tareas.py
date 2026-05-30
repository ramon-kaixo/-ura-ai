#!/usr/bin/env python3
"""
Agente Verificador de Tareas - Daemon PM2
Verifica cada 5 minutos que todas las tareas enviadas a central_router
se completen correctamente. Detecta tareas colgadas, timeouts repetidos,
y genera informe diario por Telegram.

Ejecucion:
    python agents/agente_verificador_tareas.py          # un solo ciclo
    python agents/agente_verificador_tareas.py --daemon  # modo continuo (PM2)

PM2 config:
    pm2 start agents/agente_verificador_tareas.py --name ura-verificador --interpreter python3 -- --daemon
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCRIBE_LOG = Path.home() / ".ura" / "scribe_log.json"
TIMEOUT_LOG = Path.home() / ".ura" / "timeouts.jsonl"
VERIFIER_PID = Path.home() / ".ura" / "verificador.pid"
SCAN_INTERVAL = 300

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

HUNG_THRESHOLD_MINUTES = 10
DAILY_REPORT_HOUR = 20


class AgenteVerificadorTareas:
    """Verifica integridad de tareas en el ecosistema URA."""

    def __init__(self) -> None:
        self.activo = False
        self._thread: threading.Thread | None = None
        self.ultimo_informe_diario: str = ""

    def iniciar(self, intervalo: int = SCAN_INTERVAL) -> None:
        if self.activo:
            logger.warning("Verificador ya esta activo")
            return
        self.activo = True
        self._thread = threading.Thread(
            target=self._ciclo, args=(intervalo,), daemon=True, name="verificador_tareas"
        )
        self._thread.start()
        self._escribir_pid()
        logger.info(f"Verificador iniciado (intervalo={intervalo}s)")

    def detener(self) -> None:
        self.activo = False
        if self._thread:
            self._thread.join(timeout=10)
        self._borrar_pid()
        logger.info("Verificador detenido")

    def _escribir_pid(self) -> None:
        VERIFIER_PID.write_text(str(os.getpid()))

    def _borrar_pid(self) -> None:
        try:
            VERIFIER_PID.unlink()
        except FileNotFoundError:
            pass

    def _ciclo(self, intervalo: int) -> None:
        while self.activo:
            try:
                self.verificar()
            except Exception as e:
                logger.error(f"Error en ciclo de verificacion: {e}")
            time.sleep(intervalo)

    def verificar(self) -> dict:
        """Ejecuta un ciclo de verificacion completo."""
        ahora = datetime.now()

        eventos = self._cargar_scribe_events()
        timeouts = self._cargar_timeout_events()

        perdidas = self._detectar_tareas_perdidas(eventos)
        colgadas = self._detectar_tareas_colgadas(eventos)
        timeout_alertas = self._analizar_timeouts(timeouts)

        resultado = {
            "timestamp": ahora.isoformat(),
            "eventos_scribe": len(eventos),
            "eventos_timeout": len(timeouts),
            "tareas_perdidas": len(perdidas),
            "tareas_colgadas": len(colgadas),
            "timeout_alertas": len(timeout_alertas),
        }

        if perdidas or colgadas:
            self._alertar_pushover(ahora, perdidas, colgadas)

        if ahora.hour == DAILY_REPORT_HOUR and self._debe_enviar_informe(ahora):
            self._enviar_informe_telegram(ahora, resultado, perdidas, colgadas, timeout_alertas)
            self.ultimo_informe_diario = ahora.strftime("%Y-%m-%d")

        logger.info(f"Verificacion: {resultado}")
        return resultado

    def _cargar_scribe_events(self) -> list[dict]:
        if not SCRIBE_LOG.exists():
            return []
        try:
            return json.loads(SCRIBE_LOG.read_text())
        except Exception:
            return []

    def _cargar_timeout_events(self) -> list[dict]:
        if not TIMEOUT_LOG.exists():
            return []
        eventos = []
        try:
            for line in TIMEOUT_LOG.read_text().strip().split("\n"):
                if line:
                    eventos.append(json.loads(line))
        except Exception:
            pass
        return eventos

    def _detectar_tareas_perdidas(self, eventos: list[dict]) -> list[dict]:
        """Tareas con task_start pero sin task_success para el mismo trace_id."""
        if not eventos:
            return []

        starts = {}
        successes = {}

        for e in eventos:
            ctx = e.get("context", {})
            tid = ctx.get("trace_id", "")
            if not tid:
                continue

            if e.get("type") == "task_start" or e.get("action") == "process_request":
                starts[tid] = e
            elif e.get("type") == "task_success":
                successes[tid] = e

        perdidas = []
        for tid, start_event in starts.items():
            if tid not in successes:
                perdidas.append(
                    {
                        "trace_id": tid,
                        "timestamp": start_event.get("timestamp", ""),
                        "agent": start_event.get("module", "unknown"),
                        "context": start_event.get("context", {}),
                    }
                )

        return perdidas

    def _detectar_tareas_colgadas(self, eventos: list[dict]) -> list[dict]:
        """Tareas iniciadas hace mas de HUNG_THRESHOLD_MINUTES sin completar."""
        ahora = datetime.now()
        colgadas = []

        tasks_in_progress = {}
        for e in reversed(eventos):
            ctx = e.get("context", {})
            tid = ctx.get("trace_id", "")
            if not tid:
                continue

            if e.get("type") == "task_start" and tid not in tasks_in_progress:
                tasks_in_progress[tid] = e
            elif e.get("type") == "task_success":
                tasks_in_progress.pop(tid, None)

        for tid, event in tasks_in_progress.items():
            ts_str = event.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                delta_min = (ahora - ts.replace(tzinfo=None)).total_seconds() / 60
                if delta_min > HUNG_THRESHOLD_MINUTES:
                    colgadas.append(
                        {
                            "trace_id": tid,
                            "started": ts_str,
                            "minutes_ago": round(delta_min),
                            "agent": event.get("module", "unknown"),
                        }
                    )
            except Exception:
                pass

        return colgadas

    def _analizar_timeouts(self, timeouts: list[dict]) -> list[dict]:
        """Timeouts repetidos (3+ veces mismo agente:función)."""
        conteo: dict[str, int] = {}
        ultimo: dict[str, dict] = {}

        for t in timeouts:
            key = f"{t.get('agent', '?')}:{t.get('function', '?')}"
            conteo[key] = conteo.get(key, 0) + 1
            ultimo[key] = t

        alertas = []
        for key, count in conteo.items():
            if count >= 3:
                alertas.append(
                    {
                        "key": key,
                        "count": count,
                        "last": ultimo[key],
                    }
                )

        return alertas

    def _alertar_pushover(
        self, ahora: datetime, perdidas: list[dict], colgadas: list[dict]
    ) -> None:
        import urllib.request

        token = os.environ.get("PUSHOVER_APP_TOKEN", "")
        user = os.environ.get("PUSHOVER_USER_KEY", "")
        if not (token and user):
            return

        partes = [f"URA Verificador @ {ahora.strftime('%H:%M')}"]
        if perdidas:
            partes.append(
                f"Perdidas: {len(perdidas)} (trace_id: {perdidas[0]['trace_id'][:12]}...)"
            )
        if colgadas:
            partes.append(
                f"Colgadas: {len(colgadas)} ({colgadas[0]['agent']} {colgadas[0]['minutes_ago']}min)"
            )

        msg = "\n".join(partes)

        try:
            data = urllib.parse.urlencode(
                {
                    "token": token,
                    "user": user,
                    "title": "URA Verificador",
                    "message": msg,
                    "priority": "1",
                }
            ).encode()
            urllib.request.urlopen(  # nosec B310
                urllib.request.Request("https://api.pushover.net/1/messages.json", data=data),
                timeout=5,
            )
        except Exception:
            pass

    def _debe_enviar_informe(self, ahora: datetime) -> bool:
        return self.ultimo_informe_diario != ahora.strftime("%Y-%m-%d")

    def _enviar_informe_telegram(
        self,
        ahora: datetime,
        resultado: dict,
        perdidas: list[dict],
        colgadas: list[dict],
        timeout_alertas: list[dict],
    ) -> None:
        if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
            return

        emoji_status = "OK" if not perdidas and not colgadas else "WARN"

        lineas = [
            f"{'✅' if emoji_status == 'OK' else '⚠️'} Informe URA - {ahora.strftime('%d/%m/%Y %H:%M')}",
            f"Total eventos scribe: {resultado['eventos_scribe']}",
            f"Timeouts registrados: {resultado['eventos_timeout']}",
            f"Tareas perdidas: {resultado['tareas_perdidas']}",
            f"Tareas colgadas: {resultado['tareas_colgadas']}",
        ]

        if perdidas:
            lineas.append("")
            lineas.append("TAREAS PERDIDAS:")
            for p in perdidas[:5]:
                lineas.append(f"  - {p['agent']} ({p['trace_id'][:12]}...)")

        if colgadas:
            lineas.append("")
            lineas.append("TAREAS COLGADAS:")
            for c in colgadas[:5]:
                lineas.append(f"  - {c['agent']}: {c['minutes_ago']}min sin respuesta")

        if timeout_alertas:
            lineas.append("")
            lineas.append("TIMEOUTS REPETIDOS:")
            for t in timeout_alertas[:5]:
                lineas.append(f"  - {t['key']}: {t['count']}x")

        texto = "\n".join(lineas)

        try:
            import urllib.request

            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = urllib.parse.urlencode(
                {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": texto,
                    "parse_mode": "HTML",
                }
            ).encode()
            urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)  # nosec B310
        except Exception as e:
            logger.error(f"No se pudo enviar informe Telegram: {e}")

    def estado(self) -> dict[str, Any]:
        return {
            "activo": self.activo,
            "pid_file": str(VERIFIER_PID),
            "intervalo": SCAN_INTERVAL,
            "ultimo_informe": self.ultimo_informe_diario,
        }


_instancia: AgenteVerificadorTareas | None = None


def get_verificador() -> AgenteVerificadorTareas:
    global _instancia
    if _instancia is None:
        _instancia = AgenteVerificadorTareas()
    return _instancia


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente Verificador de Tareas URA")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar en modo continuo")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL, help="Intervalo en segundos")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    verificador = get_verificador()

    def handle_signal(sig, frame):
        verificador.detener()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    if args.daemon:
        if VERIFIER_PID.exists():
            logger.warning("Ya hay una instancia corriendo (verificador.pid existe)")
            sys.exit(1)
        verificador.iniciar(args.interval)
        logger.info("Verificador en modo daemon. Ctrl+C para detener.")
        try:
            while verificador.activo:
                time.sleep(1)
        except KeyboardInterrupt:
            verificador.detener()
    else:
        resultado = verificador.verificar()
        print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
