import json, logging, statistics
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("ura.scanner.calib")

class Calibration:
    def __init__(self, config):
        self.config = config
        self.baseline_path = Path(config.baseline_path) if config.baseline_path else Path(config.data_dir) / "baseline_inicial.json"
        self._baseline = self._cargar()

    def _cargar(self) -> dict:
        try:
            if self.baseline_path.exists():
                return json.loads(self.baseline_path.read_text())
        except: pass
        return {}

    @property
    def hay_baseline(self) -> bool:
        return bool(self._baseline)

    def detectar_anomalias(self, estado) -> list:
        if not self._baseline:
            return []
        anomalias = []
        bl = self._baseline
        for metric, limite in [("ram_pct", "ram_pct_max"), ("disk_pct", "disk_pct_max"),
                                ("load_1m", "load_max")]:
            actual = getattr(estado.recursos, metric, 0) if hasattr(estado.recursos, metric) else 0
            if isinstance(actual, dict): actual = 0
            if isinstance(actual, (int, float)) and actual > bl.get(limite, 999):
                anomalias.append(f"Calib.{metric}={actual} > limite={bl.get(limite, 999)}")
        return anomalias

    def learn(self, estado) -> dict:
        bl = {k: v for k, v in estado.recursos.items() if isinstance(v, (int, float))}
        bl["ram_pct_max"] = estado.recursos.get("ram_pct", 0) * 1.2
        bl["disk_pct_max"] = estado.recursos.get("disk_pct", 0) * 1.2
        bl["load_max"] = estado.recursos.get("load_1m", 0) * 1.5
        bl["generated"] = datetime.utcnow().isoformat() + "Z"
        self._baseline = bl
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        self.baseline_path.write_text(json.dumps(bl, indent=2))
        log.info("baseline generada en %s", self.baseline_path)
        return bl
