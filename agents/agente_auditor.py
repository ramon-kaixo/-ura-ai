#!/usr/bin/env python3
"""
AGENTE AUDITOR - Supervisa automatizaciones y detecta desviaciones.

Segun MODELO_GERENCIA.md:
- Supervisa que las automatizaciones sigan funcionando como se aprobaron
- Verifica que produzcan el mismo resultado que cuando se validaron
- Detecta desviaciones de calidad o comportamiento
- Si detecta divergencia -> alerta a Ramon via Pushover
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCRIBE_LOG = Path.home() / ".ura" / "scribe_log.json"
AUDITOR_LOG = Path.home() / ".ura" / "auditor_log.jsonl"
AUDITORIA_INTERVAL = 600


class AgenteAuditor:
    """Supervisa automatizaciones y detecta desviaciones de calidad."""

    _instance: Optional["AgenteAuditor"] = None

    def __new__(cls) -> "AgenteAuditor":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.baseline: dict[str, Any] = {}
        self.ultima_auditoria: str = ""
        self.activo = False
        self._thread: threading.Thread | None = None

    def iniciar(self, intervalo: int = AUDITORIA_INTERVAL) -> None:
        if self.activo:
            return
        self.activo = True
        self._thread = threading.Thread(
            target=self._ciclo, args=(intervalo,), daemon=True, name="agente_auditor"
        )
        self._thread.start()
        logger.info(f"Auditor iniciado (intervalo={intervalo}s)")

    def detener(self) -> None:
        self.activo = False
        if self._thread:
            self._thread.join(timeout=10)

    def _ciclo(self, intervalo: int) -> None:
        while self.activo:
            try:
                self.auditar()
            except Exception as e:
                logger.error(f"Error en ciclo de auditoria: {e}")
            time.sleep(intervalo)

    def auditar(self) -> dict[str, Any]:
        """Ejecuta auditoria completa del ecosistema."""
        ahora = datetime.now()
        eventos = self._cargar_eventos()

        resultado = {
            "timestamp": ahora.isoformat(),
            "total_eventos": len(eventos),
            "errores_detectados": 0,
            "desviaciones": [],
            "patrones_sospechosos": [],
            "metricas": {},
        }

        desviaciones = self._detectar_desviaciones(eventos)
        resultado["desviaciones"] = desviaciones

        patrones = self._detectar_patrones_sospechosos(eventos)
        resultado["patrones_sospechosos"] = patrones

        metricas = self._calcular_metricas(eventos, ahora)
        resultado["metricas"] = metricas

        self._registrar_auditoria(resultado)

        if desviaciones or patrones:
            self._alertar(desviaciones, patrones, metricas)

        self.ultima_auditoria = ahora.isoformat()
        return resultado

    def _cargar_eventos(self) -> list[dict]:
        if not SCRIBE_LOG.exists():
            return []
        try:
            return json.loads(SCRIBE_LOG.read_text())
        except Exception:
            return []

    def _detectar_desviaciones(self, eventos: list[dict]) -> list[dict]:
        """Detecta desviaciones del comportamiento esperado."""
        desviaciones = []

        if not self.baseline and eventos:
            self._establecer_baseline(eventos)
            return desviaciones

        ahora = datetime.now()
        ventana = ahora - timedelta(hours=1)

        eventos_recientes = []
        for e in eventos:
            ts = self._parse_ts(e.get("timestamp", ""))
            if ts and ts > ventana:
                eventos_recientes.append(e)

        errores_recientes = len(
            [e for e in eventos_recientes if e.get("type") in ("error", "failure", "warning")]
        )

        if self.baseline.get("errores_por_hora", 0) > 0:
            tasa_esperada = self.baseline["errores_por_hora"]
            if errores_recientes > tasa_esperada * 2:
                desviaciones.append(
                    {
                        "tipo": "tasa_errores_elevada",
                        "esperado": tasa_esperada,
                        "real": errores_recientes,
                        "factor": round(errores_recientes / max(tasa_esperada, 1), 1),
                    }
                )

        tipos_recientes = [e.get("type") for e in eventos_recientes if e.get("type")]
        tipos_unicos = set(tipos_recientes)
        tipos_esperados = set(self.baseline.get("tipos_evento", []))

        if tipos_esperados:
            tipos_nuevos = tipos_unicos - tipos_esperados
            if tipos_nuevos:
                desviaciones.append(
                    {
                        "tipo": "nuevos_tipos_evento",
                        "tipos_nuevos": list(tipos_nuevos),
                    }
                )

        modulos_recientes = [e.get("module") for e in eventos_recientes if e.get("module")]
        for modulo in set(modulos_recientes):
            cuenta = modulos_recientes.count(modulo)
            esperada = self.baseline.get("modulos", {}).get(modulo, {}).get("eventos_por_hora", 0)
            if esperada > 0 and cuenta > esperada * 3:
                desviaciones.append(
                    {
                        "tipo": "modulo_anomalo",
                        "modulo": modulo,
                        "esperado": esperada,
                        "real": cuenta,
                    }
                )

        return desviaciones

    def _establecer_baseline(self, eventos: list[dict]) -> None:
        """Establece la linea base de comportamiento normal."""
        if not eventos:
            return

        total = len(eventos)
        errores = len([e for e in eventos if e.get("type") in ("error", "failure", "warning")])

        timestamps = [self._parse_ts(e.get("timestamp", "")) for e in eventos]
        timestamps_validos = [t for t in timestamps if t]
        if timestamps_validos:
            rango_horas = max(
                1, (max(timestamps_validos) - min(timestamps_validos)).total_seconds() / 3600
            )
        else:
            rango_horas = 1
        errores_por_hora = round(errores / rango_horas, 1)

        tipos = list({e.get("type") for e in eventos if e.get("type")})

        modulos: dict[str, dict] = {}
        for e in eventos:
            mod = e.get("module", "unknown")
            if mod not in modulos:
                modulos[mod] = {"eventos": 0}
            modulos[mod]["eventos"] += 1
        for mod in modulos:
            modulos[mod]["eventos_por_hora"] = round(modulos[mod]["eventos"] / rango_horas, 1)

        self.baseline = {
            "establecida": datetime.now().isoformat(),
            "total_eventos": total,
            "errores": errores,
            "errores_por_hora": errores_por_hora,
            "tipos_evento": tipos,
            "modulos": modulos,
            "rango_horas": round(rango_horas, 1),
        }

        logger.info(f"Baseline establecida: {total} eventos, {errores} errores, {rango_horas:.1f}h")

    def _detectar_patrones_sospechosos(self, eventos: list[dict]) -> list[dict]:
        """Detecta patrones sospechosos en los eventos."""
        patrones = []

        ahora = datetime.now()
        ventana_error = ahora - timedelta(minutes=5)

        errores_recientes = [
            e
            for e in eventos
            if e.get("type") in ("error", "failure")
            and self._parse_ts(e.get("timestamp", ""))
            and self._parse_ts(e.get("timestamp", "")) > ventana_error
        ]

        if len(errores_recientes) >= 3:
            modulos_afectados = list({e.get("module", "?") for e in errores_recientes})
            patrones.append(
                {
                    "tipo": "rafaga_errores",
                    "cantidad": len(errores_recientes),
                    "ventana_minutos": 5,
                    "modulos": modulos_afectados,
                }
            )

        modulos_start = {}
        modulos_success = {}
        for e in eventos:
            mod = e.get("module", "")
            if e.get("action") == "process_request":
                modulos_start[mod] = modulos_start.get(mod, 0) + 1
            elif e.get("type") == "task_success":
                modulos_success[mod] = modulos_success.get(mod, 0) + 1

        for mod, starts in modulos_start.items():
            success = modulos_success.get(mod, 0)
            if starts >= 5 and success == 0:
                patrones.append(
                    {
                        "tipo": "tareas_sin_exito",
                        "modulo": mod,
                        "iniciadas": starts,
                        "completadas": success,
                    }
                )

        return patrones

    def _calcular_metricas(self, eventos: list[dict], ahora: datetime) -> dict:
        """Calcula metricas de salud del ecosistema."""
        hoy = ahora.strftime("%Y-%m-%d")
        eventos_hoy = (
            [e for e in eventos if e.get("timestamp", "").startswith(hoy)] if eventos else []
        )

        exitos = len([e for e in eventos_hoy if e.get("type") == "task_success"])
        errores = len([e for e in eventos_hoy if e.get("type") in ("error", "failure")])

        return {
            "eventos_hoy": len(eventos_hoy),
            "exitos": exitos,
            "errores": errores,
            "tasa_exito": round(exitos / max(len(eventos_hoy), 1) * 100, 1),
        }

    def _alertar(
        self,
        desviaciones: list[dict],
        patrones: list[dict],
        metricas: dict,
    ) -> None:
        """Alerta a Ramon via Pushover."""
        import urllib.request

        token = __import__("os").environ.get("PUSHOVER_APP_TOKEN", "")
        user = __import__("os").environ.get("PUSHOVER_USER_KEY", "")
        if not (token and user):
            return

        partes = ["URA Auditor alerta:"]
        if desviaciones:
            for d in desviaciones[:3]:
                partes.append(
                    f"- {d['tipo']}: esperado={d.get('esperado', '?')} real={d.get('real', '?')}"
                )
        if patrones:
            for p in patrones[:2]:
                partes.append(
                    f"- {p['tipo']}: {p.get('cantidad', '?')} en {p.get('ventana_minutos', '?')}min"
                )

        msg = "\n".join(partes)

        try:
            data = urllib.parse.urlencode(
                {
                    "token": token,
                    "user": user,
                    "title": "URA Auditor",
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

    def _registrar_auditoria(self, resultado: dict) -> None:
        """Registra la auditoria en forensic_scribe y archivo local."""
        try:
            from core.forensic_scribe import get_forensic_scribe

            scribe = get_forensic_scribe()
            scribe.log_event(
                event_type="auditoria",
                module="agente_auditor",
                action="auditar",
                context={
                    "desviaciones": len(resultado["desviaciones"]),
                    "patrones": len(resultado["patrones_sospechosos"]),
                    "metricas": resultado.get("metricas", {}),
                },
                dependencies=["forensic_scribe"],
            )
        except Exception:
            pass

        AUDITOR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDITOR_LOG, "a") as f:
            f.write(json.dumps(resultado, ensure_ascii=False) + "\n")

    @staticmethod
    def _parse_ts(ts_str: str) -> datetime | None:
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def estado(self) -> dict:
        return {
            "activo": self.activo,
            "baseline": self.baseline.get("establecida", "no establecida"),
            "ultima_auditoria": self.ultima_auditoria,
        }


_instancia: AgenteAuditor | None = None


def get_agente_auditor() -> AgenteAuditor:
    global _instancia
    if _instancia is None:
        _instancia = AgenteAuditor()
    return _instancia


if __name__ == "__main__":
    auditor = get_agente_auditor()
    resultado = auditor.auditar()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
