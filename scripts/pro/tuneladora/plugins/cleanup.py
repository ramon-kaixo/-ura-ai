"""CleanupPlugin — limpieza, aislamientos, watermark, scripts de mantenimiento."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine


class CleanupPlugin:
    """Plugins de limpieza y mantenimiento del sistema."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine

    def forense_aislamientos(self) -> dict[str, Any]:
        """Limpia procesos aislados por el SNC con más de 7 días."""
        import shutil
        import time
        from pathlib import Path

        aislados_dir = Path("/tmp/ura_aislados")
        if not aislados_dir.exists():
            return {"total": 0, "limpiados": 0, "activos": 0}

        ahora = time.time()
        activos = 0
        limpiados = 0

        for pid_dir in aislados_dir.iterdir():
            if not pid_dir.is_dir():
                continue
            nombre = (pid_dir / "nombre.txt").read_text().strip() if (pid_dir / "nombre.txt").exists() else pid_dir.name
            if not Path(f"/proc/{pid_dir.name}").exists() or ahora - pid_dir.stat().st_mtime > 604800:
                shutil.rmtree(pid_dir, ignore_errors=True)
                limpiados += 1
                self.engine.log.info(f"Aislamiento {pid_dir.name} ({nombre}) limpiado")
            else:
                activos += 1

        if activos:
            self.engine.log.warning(f"{activos} procesos aislados activos")
        return {"total": activos + limpiados, "limpiados": limpiados, "activos": activos}

    def watermark(self) -> dict[str, Any]:
        """Ejecuta watermark_aggregator."""
        result = self.engine.run_script(
            "scripts/pro/watermark_aggregator.py",
            args=["--auto-reglas"],
            timeout=30,
        )
        return {"ok": result.returncode == 0}

    def conciencia(self) -> dict[str, Any]:
        """Ejecuta analizar_fallo_conciencia."""
        result = self.engine.run_script("scripts/pro/analizar_fallo_conciencia.py", timeout=60)
        return {"ok": result.returncode == 0}

    def pareto(self) -> dict[str, Any]:
        """Ejecuta pareto_router --clasificar."""
        result = self.engine.run_script(
            "scripts/pro/pareto_router.py",
            args=["--clasificar"],
            timeout=60,
        )
        return {"ok": result.returncode == 0}

    def auto_mejora(self) -> dict[str, Any]:
        """Ejecuta ura_self_modify."""
        result = self.engine.run_script("scripts/pro/ura_self_modify.py", timeout=60)
        return {"ok": result.returncode == 0}

    def git_commit(self, message: str = "") -> dict[str, Any]:
        """Hace git commit si hay cambios."""
        if not message:
            message = f"mantenimiento: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}"
        self.engine.run_git(["add", "-u"])
        result = self.engine.run_git(["commit", "-m", message])
        if result.returncode == 0:
            self.engine.log.info(f"Git commit: {message}")
        return {"ok": result.returncode == 0}

    def git_rollback(self) -> None:
        """Revierte cambios no commiteados."""
        self.engine.run_git(["checkout", "."])
        self.engine.log.info("Git rollback ejecutado")

    def auditoria(self, profundo: bool = False) -> dict[str, Any]:
        """Ejecuta revisor.py."""
        flags = "--full" if profundo else "--quick"
        result = self.engine.run_script("scripts/pro/revisor.py", args=[flags], timeout=120)
        try:
            reporte = json.loads(result.stdout) if result.stdout else {}
        except Exception:
            reporte = {}
        score = reporte.get("score", 0)
        bloqueante = reporte.get("bloqueante", False)
        if bloqueante:
            self.engine.log.warning(f"Score bloqueante: {score}")
        return {"score": score, "bloqueante": bloqueante, "raw": reporte}


def run_auto_cleanup():
    """Ejecuta limpieza automatica semanal."""
    import subprocess

    subprocess.run(["python", "scripts/pro/cleanup_logs.py"])
    subprocess.run(["python", "scripts/pro/vacuum_sqlite.py"])
    subprocess.run(["python", "scripts/pro/cleanup_embeddings.py"])
