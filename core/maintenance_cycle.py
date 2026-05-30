"""
Módulo: core/maintenance_cycle.py
Propósito: Ejecuta tareas de mantenimiento periódico: backup, limpieza, verificación de integridad.
Dependencias principales: datetime, time, json, pathlib, subprocess
Reglas especiales: Tolerancia a fallos: un error no para otros. Loggear cada tarea completada.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sys
from pathlib import Path

# Permitir ejecución directa como `python3 core/maintenance_cycle.py`
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.agente_documentador import AgenteDocumentador, get_agente_documentador
from core.change_logger import ChangeLogger, get_change_logger
from core.change_proposal_manager import ChangeProposalManager, get_change_proposal_manager
from core.coherence_auditor import CoherenceAuditor, get_coherence_auditor
from core.secure_trash import SecureTrash, get_secure_trash

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).resolve().parent / "data"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class MaintenanceCycle:
    """Ciclo único de mantenimiento integrado."""

    def __init__(
        self,
        manager: ChangeProposalManager | None = None,
        change_logger: ChangeLogger | None = None,
        auditor: CoherenceAuditor | None = None,
        trash: SecureTrash | None = None,
        documentador: AgenteDocumentador | None = None,
    ) -> None:
        self.manager = manager if manager is not None else get_change_proposal_manager()
        self.change_logger = change_logger if change_logger is not None else get_change_logger()
        self.auditor = auditor if auditor is not None else get_coherence_auditor()
        self.trash = trash if trash is not None else get_secure_trash()
        self.documentador = documentador if documentador is not None else get_agente_documentador()

    # ------------------------------------------------------------
    def ejecutar(self) -> Path:
        inicio = _dt.datetime.now()
        resumen: dict = {
            "timestamp_inicio": inicio.isoformat(timespec="seconds"),
            "modo_conservacion": self.trash.modo_conservacion,
            "etapas": {},
        }

        # 0. Catalogación previa: actualizar catalogo_ura.json
        try:
            catalogo = self.documentador.actualizar_catalogo()
            validacion_cat = self.documentador.validar_coherencia()
            resumen["etapas"]["0_catalogo"] = {
                "ruta": str(self.documentador.catalog_path),
                "agentes": len(catalogo.get("agentes", {})),
                "modulos": len(catalogo.get("modulos", {})),
                "aplicaciones": len(catalogo.get("aplicaciones", {})),
                "screens": len(catalogo.get("screens", {})),
                "problemas_coherencia": len(validacion_cat["problemas"]),
                "duplicados_funcionales": len(validacion_cat["duplicados_funcionales"]),
                "actualizado": catalogo.get("ultima_actualizacion", ""),
            }
        except Exception as e:
            logger.error(f"Fallo catalogando: {e}")
            resumen["etapas"]["0_catalogo"] = {"error": str(e)}

        # 1. Propuestas aprobadas → ejecutar
        aprobadas = self.manager.listar_propuestas(estado="aprobada")
        ejecutadas, fallidas = [], []
        for p in aprobadas:
            try:
                self.manager.ejecutar_propuesta(p.id)
                ejecutadas.append(p.id)
            except Exception as e:
                fallidas.append({"id": p.id, "error": str(e)})
                logger.error(f"Fallo ejecutando propuesta {p.id}: {e}")
        resumen["etapas"]["1_propuestas"] = {
            "aprobadas_encontradas": len(aprobadas),
            "ejecutadas": ejecutadas,
            "fallidas": fallidas,
        }

        # 2. Cambios desde el ciclo anterior
        momento_anterior = self._ultimo_timestamp_ciclo()
        cambios = (
            self.change_logger.desde(momento_anterior)
            if momento_anterior
            else self.change_logger.ultimos(50)
        )
        resumen["etapas"]["2_change_logger"] = {
            "momento_anterior": (
                momento_anterior.isoformat(timespec="seconds") if momento_anterior else None
            ),
            "cambios_detectados": len(cambios),
            "muestra": cambios[:5],
        }

        # 3. Auditoría de coherencia
        informe = self.auditor.auditar()
        resumen["etapas"]["3_auditoria"] = {
            "totales": informe["totales"],
            "papelera": informe["papelera"],
            "propuestas_pendientes": informe["propuestas_pendientes"],
        }
        resumen["_auditoria_completa"] = informe

        # 4. Rotación de papelera
        rotados: list[str] = []
        if not self.trash.modo_conservacion:
            versiones = self.trash.listar_papelera()
            for rel, lista in versiones.items():
                if len(lista) > self.trash.MAX_VERSIONS:
                    borrados = self.trash.rotar_versiones(self.trash.project_root / rel)
                    rotados.extend(str(b) for b in borrados)
        resumen["etapas"]["4_rotacion_papelera"] = {
            "modo_conservacion": self.trash.modo_conservacion,
            "max_versions": self.trash.MAX_VERSIONS,
            "rotados": rotados,
        }

        fin = _dt.datetime.now()
        resumen["timestamp_fin"] = fin.isoformat(timespec="seconds")
        resumen["duracion_segundos"] = round((fin - inicio).total_seconds(), 3)

        # 5. Guardar informe
        report_path = self._guardar_informe(resumen, inicio)
        logger.info(f"Ciclo de mantenimiento completado: {report_path}")
        return report_path

    # ------------------------------------------------------------
    def _ultimo_timestamp_ciclo(self) -> _dt.datetime | None:
        previos = sorted(REPORTS_DIR.glob("maintenance_report_*.md"))
        if not previos:
            return None
        ultimo = previos[-1]
        try:
            # Nombre formato: maintenance_report_20260507_1700.md
            stamp = ultimo.stem.replace("maintenance_report_", "")
            return _dt.datetime.strptime(stamp, "%Y%m%d_%H%M")
        except Exception:
            return None

    def _guardar_informe(self, resumen: dict, inicio: _dt.datetime) -> Path:
        stamp = inicio.strftime("%Y%m%d_%H%M")
        path = REPORTS_DIR / f"maintenance_report_{stamp}.md"
        # Evitar colisión si hay dos ciclos en el mismo minuto
        i = 1
        while path.exists():
            path = REPORTS_DIR / f"maintenance_report_{stamp}_{i}.md"
            i += 1
        path.write_text(self._render_markdown(resumen), encoding="utf-8")
        # Adicional: volcar JSON completo para otras herramientas
        path.with_suffix(".json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def _render_markdown(self, r: dict) -> str:
        totales = r["etapas"]["3_auditoria"]["totales"]
        papelera = r["etapas"]["3_auditoria"]["papelera"]
        lines = [
            f"# Informe de mantenimiento — {r['timestamp_inicio']}",
            "",
            f"- **Modo conservación**: {'ACTIVADO' if r['modo_conservacion'] else 'DESACTIVADO'}",
            f"- **Duración**: {r.get('duracion_segundos', 0)} s",
            f"- **Fin**: {r.get('timestamp_fin', '')}",
            "",
            "## 0. Catálogo URA (AgenteDocumentador)",
            "",
        ]
        cat = r["etapas"].get("0_catalogo", {})
        if "error" in cat:
            lines.append(f"- ERROR: {cat['error']}")
        else:
            lines.extend(
                [
                    f"- Ruta: `{cat.get('ruta', '')}`",
                    f"- Agentes catalogados: **{cat.get('agentes', 0)}**",
                    f"- Módulos catalogados: **{cat.get('modulos', 0)}**",
                    f"- Aplicaciones detectadas: {cat.get('aplicaciones', 0)}",
                    f"- Screens documentados: {cat.get('screens', 0)}",
                    f"- Problemas de coherencia: {cat.get('problemas_coherencia', 0)}",
                    f"- Duplicados funcionales: {cat.get('duplicados_funcionales', 0)}",
                ]
            )
        lines.extend(
            [
                "",
                "## 1. Propuestas ejecutadas",
                "",
                f"- Aprobadas encontradas: {r['etapas']['1_propuestas']['aprobadas_encontradas']}",
                f"- Ejecutadas: {len(r['etapas']['1_propuestas']['ejecutadas'])}",
                f"- Fallidas: {len(r['etapas']['1_propuestas']['fallidas'])}",
            ]
        )
        if r["etapas"]["1_propuestas"]["ejecutadas"]:
            lines.append("")
            for pid in r["etapas"]["1_propuestas"]["ejecutadas"]:
                lines.append(f"  - `{pid}`")
        if r["etapas"]["1_propuestas"]["fallidas"]:
            lines.append("")
            lines.append("**Fallidas:**")
            for f in r["etapas"]["1_propuestas"]["fallidas"]:
                lines.append(f"  - `{f['id']}`: {f['error']}")

        lines.extend(
            [
                "",
                "## 2. ChangeLogger",
                "",
                f"- Momento anterior: {r['etapas']['2_change_logger']['momento_anterior']}",
                f"- Cambios detectados: {r['etapas']['2_change_logger']['cambios_detectados']}",
                "",
                "## 3. Auditoría de coherencia",
                "",
                f"- Hallazgos totales: **{totales['hallazgos']}**",
                f"  - Errores: {totales['errores']}",
                f"  - Warnings: {totales['warnings']}",
                f"  - Infos: {totales['infos']}",
                "",
                f"- Papelera ({papelera['trash_root']}):",
                f"  - Archivos distintos: {papelera['archivos_distintos']}",
                f"  - Versiones totales: {papelera['versiones_totales']}",
                "",
                "### Propuestas pendientes/aprobadas",
                "",
            ]
        )
        pendientes = r["etapas"]["3_auditoria"]["propuestas_pendientes"]
        if pendientes:
            for a in pendientes:
                lines.append(f"- `{a}`")
        else:
            lines.append("- _(ninguna)_")

        # Hallazgos destacados
        hallazgos = r["_auditoria_completa"]["hallazgos"]
        if hallazgos:
            lines.extend(["", "### Hallazgos destacados", ""])
            for h in hallazgos[:25]:
                lines.append(
                    f"- [{h['severidad'].upper()}] `{h['archivo']}` — {h['mensaje']} ({h['categoria']})"
                )
            if len(hallazgos) > 25:
                lines.append(f"- … y {len(hallazgos) - 25} más (ver JSON adjunto).")

        lines.extend(
            [
                "",
                "## 4. Rotación de papelera",
                "",
                f"- Modo conservación: {'ACTIVADO (no se rota nada)' if r['etapas']['4_rotacion_papelera']['modo_conservacion'] else 'DESACTIVADO'}",
                f"- MAX_VERSIONS: {r['etapas']['4_rotacion_papelera']['max_versions']}",
                f"- Rotados en este ciclo: {len(r['etapas']['4_rotacion_papelera']['rotados'])}",
                "",
            ]
        )
        return "\n".join(lines)


def main() -> int:  # pragma: no cover
    pass

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )
    ciclo = MaintenanceCycle()
    path = ciclo.ejecutar()
    print(f"\nInforme generado: {path}")
    print(f"JSON asociado:    {path.with_suffix('.json')}")
    print("\n--- Contenido del informe ---\n")
    print(path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
