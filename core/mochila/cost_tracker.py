import json
import os
import time
from datetime import date
from pathlib import Path

TARIFAS: dict[str, float] = {
    "ollama": 0.0,
    "openrouter": 0.0,
    "gemini": 0.0,
}


def _cost_file() -> Path:
    return Path(os.environ.get("MOCHILA_COST_FILE", str(Path.home() / ".nervioso" / "cost_tracker.jsonl")))


class CostTracker:
    def __init__(self, tarifas: dict[str, float] | None = None, cost_file: Path | None = None):
        self.tarifas = tarifas or TARIFAS
        self._cost_file = cost_file or _cost_file()
        self._cost_file.parent.mkdir(parents=True, exist_ok=True)

    def registrar(self, provider: str, modelo: str, prompt_tokens: int, completion_tokens: int) -> dict:
        entrada = {
            "timestamp": time.time(),
            "date": date.today().isoformat(),
            "provider": provider,
            "modelo": modelo,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_estimate": self._calcular_coste(provider, prompt_tokens, completion_tokens),
        }
        with open(self._cost_file, "a") as f:
            f.write(json.dumps(entrada) + "\n")
        return entrada

    def _calcular_coste(self, provider: str, prompt_tokens: int, completion_tokens: int) -> float:
        tarifa = self.tarifas.get(provider, 0.0)
        return (prompt_tokens + completion_tokens) * tarifa

    def resumen_hoy(self) -> dict:
        hoy = date.today().isoformat()
        total_cost = 0.0
        total_tokens = 0
        por_provider: dict[str, int] = {}
        if not self._cost_file.exists():
            return {"date": hoy, "total_cost": 0.0, "total_tokens": 0, "por_provider": {}}
        with open(self._cost_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("date") == hoy:
                    total_cost += entry.get("cost_estimate", 0.0)
                    total_tokens += entry.get("total_tokens", 0)
                    p = entry.get("provider", "unknown")
                    por_provider[p] = por_provider.get(p, 0) + 1
        return {
            "date": hoy,
            "total_cost": round(total_cost, 6),
            "total_tokens": total_tokens,
            "por_provider": por_provider,
        }
