from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Idea:
    idea: str
    tema: str
    etiquetas: list[str] = field(default_factory=list)
    tipo: str = "dato"
    herramienta: str = ""
    coste: str = ""
    fuente: str = ""
    fecha_captura: str = ""
    fecha_fuente: str = ""
    hash_origen: str = ""
    version: int = 1
    vigente: bool = True
    # --- v2 ---
    datos_duros: dict = field(default_factory=dict)
    rasgos_visuales: dict = field(default_factory=dict)
    resumen_visual: str = ""
    puentes: list[str] = field(default_factory=list)
    vigilada: bool = False
    frecuencia: str = ""
    detector: str = ""

    def __post_init__(self):
        if not self.fecha_captura:
            self.fecha_captura = datetime.now(UTC).isoformat()

    def texto_para_embedding(self) -> str:
        extras = " ".join(self.etiquetas) if self.etiquetas else ""
        duros = " ".join(f"{k}: {v}" for k, v in self.datos_duros.items()) if self.datos_duros else ""
        visual = self.resumen_visual or ""
        return f"{self.idea} {self.tema} {extras} {duros} {visual}".strip()

    def to_payload(self) -> dict[str, Any]:
        d = asdict(self)
        d["etiquetas"] = self.etiquetas
        return d

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Idea":
        return cls(**{k: v for k, v in payload.items() if k in cls.__dataclass_fields__})

    @property
    def dimensiones(self) -> int:
        return 768
