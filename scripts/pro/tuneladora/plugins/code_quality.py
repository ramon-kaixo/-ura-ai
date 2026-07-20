"""CodeQualityPlugin — ruff, formato, F821, token_screen, inspectores."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine


class CodeQualityPlugin:
    """Plugins de calidad de código. Fase validation."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine

    def ruff_check(self, select: str = "F821,F841,E402") -> dict[str, Any]:
        """Ejecuta ruff check y retorna conteo de errores."""
        result = self.engine.run_ruff(["check", "--select", select, "--output-format", "concise", "."])
        f821 = result.stdout.count("F821")
        f841 = result.stdout.count("F841")
        self.engine.log.info(f"Ruff: {f821} F821, {f841} F841")
        return {"f821": f821, "f841": f841, "returncode": result.returncode}

    def ruff_fix(self, select: str = "", unsafe: bool = False) -> dict[str, Any]:
        """Ejecuta ruff --fix."""
        args = ["check", "--fix"]
        if unsafe:
            args.append("--unsafe-fixes")
        if select:
            args.extend(["--select", select])
        args.append(".")
        timeout = 300 if unsafe else 120
        result = self.engine.run_ruff(args, timeout=timeout)
        return {"returncode": result.returncode}

    def ruff_format(self) -> dict[str, Any]:
        """Ejecuta ruff format."""
        result = self.engine.run_ruff(["format", "."], timeout=120)
        return {"returncode": result.returncode}

    def token_screen(self) -> dict[str, Any]:
        """Ejecuta token_screen."""
        result = self.engine.run_script(
            "scripts/pro/token_screen.py",
            args=["--texto", "test", "--json"],
            timeout=15,
        )
        return {"ok": result.returncode == 0}

    def scanner(self, mode: str = "json") -> dict[str, Any]:
        """Ejecuta scanner_autoajuste."""
        args = ["--json"] if mode == "json" else ["--diff", "--json"]
        result = self.engine.run_script("scripts/pro/scanner_autoajuste.py", args=args, timeout=30)
        return {"returncode": result.returncode}

    def poda(self) -> dict[str, Any]:
        """Ejecuta poda_mecanica."""
        result = self.engine.run_script("scripts/pro/poda_mecanica.py", args=["--json"], timeout=30)
        return {"returncode": result.returncode}

    def compactadora(self) -> dict[str, Any]:
        """Ejecuta compactadora + auto_reglas."""
        self.engine.run_script("scripts/pro/compactadora.py", args=[], timeout=15)
        self.engine.run_script("scripts/pro/auto_reglas.py", args=["--generar"], timeout=30)
        return {"ok": True}

    def inspectores(self) -> dict[str, Any]:
        """Ejecuta inspectores."""
        result = self.engine.run_script("scripts/pro/inspectores.py", args=["--json"], timeout=60)
        return {"ok": result.returncode == 0}

    def f821_snapshot(self, label: str = "mantenimiento") -> dict[str, Any]:
        """Toma snapshot F821."""
        self.engine.run_script(
            "scripts/pro/f821_watch.py",
            args=["snapshot", "--label", label],
            timeout=30,
        )
        return {"ok": True}

    def f821_compare(self, target: str = "mantenimiento") -> dict[str, Any]:
        """Compara F821 contra un target."""
        result = self.engine.run_script(
            "scripts/pro/f821_watch.py",
            args=["compare", "--target", target],
            timeout=30,
        )
        return {"ok": result.returncode == 0, "output": result.stdout[:200]}
