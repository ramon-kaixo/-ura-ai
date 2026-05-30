"""Registrador de cambios atado al gestor de propuestas.

Reglas:
- Un cambio **solo** se registra si existe una propuesta aprobada o ejecutada
  asociada (identificada por ``id_propuesta``).
- Antes de escribir el nuevo contenido, el archivo anterior se mueve a la
  papelera mediante :class:`SecureTrash`.
- Cada entrada del log incluye: timestamp, ID de propuesta, tipo de cambio,
  ruta del archivo, hash antes/después, y ruta de la versión en papelera.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
from pathlib import Path

from core.change_proposal_manager import ChangeProposalManager, get_change_proposal_manager
from core.secure_trash import SecureTrash, get_secure_trash

logger = logging.getLogger(__name__)

LOG_PATH = Path(__file__).resolve().parent / "data" / "change_log.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


class ChangeLogger:
    """Registra cambios de ficheros solo si están amparados por una propuesta."""

    def __init__(
        self,
        log_path: Path | None = None,
        proposal_manager: ChangeProposalManager | None = None,
        trash: SecureTrash | None = None,
    ) -> None:
        self.log_path = Path(log_path) if log_path else LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.manager = (
            proposal_manager if proposal_manager is not None else get_change_proposal_manager()
        )
        self.trash = trash if trash is not None else get_secure_trash()

    # ------------------------------------------------------------
    # Core
    # ------------------------------------------------------------
    # Tipos triviales no requieren propuesta completa (solo registro).
    TIPOS_TRIVIALES = {"comentario", "logging", "typo", "format", "docstring"}

    def registrar_cambio(
        self,
        archivo: str | Path,
        id_propuesta: str,
        tipo: str,
        contenido_nuevo: bytes | str | None = None,
        *,
        motivo: str = "",
        trivial: bool = False,
    ) -> dict:
        """Registra un cambio si la propuesta está aprobada/ejecutada.

        Si se pasa ``contenido_nuevo``, el archivo antiguo (si existe) se mueve
        a la papelera y se escribe el nuevo contenido. Si no se pasa, solo se
        registra el cambio (para casos donde la escritura la hizo otro
        componente).

        Excepción cláusula 6 (REGLAS DE ORO): si ``trivial=True`` o el ``tipo``
        está en ``TIPOS_TRIVIALES``, no se exige propuesta. La entrada queda
        marcada con ``id_propuesta="trivial"`` en el log para auditoría.
        """
        es_trivial = bool(trivial) or tipo in self.TIPOS_TRIVIALES
        if es_trivial and not id_propuesta:
            id_propuesta = "trivial"
            propuesta = None
            titulo_propuesta = f"trivial:{tipo}"
        else:
            propuesta = self._verificar_propuesta(id_propuesta)
            titulo_propuesta = propuesta.titulo

        archivo_path = Path(archivo)
        if not archivo_path.is_absolute():
            archivo_path = Path(__file__).resolve().parents[1] / archivo_path

        hash_antes = ""
        papelera_path = ""
        if archivo_path.exists() and archivo_path.is_file():
            hash_antes = _sha256_file(archivo_path)
            if contenido_nuevo is not None:
                dest = self.trash.mover_a_papelera(archivo_path, motivo=f"propuesta:{id_propuesta}")
                papelera_path = str(dest)

        if contenido_nuevo is not None:
            archivo_path.parent.mkdir(parents=True, exist_ok=True)
            mode = "wb" if isinstance(contenido_nuevo, (bytes, bytearray)) else "w"
            if mode == "wb":
                with open(archivo_path, "wb") as f:
                    f.write(contenido_nuevo)  # type: ignore[arg-type]
            else:
                with open(archivo_path, "w", encoding="utf-8") as f:
                    f.write(contenido_nuevo)  # type: ignore[arg-type]

        hash_despues = _sha256_file(archivo_path) if archivo_path.exists() else ""

        entry = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "id_propuesta": id_propuesta,
            "titulo_propuesta": titulo_propuesta,
            "trivial": es_trivial,
            "tipo": tipo,
            "archivo": str(archivo_path),
            "hash_antes": hash_antes,
            "hash_despues": hash_despues,
            "papelera": papelera_path,
            "motivo": motivo,
        }
        self._append(entry)
        logger.info(f"Cambio registrado: {archivo_path} (propuesta={id_propuesta})")
        return entry

    def registrar_borrado(self, archivo: str | Path, id_propuesta: str, motivo: str = "") -> dict:
        """Marca un archivo como eliminado: lo mueve a papelera y registra."""
        propuesta = self._verificar_propuesta(id_propuesta)
        archivo_path = Path(archivo)
        if not archivo_path.is_absolute():
            archivo_path = Path(__file__).resolve().parents[1] / archivo_path
        if not archivo_path.exists():
            raise FileNotFoundError(archivo_path)
        hash_antes = _sha256_file(archivo_path)
        dest = self.trash.mover_a_papelera(
            archivo_path, motivo=f"propuesta:{id_propuesta}:{motivo}"
        )
        entry = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "id_propuesta": id_propuesta,
            "titulo_propuesta": propuesta.titulo,
            "tipo": "delete",
            "archivo": str(archivo_path),
            "hash_antes": hash_antes,
            "hash_despues": "",
            "papelera": str(dest),
            "motivo": motivo,
        }
        self._append(entry)
        logger.info(f"Borrado registrado: {archivo_path} → {dest}")
        return entry

    def ultimos(self, n: int = 20) -> list[dict]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    def desde(self, momento: _dt.datetime) -> list[dict]:
        if not self.log_path.exists():
            return []
        out: list[dict] = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    ts = _dt.datetime.fromisoformat(e["timestamp"])
                    if ts >= momento:
                        out.append(e)
                except Exception:
                    continue
        return out

    # ------------------------------------------------------------
    # Privados
    # ------------------------------------------------------------
    def _verificar_propuesta(self, id_propuesta: str):
        if not id_propuesta:
            raise PermissionError("Cambio rechazado: falta id_propuesta.")
        try:
            p = self.manager._leer(id_propuesta)  # noqa: SLF001 (acceso controlado)
        except FileNotFoundError:
            raise PermissionError(f"Cambio rechazado: propuesta inexistente ({id_propuesta}).")
        if p.estado not in {"aprobada", "ejecutada"}:
            raise PermissionError(
                f"Cambio rechazado: propuesta {id_propuesta} en estado '{p.estado}'. "
                "Debe estar 'aprobada' o 'ejecutada'."
            )
        return p

    def _append(self, entry: dict) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# Singleton ----------------------------------------------------------------
_logger_instance: ChangeLogger | None = None


def get_change_logger() -> ChangeLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ChangeLogger()
    return _logger_instance


if __name__ == "__main__":  # pragma: no cover
    cl = ChangeLogger()
    print(f"Log en: {cl.log_path}")
    for e in cl.ultimos(5):
        print(f"  {e['timestamp']} [{e['tipo']}] {e['archivo']} prop={e['id_propuesta']}")
