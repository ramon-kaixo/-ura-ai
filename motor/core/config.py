import os, json
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class UraConfig:
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    deploy_dir: str = "/home/ramon/URA/ura_ia_1972/deploy"
    data_dir: str = ""
    log_level: str = "INFO"
    is_vm: bool = True
    asus_host: str = "100.72.103.12"
    asus_port: int = 4198
    tailscale_iface: str = "tailscale0"
    timer_interval_min: int = 5
    failure_knowledge_path: str = ""
    baseline_path: str = ""
    auto_verify: bool = False
    schema_version: int = 2

    def __post_init__(self):
        base = Path(__file__).parent.parent
        if not self.data_dir:
            self.data_dir = str(base / "data")
        if not self.failure_knowledge_path:
            self.failure_knowledge_path = str(base / "data" / "failure_knowledge_inicial.json")
        if not self.baseline_path:
            self.baseline_path = str(base / "data" / "baseline_inicial.json")

    @classmethod
    def load(cls, path: str = "") -> "UraConfig":
        candidates = [p for p in [path, os.environ.get("URA_CONFIG", ""), "/etc/ura/config.json"] if p]
        c = cls()
        for p in candidates:
            if p and Path(p).exists():
                d = json.loads(Path(p).read_text())
                for k, v in d.items():
                    if hasattr(c, k):
                        setattr(c, k, v)
                break
        c.qdrant_host = os.environ.get("URA_QDRANT_HOST", c.qdrant_host)
        c.log_level = os.environ.get("URA_LOG_LEVEL", c.log_level)
        return c
