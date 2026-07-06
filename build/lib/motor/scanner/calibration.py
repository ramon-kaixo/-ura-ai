import json
import logging
import statistics
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("ura.scanner.calib")


class Calibration:
    """Gestión de baseline y detección de anomalías por calibración."""

    def __init__(self, config):
        self.config = config
        self.baseline_path = (
            Path(config.baseline_path) if config.baseline_path else Path(config.data_dir) / "baseline_inicial.json"
        )
        self._baseline = self._cargar()

    def _cargar(self) -> dict:
        """Carga baseline desde disco."""
        try:
            if self.baseline_path.exists():
                return json.loads(self.baseline_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning("error cargando baseline: %s", e)
        return {}

    @property
    def hay_baseline(self) -> bool:
        """Indica si existe un baseline cargado."""
        return bool(self._baseline)

    def detectar_anomalias(self, estado) -> list:
        """Detecta anomalías comparando estado actual vs baseline."""
        if not self._baseline:
            return []
        anomalias = []
        bl = self._baseline
        for metric, limite in [("ram_pct", "ram_pct_max"), ("disk_pct", "disk_pct_max"), ("load_1m", "load_max")]:
            actual = estado.recursos.get(metric, 0) if isinstance(estado.recursos, dict) else 0
            if isinstance(actual, (int, float)) and actual > bl.get(limite, 999):
                anomalias.append(f"Calib.{metric}={actual} > limite={bl.get(limite, 999)}")
        return anomalias

    def learn(self, estado, trends: list = None) -> dict:
        """Entrena baseline a partir de un scan y tendencias históricas."""
        bl = {k: v for k, v in estado.recursos.items() if isinstance(v, (int, float))}
        if trends and len(trends) >= 3:
            for metrica, factor in [("ram_pct", 1.3), ("disk_pct", 1.2), ("load_1m", 2.0)]:
                vals = [t.get(metrica, 0) for t in trends if isinstance(t.get(metrica), (int, float))]
                if len(vals) >= 3:
                    media = statistics.mean(vals)
                    desv = statistics.stdev(vals) if len(vals) > 1 else media * 0.1
                    bl[f"{metrica}_max"] = round(media + max(desv * 3, media * 0.2), 1)
        else:
            bl["ram_pct_max"] = estado.recursos.get("ram_pct", 0) * 1.2
            bl["disk_pct_max"] = estado.recursos.get("disk_pct", 0) * 1.2
            bl["load_max"] = estado.recursos.get("load_1m", 0) * 1.5
        bl["generated"] = datetime.now(UTC).isoformat() + "Z"
        bl["puntos_trend"] = len(trends) if trends else 0
        self._baseline = bl
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self.baseline_path.write_text(json.dumps(bl, indent=2))
        log.info("baseline actualizada (%d puntos de tendencia)", bl["puntos_trend"])
        return bl

    def detect(self, trends: list) -> dict:
        """Detecta anomalías vs tendencia histórica usando z-score."""
        if not trends:
            return {"anomalias": [], "ok": True}
        anomalias = []
        for metrica, nombre, warn_factor, crit_factor in [
            ("ram_pct", "RAM", 1.5, 2.0),
            ("disk_pct", "Disco", 1.3, 1.8),
            ("load_1m", "Load", 2.0, 3.0),
        ]:
            vals = [t.get(metrica, 0) for t in trends if isinstance(t.get(metrica), (int, float))]
            if len(vals) < 3:
                continue
            actual = vals[-1]
            media = statistics.mean(vals[:-1]) if len(vals) > 1 else vals[0]
            desv = statistics.stdev(vals[:-1]) if len(vals) > 3 else media * 0.1
            if desv == 0:
                desv = media * 0.1
            if actual > media + desv * crit_factor:
                anomalias.append(
                    {
                        "metrica": metrica,
                        "nombre": nombre,
                        "actual": actual,
                        "media": round(media, 1),
                        "desv": round(desv, 1),
                        "nivel": "critico",
                        "z_score": round((actual - media) / desv, 1),
                    },
                )
            elif actual > media + desv * warn_factor:
                anomalias.append(
                    {
                        "metrica": metrica,
                        "nombre": nombre,
                        "actual": actual,
                        "media": round(media, 1),
                        "desv": round(desv, 1),
                        "nivel": "warning",
                        "z_score": round((actual - media) / desv, 1),
                    },
                )
        return {
            "anomalias": anomalias,
            "ok": len(anomalias) == 0,
            "total_puntos": len(trends),
            "ultimo": trends[-1] if trends else None,
        }
