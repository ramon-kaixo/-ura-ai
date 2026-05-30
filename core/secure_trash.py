"""
Módulo: core/secure_trash.py
Propósito: Papelera segura que versiona archivos antes de borrarlos para permitir restauración.
Dependencias principales: shutil, pathlib, json, datetime
Reglas especiales: Nunca borrar sin versionar. Mantener mínimo 3 versiones.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Raíces configurables vía entorno para facilitar tests
_ENV_TRASH_ROOT = os.environ.get("URA_TRASH_ROOT")
_ENV_PROJECT_ROOT = os.environ.get("URA_PROJECT_ROOT")

DEFAULT_TRASH_ROOT = (
    Path(_ENV_TRASH_ROOT) if _ENV_TRASH_ROOT else Path("/Volumes/TOSHIBA_NUEVO/URA_papelera")
)
DEFAULT_PROJECT_ROOT = (
    Path(_ENV_PROJECT_ROOT) if _ENV_PROJECT_ROOT else Path(__file__).resolve().parents[1]
)

_STATE_FILENAME = ".secure_trash_state.json"
_LOG_FILENAME = "trash_log.jsonl"
_VERSION_RE = re.compile(r"\.v(\d{3,})(\.[^.]+)?$")


class SecureTrash:
    """Papelera versionada para archivos del proyecto URA."""

    MAX_VERSIONS: int = 10

    def __init__(
        self,
        trash_root: Path | None = None,
        project_root: Path | None = None,
        max_versions: int | None = None,
    ) -> None:
        self.trash_root = Path(trash_root) if trash_root else DEFAULT_TRASH_ROOT
        self.project_root = Path(project_root) if project_root else DEFAULT_PROJECT_ROOT
        if max_versions is not None:
            self.MAX_VERSIONS = max_versions
        self._ensure_root()
        self._state_path = self.trash_root / _STATE_FILENAME
        self._log_path = self.trash_root / _LOG_FILENAME
        self._state = self._load_state()

    # ------------------------------------------------------------
    # Estado persistente
    # ------------------------------------------------------------
    def _ensure_root(self) -> None:
        self.trash_root.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        if self._state_path.exists():
            try:
                return json.loads(self._state_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Estado papelera corrupto, reinicializando: {e}")
        return {"modo_conservacion": True, "version_counter": {}}

    def _save_state(self) -> None:
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._state_path)

    # ------------------------------------------------------------
    # Modo conservación
    # ------------------------------------------------------------
    def activar_modo_conservacion(self) -> None:
        self._state["modo_conservacion"] = True
        self._save_state()
        logger.info("SecureTrash: modo conservación ACTIVADO (no se borra nada).")

    def desactivar_modo_conservacion(self) -> None:
        self._state["modo_conservacion"] = False
        self._save_state()
        logger.info("SecureTrash: modo conservación DESACTIVADO (rotación habilitada).")

    @property
    def modo_conservacion(self) -> bool:
        return bool(self._state.get("modo_conservacion", True))

    # ------------------------------------------------------------
    # Rutas
    # ------------------------------------------------------------
    def _relative_key(self, ruta_archivo: Path) -> str:
        """Devuelve la ruta relativa al project_root o absoluta si está fuera."""
        try:
            return str(Path(ruta_archivo).resolve().relative_to(self.project_root.resolve()))
        except ValueError:
            # Fuera del repo: usar hash del path absoluto para evitar colisiones
            abs_str = str(Path(ruta_archivo).resolve())
            h = hashlib.sha1(abs_str.encode(), usedforsecurity=False).hexdigest()[:8]
            return f"_external_/{h}/{Path(ruta_archivo).name}"

    def _trash_dir_for(self, ruta_archivo: Path) -> Path:
        rel = self._relative_key(Path(ruta_archivo))
        return self.trash_root / rel

    def _next_version(self, ruta_archivo: Path) -> int:
        key = self._relative_key(Path(ruta_archivo))
        counter = self._state.setdefault("version_counter", {})
        n = int(counter.get(key, 0)) + 1
        counter[key] = n
        return n

    def _versioned_name(self, original_name: str, version: int) -> str:
        """`foo.py` → `foo.v003.py`. Sin extensión: `foo.v003`."""
        p = Path(original_name)
        stem, ext = p.stem, p.suffix
        if ext:
            return f"{stem}.v{version:03d}{ext}"
        return f"{stem}.v{version:03d}"

    # ------------------------------------------------------------
    # Operaciones principales
    # ------------------------------------------------------------
    def mover_a_papelera(self, ruta_archivo: str | os.PathLike, motivo: str = "") -> Path:
        src = Path(ruta_archivo)
        if not src.exists():
            raise FileNotFoundError(f"No existe: {src}")
        if not src.is_file():
            raise ValueError(f"Solo se aceptan archivos regulares: {src}")

        version = self._next_version(src)
        dest_dir = self._trash_dir_for(src)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / self._versioned_name(src.name, version)

        shutil.move(str(src), str(dest))
        self._save_state()
        self._log(
            operacion="mover_a_papelera",
            origen=str(src),
            destino=str(dest),
            version=version,
            motivo=motivo,
        )
        logger.info(f"Archivo movido a papelera: {src} → {dest}")

        # Si no estamos en modo conservación, rotar.
        if not self.modo_conservacion:
            self.rotar_versiones(src)
        return dest

    def restaurar_de_papelera(
        self, ruta_original: str | os.PathLike, version: int | None = None
    ) -> Path:
        original = Path(ruta_original)
        dest_dir = self._trash_dir_for(original)
        if not dest_dir.exists():
            raise FileNotFoundError(f"No hay versiones en papelera para: {original}")
        versiones = self._listar_versiones_dir(dest_dir, original.name)
        if not versiones:
            raise FileNotFoundError(f"No hay versiones en papelera para: {original}")
        if version is None:
            elegido = versiones[-1]
        else:
            candidatos = [v for v in versiones if v["version"] == version]
            if not candidatos:
                raise FileNotFoundError(f"Versión {version} no encontrada para {original}")
            elegido = candidatos[0]

        src_trash = Path(elegido["path"])
        # Antes de restaurar, si el original existe, moverlo a papelera para no perderlo.
        if original.exists():
            self.mover_a_papelera(original, motivo="backup_previo_a_restaurar")
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_trash), str(original))
        self._log(
            operacion="restaurar_de_papelera",
            origen=str(src_trash),
            destino=str(original),
            version=elegido["version"],
        )
        logger.info(f"Restaurado de papelera: {src_trash} → {original}")
        return original

    def rotar_versiones(self, ruta_archivo: str | os.PathLike) -> list[Path]:
        """Elimina las versiones más antiguas que excedan MAX_VERSIONS.

        Solo actúa si modo_conservacion está DESACTIVADO. Devuelve la lista
        de archivos borrados.
        """
        if self.modo_conservacion:
            return []
        original = Path(ruta_archivo)
        dest_dir = self._trash_dir_for(original)
        if not dest_dir.exists():
            return []
        versiones = self._listar_versiones_dir(dest_dir, original.name)
        if len(versiones) <= self.MAX_VERSIONS:
            return []
        exceso = len(versiones) - self.MAX_VERSIONS
        a_borrar = versiones[:exceso]
        borrados: list[Path] = []
        for v in a_borrar:
            p = Path(v["path"])
            try:
                p.unlink()
                borrados.append(p)
                self._log(
                    operacion="rotacion_borrado",
                    origen=str(p),
                    destino="",
                    version=v["version"],
                    motivo=f"exceso_versiones (max={self.MAX_VERSIONS})",
                )
            except Exception as e:
                logger.error(f"Error borrando {p}: {e}")
        logger.info(f"Rotación: {len(borrados)} versiones antiguas eliminadas de {original}")
        return borrados

    # ------------------------------------------------------------
    # Listados
    # ------------------------------------------------------------
    def _listar_versiones_dir(self, dest_dir: Path, original_name: str) -> list[dict]:
        p = Path(original_name)
        stem, ext = p.stem, p.suffix
        pattern = f"{re.escape(stem)}\\.v(\\d{{3,}}){re.escape(ext) if ext else ''}$"
        regex = re.compile(pattern)
        out = []
        for f in dest_dir.iterdir():
            if not f.is_file():
                continue
            m = regex.match(f.name)
            if m:
                out.append(
                    {
                        "path": str(f),
                        "version": int(m.group(1)),
                        "size": f.stat().st_size,
                        "mtime": _dt.datetime.fromtimestamp(f.stat().st_mtime).isoformat(
                            timespec="seconds"
                        ),
                    }
                )
        return sorted(out, key=lambda x: x["version"])

    def listar_papelera(self) -> dict[str, list[dict]]:
        """Devuelve {ruta_relativa: [versiones...]} con todas las versiones guardadas."""
        resultado: dict[str, list[dict]] = {}
        if not self.trash_root.exists():
            return resultado
        for root, _dirs, files in os.walk(self.trash_root):
            root_path = Path(root)
            agrupado: dict[str, list[dict]] = {}
            for f in files:
                if f.startswith(".") or f == _LOG_FILENAME:
                    continue
                m = _VERSION_RE.search(f)
                if not m:
                    continue
                version = int(m.group(1))
                suffix = m.group(2) or ""
                # Reconstruir nombre original (sin .vNNN)
                nombre_original = _VERSION_RE.sub(suffix, f)
                full = root_path / f
                stat = full.stat()
                rel = root_path.relative_to(self.trash_root) / nombre_original
                agrupado.setdefault(str(rel), []).append(
                    {
                        "version": version,
                        "path": str(full),
                        "size": stat.st_size,
                        "mtime": _dt.datetime.fromtimestamp(stat.st_mtime).isoformat(
                            timespec="seconds"
                        ),
                    }
                )
            for k, v in agrupado.items():
                resultado[k] = sorted(v, key=lambda x: x["version"])
        return resultado

    # ------------------------------------------------------------
    # Log
    # ------------------------------------------------------------
    def _log(self, **entry) -> None:
        entry["timestamp"] = _dt.datetime.now().isoformat(timespec="seconds")
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"No se pudo registrar en trash_log: {e}")


# Singleton ----------------------------------------------------------------
_trash_instance: SecureTrash | None = None


def get_secure_trash() -> SecureTrash:
    """Obtener el singleton de secure trash."""
    global _trash_instance
    if _trash_instance is None:
        _trash_instance = SecureTrash()
    return _trash_instance


if __name__ == "__main__":  # pragma: no cover
    t = SecureTrash()
    print(f"trash_root = {t.trash_root}")
    print(f"modo_conservacion = {t.modo_conservacion}")
    print(f"MAX_VERSIONS = {t.MAX_VERSIONS}")
    print("Papelera actual:")
    print(json.dumps(t.listar_papelera(), ensure_ascii=False, indent=2))
