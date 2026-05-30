"""Auditor de coherencia del repositorio.

Comprueba:
- Que los archivos Python parseen correctamente (AST).
- Que no haya archivos marcados para borrado que aún existan.
- Que cada cambio reciente del ``ChangeLogger`` tenga propuesta válida.
- Que compara cada archivo vivo con la última versión de la papelera para
  detectar regresiones recientes (archivo más pequeño, pérdida de símbolos
  Python, etc.).
- Toma en cuenta las **propuestas pendientes** para evitar reportar como
  inconsistencia algo que ya está documentado y pendiente de ejecución.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from core.agente_documentador import AgenteDocumentador, get_agente_documentador
from core.change_logger import ChangeLogger, get_change_logger
from core.change_proposal_manager import ChangeProposalManager, get_change_proposal_manager
from core.secure_trash import SecureTrash, get_secure_trash

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Hallazgo:
    severidad: str  # "info" | "warning" | "error"
    categoria: str
    archivo: str
    mensaje: str
    datos: dict = field(default_factory=dict)


class CoherenceAuditor:
    """Auditor que cruza código fuente, propuestas y papelera."""

    def __init__(
        self,
        project_root: Path | None = None,
        proposal_manager: ChangeProposalManager | None = None,
        change_logger: ChangeLogger | None = None,
        trash: SecureTrash | None = None,
        documentador: AgenteDocumentador | None = None,
    ) -> None:
        self.project_root = Path(project_root) if project_root else PROJECT_ROOT
        self.manager = (
            proposal_manager if proposal_manager is not None else get_change_proposal_manager()
        )
        self.logger = change_logger if change_logger is not None else get_change_logger()
        self.trash = trash if trash is not None else get_secure_trash()
        self.documentador = documentador if documentador is not None else get_agente_documentador()

    # ------------------------------------------------------------
    # Auditoría completa
    # ------------------------------------------------------------
    def auditar(self) -> dict:
        hallazgos: list[Hallazgo] = []
        resumen_papelera = self._resumen_papelera()
        archivos_pendientes = self._archivos_en_propuestas_pendientes()

        # 1. Sintaxis Python
        hallazgos.extend(self._auditar_sintaxis_python(archivos_pendientes))

        # 2. Cambios recientes sin propuesta
        hallazgos.extend(self._auditar_log_propuestas())

        # 3. Regresiones detectables por comparación con papelera
        hallazgos.extend(self._auditar_regresiones(resumen_papelera))

        # 4. Cruce con catálogo URA (AgenteDocumentador)
        catalogo_info, catalogo_hallazgos = self._auditar_con_catalogo()
        hallazgos.extend(catalogo_hallazgos)

        informe = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "project_root": str(self.project_root),
            "modo_conservacion": self.trash.modo_conservacion,
            "totales": {
                "hallazgos": len(hallazgos),
                "errores": sum(1 for h in hallazgos if h.severidad == "error"),
                "warnings": sum(1 for h in hallazgos if h.severidad == "warning"),
                "infos": sum(1 for h in hallazgos if h.severidad == "info"),
            },
            "papelera": resumen_papelera,
            "catalogo": catalogo_info,
            "propuestas_pendientes": sorted(archivos_pendientes),
            "hallazgos": [h.__dict__ for h in hallazgos],
        }
        return informe

    # ------------------------------------------------------------
    # Catálogo URA
    # ------------------------------------------------------------
    def _auditar_con_catalogo(self) -> tuple[dict, list[Hallazgo]]:
        """Lee el catálogo y reporta agentes rotos, archivos faltantes y
        duplicados funcionales que no estén ya cubiertos por una propuesta.
        """
        hallazgos: list[Hallazgo] = []
        info: dict = {"disponible": False}
        try:
            catalogo = self.documentador.cargar_catalogo() or self.documentador.generar_catalogo()
        except Exception as e:
            logger.warning(f"No se pudo cargar el catálogo: {e}")
            return info, hallazgos
        if not catalogo:
            return info, hallazgos
        validacion = self.documentador.validar_coherencia()
        info = {
            "disponible": True,
            "ruta": str(self.documentador.catalog_path),
            "ultima_actualizacion": catalogo.get("ultima_actualizacion", ""),
            "total_agentes": validacion.get("total_agentes", 0),
            "total_modulos": validacion.get("total_modulos", 0),
            "problemas": len(validacion.get("problemas", [])),
            "duplicados_funcionales": len(validacion.get("duplicados_funcionales", [])),
        }

        archivos_pendientes = self._archivos_en_propuestas_pendientes()

        for prob in validacion.get("problemas", []):
            archivo = prob.get("ruta") or prob.get("ruta_esperada", "")
            # Si ya hay una propuesta tocando este archivo, no es un hallazgo activo.
            if any(archivo and archivo in p for p in archivos_pendientes):
                continue
            severidad = (
                "error" if prob["tipo"] in {"agente_roto", "archivo_inexistente"} else "warning"
            )
            hallazgos.append(
                Hallazgo(
                    severidad=severidad,
                    categoria=f"catalogo:{prob['tipo']}",
                    archivo=archivo,
                    mensaje=f"Catálogo: {prob['tipo']} en agente '{prob.get('nombre', '')}'",
                    datos=prob,
                )
            )

        for dup in validacion.get("duplicados_funcionales", []):
            hallazgos.append(
                Hallazgo(
                    severidad="warning",
                    categoria="catalogo:duplicado_funcional",
                    archivo=", ".join(dup.get("agentes", [])),
                    mensaje=f"Varios agentes comparten intención '{dup['intencion']}': {dup['agentes']}",
                    datos=dup,
                )
            )
        return info, hallazgos

    # ------------------------------------------------------------
    # Papelera
    # ------------------------------------------------------------
    def _resumen_papelera(self) -> dict:
        versiones = self.trash.listar_papelera()
        total_versiones = sum(len(v) for v in versiones.values())
        return {
            "archivos_distintos": len(versiones),
            "versiones_totales": total_versiones,
            "trash_root": str(self.trash.trash_root),
            "por_archivo": {k: len(v) for k, v in versiones.items()},
        }

    def _archivos_en_propuestas_pendientes(self) -> set[str]:
        out: set[str] = set()
        for p in self.manager.listar_propuestas(estado="pendiente"):
            for a in p.archivos_afectados:
                out.add(str(Path(a)))
        for p in self.manager.listar_propuestas(estado="aprobada"):
            for a in p.archivos_afectados:
                out.add(str(Path(a)))
        return out

    # ------------------------------------------------------------
    # Sintaxis
    # ------------------------------------------------------------
    def _auditar_sintaxis_python(self, ignorar: set[str]) -> list[Hallazgo]:
        hallazgos: list[Hallazgo] = []
        excluir_dirs = {
            ".venv",
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "mlflow",
            "output",
            "logs",
        }
        for py in self.project_root.rglob("*.py"):
            if any(part in excluir_dirs for part in py.parts):
                continue
            rel = str(py.relative_to(self.project_root))
            if rel in ignorar or str(py) in ignorar:
                continue
            try:
                ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError as e:
                hallazgos.append(
                    Hallazgo(
                        severidad="error",
                        categoria="sintaxis",
                        archivo=rel,
                        mensaje=f"SyntaxError: {e.msg} (línea {e.lineno})",
                        datos={"lineno": e.lineno, "offset": e.offset},
                    )
                )
            except Exception as e:
                hallazgos.append(
                    Hallazgo(
                        severidad="warning",
                        categoria="sintaxis",
                        archivo=rel,
                        mensaje=f"No se pudo parsear: {e}",
                    )
                )
        return hallazgos

    # ------------------------------------------------------------
    # Log de cambios ↔ propuestas
    # ------------------------------------------------------------
    def _auditar_log_propuestas(self) -> list[Hallazgo]:
        hallazgos: list[Hallazgo] = []
        recientes = self.logger.ultimos(200)
        for entry in recientes:
            pid = entry.get("id_propuesta", "")
            if not pid:
                hallazgos.append(
                    Hallazgo(
                        severidad="error",
                        categoria="log_sin_propuesta",
                        archivo=entry.get("archivo", ""),
                        mensaje="Entrada de change_log sin id_propuesta.",
                        datos=entry,
                    )
                )
                continue
            try:
                p = self.manager._leer(pid)  # noqa: SLF001
            except FileNotFoundError:
                hallazgos.append(
                    Hallazgo(
                        severidad="error",
                        categoria="propuesta_ausente",
                        archivo=entry.get("archivo", ""),
                        mensaje=f"Propuesta referenciada no existe: {pid}",
                        datos=entry,
                    )
                )
                continue
            if p.estado not in {"aprobada", "ejecutada"}:
                hallazgos.append(
                    Hallazgo(
                        severidad="warning",
                        categoria="propuesta_estado_invalido",
                        archivo=entry.get("archivo", ""),
                        mensaje=f"Cambio registrado con propuesta en estado '{p.estado}'.",
                        datos={"id_propuesta": pid},
                    )
                )
        return hallazgos

    # ------------------------------------------------------------
    # Regresiones
    # ------------------------------------------------------------
    def _auditar_regresiones(self, resumen_papelera: dict) -> list[Hallazgo]:
        """Compara cada archivo vivo con la última versión en papelera."""
        hallazgos: list[Hallazgo] = []
        versiones = self.trash.listar_papelera()
        for rel, lista in versiones.items():
            if not lista:
                continue
            ultima = lista[-1]
            # Intentar localizar el archivo vivo reconstruyendo la ruta.
            vivo = self.project_root / rel
            if not vivo.exists() or not vivo.is_file():
                continue
            size_vivo = vivo.stat().st_size
            size_trash = int(ultima.get("size", 0))
            if size_trash > 0 and size_vivo < size_trash * 0.5:
                hallazgos.append(
                    Hallazgo(
                        severidad="warning",
                        categoria="posible_regresion_tamano",
                        archivo=rel,
                        mensaje=(
                            f"Archivo vivo {size_vivo}B es <50% de la última versión en papelera "
                            f"({size_trash}B). Posible borrado accidental."
                        ),
                        datos={
                            "size_vivo": size_vivo,
                            "size_trash": size_trash,
                            "version": ultima["version"],
                        },
                    )
                )
            # Comparación AST si es Python
            if vivo.suffix == ".py":
                try:
                    syms_vivo = self._simbolos_py(vivo.read_text(encoding="utf-8"))
                    syms_trash = self._simbolos_py(Path(ultima["path"]).read_text(encoding="utf-8"))
                    perdidos = sorted(syms_trash - syms_vivo)
                    if perdidos:
                        hallazgos.append(
                            Hallazgo(
                                severidad="warning",
                                categoria="simbolos_perdidos",
                                archivo=rel,
                                mensaje=f"Símbolos presentes en papelera y ausentes en vivo: {perdidos[:10]}",
                                datos={"perdidos": perdidos, "version": ultima["version"]},
                            )
                        )
                except SyntaxError:
                    pass
                except Exception as e:
                    logger.debug(f"Comparación AST falló para {rel}: {e}")
        return hallazgos

    @staticmethod
    def _simbolos_py(src: str) -> set[str]:
        tree = ast.parse(src)
        out: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(f"{type(node).__name__}:{node.name}")
        return out


# Singleton ----------------------------------------------------------------
_auditor_instance: CoherenceAuditor | None = None


def get_coherence_auditor() -> CoherenceAuditor:
    global _auditor_instance
    if _auditor_instance is None:
        _auditor_instance = CoherenceAuditor()
    return _auditor_instance


if __name__ == "__main__":  # pragma: no cover
    aud = CoherenceAuditor()
    informe = aud.auditar()
    print(json.dumps(informe["totales"], ensure_ascii=False, indent=2))
    print(
        f"Papelera: {informe['papelera']['versiones_totales']} versiones de {informe['papelera']['archivos_distintos']} archivos."
    )
    print(f"Hallazgos: {len(informe['hallazgos'])}")
