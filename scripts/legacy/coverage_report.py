#!/usr/bin/env python3
"""
URA Coverage Report - Generación de reportes de cobertura
"""

import json
import subprocess
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger("coverage_report", log_dir="./logs")


class CoverageReporter:
    """Generador de reportes de cobertura"""

    def __init__(self, source_dirs: list = None, min_coverage: float = 80.0):
        """
        Inicializar reporter

        Args:
            source_dirs: Directorios fuente
            min_coverage: Cobertura mínima requerida
        """
        self.source_dirs = source_dirs or ["core"]
        self.min_coverage = min_coverage

    def run_coverage(self) -> dict:
        """
        Ejecutar análisis de cobertura

        Returns:
            Resultados de cobertura
        """
        cmd = [
            "python",
            "-m",
            "pytest",
            "--cov=" + ",".join(self.source_dirs),
            "--cov-report=json",
            "--cov-report=html",
            "--cov-report=term",
            "tests/",
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True)
            logger.info("Coverage analysis completed")

            # Leer resultados JSON
            coverage_file = Path("coverage.json")
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)
                return self._parse_coverage_data(coverage_data)

            return {"error": "Coverage file not found"}

        except Exception as e:
            logger.error(f"Error running coverage: {e}")
            return {"error": str(e)}

    def _parse_coverage_data(self, data: dict) -> dict:
        """
        Parsear datos de cobertura

        Args:
            data: Datos de coverage.json

        Returns:
            Resultados parseados
        """
        totals = data.get("totals", {})

        return {
            "coverage_percent": round(totals.get("percent_covered", 0), 2),
            "lines_covered": totals.get("covered_lines", 0),
            "lines_total": totals.get("num_statements", 0),
            "missing_lines": totals.get("missing_lines", 0),
            "meets_minimum": totals.get("percent_covered", 0) >= self.min_coverage,
        }

    def generate_html_report(self) -> str:
        """
        Generar reporte HTML

        Returns:
            Ruta del reporte
        """
        report_path = "htmlcov/index.html"
        if Path(report_path).exists():
            logger.info(f"HTML report generated: {report_path}")
            return report_path
        return None


if __name__ == "__main__":
    reporter = CoverageReporter()
    results = reporter.run_coverage()
    print(f"Coverage results: {results}")
