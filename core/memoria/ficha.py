from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class Idea:
    idea: str
    tema: str
    etiquetas: list[str] = field(default_factory=list)
    tipo: str = "dato"  # herramienta | tendencia | tecnica | dato
    herramienta: str = ""
    coste: str = ""  # gratis | pago | freemium
    fuente: str = ""
    fecha_captura: str = ""
    fecha_fuente: str = ""
    hash_origen: str = ""  # BLAKE3 del archivo fuente
    version: int = 1
    vigente: bool = True

    def __post_init__(self):
        if not self.fecha_captura:
            self.fecha_captura = datetime.now(timezone.utc).isoformat()

    def texto_para_embedding(self) -> str:
        extras = " ".join(self.etiquetas) if self.etiquetas else ""
        return f"{self.idea} {self.tema} {extras}".strip()

    def to_payload(self) -> dict[str, Any]:
        d = asdict(self)
        d["etiquetas"] = self.etiquetas
        return d

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Idea":
        return cls(**{k: v for k, v in payload.items() if k in cls.__dataclass_fields__})

    @property
    def dimensiones(self) -> int:
        return 768  # nomic-embed-text
