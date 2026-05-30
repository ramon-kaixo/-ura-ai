"""Gestor de propuestas de cambio con validación automática.

Ningún cambio del sistema puede aplicarse sin:
1. Una propuesta registrada como archivo Markdown en ``core/data/proposals/``.
2. Una validación automática que compruebe integridad/coherencia.
3. Una ejecución que primero mueve los archivos afectados a la papelera
   mediante :class:`SecureTrash` antes de aplicar nada.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Iterable

from core.secure_trash import SecureTrash, get_secure_trash

logger = logging.getLogger(__name__)

PROPOSALS_DIR = Path(__file__).resolve().parent / "data" / "proposals"
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

ESTADOS_VALIDOS = {"pendiente", "aprobada", "rechazada", "ejecutada"}
TIPOS_VALIDOS = {"feature", "bugfix", "refactor", "delete", "rename", "docs", "config"}


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------
@dataclass
class Propuesta:
    id: str
    titulo: str
    descripcion: str
    archivos_afectados: list[str]
    tipo: str
    autor: str
    fecha_creacion: str
    estado: str = "pendiente"
    motivo_rechazo: str = ""
    fecha_validacion: str = ""
    fecha_ejecucion: str = ""
    ejecutor_cambios: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# Propuesta de cambio: {self.titulo}",
            "",
            f"- **ID**: `{self.id}`",
            f"- **Fecha**: {self.fecha_creacion}",
            f"- **Autor**: {self.autor}",
            f"- **Tipo**: {self.tipo}",
            f"- **Estado**: {self.estado}",
        ]
        if self.fecha_validacion:
            lines.append(f"- **Validada**: {self.fecha_validacion}")
        if self.fecha_ejecucion:
            lines.append(f"- **Ejecutada**: {self.fecha_ejecucion}")
        if self.motivo_rechazo:
            lines.append(f"- **Motivo rechazo**: {self.motivo_rechazo}")
        lines.extend(
            [
                "",
                "## Descripción",
                "",
                self.descripcion.strip() or "_(sin descripción)_",
                "",
                "## Archivos afectados",
                "",
            ]
        )
        if self.archivos_afectados:
            lines.extend(f"- `{a}`" for a in self.archivos_afectados)
        else:
            lines.append("- _(ninguno)_")
        lines.append("")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Persistencia (frontmatter JSON embebido al final del .md)
# --------------------------------------------------------------------------
_META_RE = re.compile(r"<!--META\n(.*?)\n-->", re.DOTALL)


def _render_file(p: Propuesta) -> str:
    meta = json.dumps(asdict(p), ensure_ascii=False, indent=2)
    return p.to_markdown() + "\n<!--META\n" + meta + "\n-->\n"


def _parse_file(path: Path) -> Propuesta:
    text = path.read_text(encoding="utf-8")
    m = _META_RE.search(text)
    if not m:
        raise ValueError(f"Propuesta sin metadatos válidos: {path}")
    data = json.loads(m.group(1))
    return Propuesta(**data)


# --------------------------------------------------------------------------
# Gestor
# --------------------------------------------------------------------------
class ChangeProposalManager:
    """Gestor único de propuestas. Delegación a SecureTrash en ejecución."""

    def __init__(
        self,
        proposals_dir: Path | None = None,
        trash: SecureTrash | None = None,
        autor_por_defecto: str = "ura",
    ) -> None:
        self.proposals_dir = Path(proposals_dir) if proposals_dir else PROPOSALS_DIR
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.trash = trash if trash is not None else get_secure_trash()
        self.autor_por_defecto = autor_por_defecto
        # Registro de ejecutores externos (callables) por id de propuesta
        self._ejecutores: dict[str, Callable[[Propuesta], list[dict]]] = {}

    # ------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------
    def crear_propuesta(
        self,
        titulo: str,
        descripcion: str,
        archivos_afectados: Iterable[str],
        tipo: str,
        autor: str | None = None,
    ) -> Propuesta:
        if tipo not in TIPOS_VALIDOS:
            raise ValueError(f"Tipo inválido '{tipo}'. Válidos: {sorted(TIPOS_VALIDOS)}")
        archivos = [str(a) for a in archivos_afectados]
        now = _dt.datetime.now()
        pid = self._generar_id(titulo, now)
        propuesta = Propuesta(
            id=pid,
            titulo=titulo.strip(),
            descripcion=descripcion.strip(),
            archivos_afectados=archivos,
            tipo=tipo,
            autor=(autor or self.autor_por_defecto),
            fecha_creacion=now.isoformat(timespec="seconds"),
            estado="pendiente",
        )
        self._escribir(propuesta)
        logger.info(f"Propuesta creada: {pid} - {titulo}")
        return propuesta

    def validar_propuesta(self, id_propuesta: str) -> Propuesta:
        """Validador automático: revisa integridad y coherencia documental."""
        p = self._leer(id_propuesta)
        if p.estado not in {"pendiente"}:
            raise ValueError(f"Solo se pueden validar propuestas pendientes (actual: {p.estado})")

        errores: list[str] = []
        if not p.titulo or len(p.titulo) < 5:
            errores.append("Título demasiado corto (mínimo 5 caracteres).")
        if not p.descripcion or len(p.descripcion) < 20:
            errores.append("Descripción insuficiente (mínimo 20 caracteres).")
        if p.tipo not in TIPOS_VALIDOS:
            errores.append(f"Tipo inválido: {p.tipo}.")
        if p.tipo != "docs" and not p.archivos_afectados:
            errores.append("La propuesta no lista archivos afectados.")

        # Los archivos deben existir (salvo que sea un 'feature' que los crea).
        # Aceptamos rutas que aún no existan si la descripción menciona 'crear' o 'nuevo'.
        tolera_inexistentes = bool(
            re.search(r"\b(crear|nuevo|nueva)\b", p.descripcion, re.IGNORECASE)
        )
        for a in p.archivos_afectados:
            ruta = Path(a)
            if not ruta.is_absolute():
                ruta = Path(__file__).resolve().parents[1] / a
            if not ruta.exists() and not tolera_inexistentes:
                errores.append(f"Archivo afectado no existe: {a}")

        p.fecha_validacion = _dt.datetime.now().isoformat(timespec="seconds")
        if errores:
            p.estado = "rechazada"
            p.motivo_rechazo = "; ".join(errores)
            logger.warning(f"Propuesta {p.id} RECHAZADA: {p.motivo_rechazo}")
        else:
            p.estado = "aprobada"
            p.motivo_rechazo = ""
            logger.info(f"Propuesta {p.id} APROBADA.")
        self._escribir(p)
        return p

    def registrar_ejecutor(self, id_propuesta: str, fn: Callable[[Propuesta], list[dict]]) -> None:
        """Registra una función que aplicará los cambios de la propuesta.

        La función recibe la propuesta y debe devolver una lista de dicts
        describiendo cada cambio aplicado (para auditoría).
        """
        self._ejecutores[id_propuesta] = fn

    def ejecutar_propuesta(
        self,
        id_propuesta: str,
        ejecutor: Callable[[Propuesta], list[dict]] | None = None,
    ) -> Propuesta:
        """Ejecuta una propuesta aprobada. Envía los archivos afectados a la
        papelera ANTES de aplicar cualquier cambio.
        """
        p = self._leer(id_propuesta)
        if p.estado != "aprobada":
            raise ValueError(f"Solo se ejecutan propuestas aprobadas (actual: {p.estado})")

        fn = ejecutor or self._ejecutores.get(id_propuesta)

        # 1. Mover a papelera todos los archivos afectados que existan.
        cambios: list[dict] = []
        for a in p.archivos_afectados:
            ruta = Path(a)
            if not ruta.is_absolute():
                ruta = Path(__file__).resolve().parents[1] / a
            if ruta.exists() and ruta.is_file():
                try:
                    dest = self.trash.mover_a_papelera(ruta, motivo=f"propuesta:{p.id}")
                    cambios.append(
                        {
                            "accion": "backup_papelera",
                            "archivo": str(ruta),
                            "papelera": str(dest),
                        }
                    )
                except Exception as e:
                    logger.error(f"No se pudo hacer backup de {ruta}: {e}")
                    cambios.append(
                        {"accion": "backup_papelera_fallido", "archivo": str(ruta), "error": str(e)}
                    )

        # 2. Ejecutar la función de cambios (si se proporciona).
        if fn is not None:
            try:
                cambios_fn = fn(p) or []
                cambios.extend(cambios_fn)
            except Exception as e:
                logger.error(f"Ejecutor lanzó excepción: {e}")
                p.motivo_rechazo = f"Fallo al ejecutar: {e}"
                p.estado = "rechazada"
                self._escribir(p)
                raise

        p.estado = "ejecutada"
        p.fecha_ejecucion = _dt.datetime.now().isoformat(timespec="seconds")
        p.ejecutor_cambios = cambios
        self._escribir(p)
        logger.info(f"Propuesta {p.id} EJECUTADA con {len(cambios)} operaciones.")
        return p

    def listar_propuestas(self, estado: str | None = None) -> list[Propuesta]:
        if estado is not None and estado not in ESTADOS_VALIDOS:
            raise ValueError(f"Estado inválido '{estado}'. Válidos: {sorted(ESTADOS_VALIDOS)}")
        out: list[Propuesta] = []
        for f in sorted(self.proposals_dir.glob("*.md")):
            try:
                p = _parse_file(f)
            except Exception as e:
                logger.warning(f"Propuesta ilegible {f}: {e}")
                continue
            if estado is None or p.estado == estado:
                out.append(p)
        return out

    # ------------------------------------------------------------
    # Privados
    # ------------------------------------------------------------
    def _generar_id(self, titulo: str, when: _dt.datetime) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", titulo.lower()).strip("-")[:40] or "propuesta"
        stamp = when.strftime("%Y%m%d_%H%M%S")
        return f"{stamp}_{slug}"

    def _path_for(self, id_propuesta: str) -> Path:
        return self.proposals_dir / f"{id_propuesta}.md"

    def _leer(self, id_propuesta: str) -> Propuesta:
        path = self._path_for(id_propuesta)
        if not path.exists():
            raise FileNotFoundError(f"Propuesta no encontrada: {id_propuesta}")
        return _parse_file(path)

    def _escribir(self, p: Propuesta) -> None:
        path = self._path_for(p.id)
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(_render_file(p), encoding="utf-8")
        tmp.replace(path)


# Singleton ----------------------------------------------------------------
_manager_instance: ChangeProposalManager | None = None


def get_change_proposal_manager() -> ChangeProposalManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ChangeProposalManager()
    return _manager_instance


if __name__ == "__main__":  # pragma: no cover
    m = ChangeProposalManager()
    print(f"Propuestas en {m.proposals_dir}:")
    for p in m.listar_propuestas():
        print(f"  [{p.estado}] {p.id} - {p.titulo}")
