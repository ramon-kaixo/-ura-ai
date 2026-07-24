"""CleanupPlugin — limpieza, aislamientos, watermark, scripts de mantenimiento.

v3.0: integra logica de scripts sueltos directamente.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine


class CleanupPlugin:
    """Plugins de limpieza y mantenimiento del sistema."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine

    def cleanup_logs(self, days: int = 30) -> dict[str, Any]:
        """Elimina logs mayores a N dias."""
        log_dir = Path.home() / "URA" / "ura_ia_1972" / "motor" / "observability" / "logs"
        cutoff = time.time() - (days * 86400)
        removed = 0
        if not log_dir.exists():
            return {"removed": 0, "reason": "log_dir_not_found"}
        for f in log_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                try:
                    f.unlink()
                    removed += 1
                except Exception as e:
                    self.engine.log.warning(f"Error eliminando {f.name}: {e}")
        self.engine.log.info(f"Logs eliminados: {removed} (>{days} dias)")
        return {"removed": removed, "days": days}

    def cleanup_embeddings(self) -> dict[str, Any]:
        """Elimina embeddings sin documento asociado."""
        emb_dir = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "embeddings"
        doc_dir = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "documents"
        removed = 0
        if not emb_dir.exists():
            return {"removed": 0, "reason": "embeddings_dir_not_found"}
        for emb in emb_dir.iterdir():
            doc = doc_dir / emb.name
            if not doc.exists():
                try:
                    emb.unlink()
                    removed += 1
                except Exception as e:
                    self.engine.log.warning(f"Error eliminando {emb.name}: {e}")
        self.engine.log.info(f"Embeddings huerfanos: {removed} eliminados")
        return {"removed": removed}

    def vacuum_sqlite(self) -> dict[str, Any]:
        """Ejecuta VACUUM en bases SQLite."""
        bases = ["knowledge/knowledge.db"]
        results: list[dict[str, Any]] = []
        for db_path in bases:
            p = Path(db_path)
            if not p.exists():
                results.append({"path": db_path, "status": "skipped"})
                continue
            try:
                conn = sqlite3.connect(str(p))
                conn.execute("VACUUM")
                conn.close()
                results.append({"path": db_path, "status": "ok"})
                self.engine.log.info(f"VACUUM OK: {db_path}")
            except Exception as e:
                self.engine.log.warning(f"VACUUM FAIL {db_path}: {e}")
                results.append({"path": db_path, "status": "error", "error": str(e)})
        return {"results": results}

    def check_disk(self, threshold: float = 90.0) -> dict[str, Any]:
        """Verifica espacio en disco. Retorna porcentaje usado."""
        try:
            usage = shutil.disk_usage("/")
            percent = round((usage.used / usage.total) * 100, 1)
            libre_gb = round((usage.free / (1024**3)), 1)
            status = "ok" if percent < threshold else "warning"
            if status == "warning":
                self.engine.log.warning(f"DISCO: {percent}% usado (>{threshold}%)")
            else:
                self.engine.log.info(f"DISCO: {percent}% usado (libre: {libre_gb}GB)")
            return {"percent": percent, "libre_gb": libre_gb, "status": status, "threshold": threshold}
        except Exception as e:
            self.engine.log.warning(f"Disk check fallo: {e}")
            return {"percent": -1, "status": "error", "error": str(e)}

    def detect_duplicates(self) -> dict[str, Any]:
        """Detecta funciones duplicadas via AST."""
        import ast
        import hashlib
        from collections import defaultdict

        duplicates: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
        for f in Path().rglob("*.py"):
            if any(x in str(f) for x in ["test", "__pycache__", ".venv", ".sandbox_packages", "build"]):
                continue
            try:
                tree = ast.parse(f.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and len(node.body) > 3:
                        h = hashlib.sha256(ast.dump(node).encode()).hexdigest()[:16]
                        duplicates[h].append((str(f), node.name, node.lineno))
            except SyntaxError:
                continue
        groups = sum(1 for items in duplicates.values() if len(items) > 1)
        self.engine.log.info(f"Duplicados detectados: {groups} grupos")
        return {"groups": groups, "total_funcs": len(duplicates)}

    def tech_debt_report(self) -> dict[str, Any]:
        """Genera metricas de deuda tecnica."""
        todo_count = 0
        fixme_count = 0
        for f in Path("motor").rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                text = f.read_text()
                todo_count += text.count("TODO")
                fixme_count += text.count("FIXME")
            except Exception:
                continue
        self.engine.log.info(f"Tech debt: {todo_count} TODO, {fixme_count} FIXME")
        return {"todos": todo_count, "fixmes": fixme_count}

    # ── Metodos existentes ─────────────────────────────────

    def forense_aislamientos(self) -> dict[str, Any]:
        """Limpia procesos aislados por el SNC con mas de 7 dias."""
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
        result = self.engine.run_script("scripts/pro/watermark_aggregator.py", args=["--auto-reglas"], timeout=30)
        return {"ok": result.returncode == 0}

    def conciencia(self) -> dict[str, Any]:
        result = self.engine.run_script("scripts/pro/analizar_fallo_conciencia.py", timeout=60)
        return {"ok": result.returncode == 0}

    def pareto(self) -> dict[str, Any]:
        result = self.engine.run_script("scripts/pro/pareto_router.py", args=["--clasificar"], timeout=60)
        return {"ok": result.returncode == 0}

    def auto_mejora(self) -> dict[str, Any]:
        result = self.engine.run_script("scripts/pro/ura_self_modify.py", timeout=60)
        return {"ok": result.returncode == 0}

    def git_commit(self, message: str = "") -> dict[str, Any]:
        if not message:
            message = f"mantenimiento: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}"
        self.engine.run_git(["add", "-u"])
        result = self.engine.run_git(["commit", "-m", message])
        if result.returncode == 0:
            self.engine.log.info(f"Git commit: {message}")
        return {"ok": result.returncode == 0}

    def git_rollback(self) -> None:
        self.engine.run_git(["checkout", "."])
        self.engine.log.info("Git rollback ejecutado")

    def auditoria(self, profundo: bool = False) -> dict[str, Any]:
        flags = "--full" if profundo else "--quick"
        result = self.engine.run_script("scripts/pro/revisor.py", args=[flags], timeout=120)
        try:
            reporte = json.loads(result.stdout) if result.stdout else {}
        except Exception:
            reporte = {}
        if reporte.get("bloqueante"):
            self.engine.log.warning(f"Score bloqueante: {reporte.get("score", 0)}")
        return {"score": reporte.get("score", 0), "bloqueante": reporte.get("bloqueante", False), "raw": reporte}
