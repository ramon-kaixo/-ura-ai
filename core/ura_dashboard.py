#!/usr/bin/env python3
"""
Interfaz Visual para Monitorear Conciencia de URA

Dashboard para monitorear estado de conciencia:
- Visualización de conflictos detectados
- Gráficos de uso de recursos
- Métricas en tiempo real
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class URADashboard:
    """Dashboard para monitorear conciencia de URA."""

    def __init__(self):
        self.html_template = self._get_html_template()

    def _get_html_template(self) -> str:
        """Obtener template HTML del dashboard."""
        return """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>URA Consciousness Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 {
            text-align: center;
            color: #667eea;
            margin-bottom: 30px;
        }
        .section {
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .section h2 {
            color: #667eea;
            margin-top: 0;
        }
        .metric {
            display: inline-block;
            margin: 10px;
            padding: 15px;
            background: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            min-width: 150px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        .metric-label {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        .conflict {
            padding: 10px;
            margin: 5px 0;
            background: #fff3cd;
            border-left: 3px solid #ffc107;
            border-radius: 3px;
        }
        .conflict-high {
            background: #f8d7da;
            border-left-color: #dc3545;
        }
        .conflict-medium {
            background: #fff3cd;
            border-left-color: #ffc107;
        }
        .conflict-low {
            background: #d1ecf1;
            border-left-color: #17a2b8;
        }
        .status {
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
        }
        .status-ok {
            background: #d4edda;
            color: #155724;
        }
        .status-warning {
            background: #fff3cd;
            color: #856404;
        }
        .status-error {
            background: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>URA Consciousness Dashboard</h1>

        <div class="section">
            <h2>Estado del Sistema</h2>
            <div id="system-status"></div>
        </div>

        <div class="section">
            <h2>Métricas de Conciencia</h2>
            <div id="metrics"></div>
        </div>

        <div class="section">
            <h2>Configuración Dinámica</h2>
            <div id="config"></div>
        </div>

        <div class="section">
            <h2>Conflictos Detectados</h2>
            <div id="conflicts"></div>
        </div>

        <div class="section">
            <h2>Rollback & Snapshots</h2>
            <div id="rollback"></div>
        </div>

        <div class="section">
            <h2>Auto-Pruning</h2>
            <div id="pruning"></div>
        </div>

        <p style="text-align: center; color: #666; margin-top: 30px;">
            Última actualización: <span id="last-update"></span>
        </p>
    </div>

    <script>
        function updateDashboard() {
            // Aquí se cargarían los datos desde el backend
            document.getElementById('last-update').textContent = new Date().toLocaleString();
        }

        updateDashboard();
        setInterval(updateDashboard, 5000); // Actualizar cada 5 segundos
    </script>
</body>
</html>
        """

    def generate_dashboard(self) -> str:
        """Generar dashboard HTML con datos actuales."""
        html = self.html_template

        # Obtener datos de los sistemas
        try:
            from core.ura_auto_pruning import URAAutoPruning
            from core.ura_dynamic_config import URADynamicConfig
            from core.ura_metrics import URAMetrics
            from core.ura_rollback import URARollback
            from core.ura_unified_context import URAUnifiedContext

            metrics = URAMetrics()
            config = URADynamicConfig()
            unified = URAUnifiedContext()
            rollback = URARollback()
            pruning = URAAutoPruning()

            # Generar HTML para cada sección
            metrics_html = self._generate_metrics_html(metrics)
            config_html = self._generate_config_html(config)
            conflicts_html = self._generate_conflicts_html(unified)
            rollback_html = self._generate_rollback_html(rollback)
            pruning_html = self._generate_pruning_html(pruning)
            status_html = self._generate_status_html(unified)

            # Reemplazar placeholders
            html = html.replace('<div id="metrics"></div>', metrics_html)
            html = html.replace('<div id="config"></div>', config_html)
            html = html.replace('<div id="conflicts"></div>', conflicts_html)
            html = html.replace('<div id="rollback"></div>', rollback_html)
            html = html.replace('<div id="pruning"></div>', pruning_html)
            html = html.replace('<div id="system-status"></div>', status_html)

        except Exception as e:
            logger.error(f"Error generando dashboard: {e}")

        return html

    def _generate_metrics_html(self, metrics) -> str:
        """Generar HTML para métricas."""
        top_levels = metrics.get_top_levels_by_impact(3)
        total_usage = sum(m.usage_count for m in metrics.metrics.values())

        html = f"""
        <div class="metric">
            <div class="metric-value">{total_usage}</div>
            <div class="metric-label">Usos Totales</div>
        </div>
        <div class="metric">
            <div class="metric-value">{len(metrics.metrics)}</div>
            <div class="metric-label">Niveles Activos</div>
        </div>
        <div class="metric">
            <div class="metric-value">{", ".join(top_levels[:2])}</div>
            <div class="metric-label">Top Niveles</div>
        </div>
        """
        return html

    def _generate_config_html(self, config) -> str:
        """Generar HTML para configuración."""
        profile = config.get_current_profile()

        html = f"""
        <div class="status status-ok">
            <strong>Perfil Actual:</strong> {profile.profile_name}<br>
            <strong>Niveles Activos:</strong> {len(profile.active_levels)}/23<br>
            <strong>Cache TTL:</strong> {profile.cache_ttl}s<br>
            <strong>Lazy Loading:</strong> {"Sí" if profile.lazy_loading else "No"}
        </div>
        """
        return html

    def _generate_conflicts_html(self, unified) -> str:
        """Generar HTML para conflictos."""
        conflicts = unified.conflict_detector.conflict_log

        if not conflicts:
            return '<div class="status status-ok">No hay conflictos registrados.</div>'

        html = ""
        for conflict in conflicts[-5:]:
            severity_class = f"conflict-{conflict.get('severity', 'low')}"
            html += f"""
            <div class="conflict {severity_class}">
                <strong>{conflict.get("level1", "")}</strong> vs <strong>{conflict.get("level2", "")}</strong><br>
                {conflict.get("reason", "")}<br>
                <small>{conflict.get("timestamp", "")}</small>
            </div>
            """

        return html

    def _generate_rollback_html(self, rollback) -> str:
        """Generar HTML para rollback."""
        if not rollback.snapshots:
            return '<div class="status status-warning">No hay snapshots disponibles.</div>'

        html = f"""
        <div class="metric">
            <div class="metric-value">{len(rollback.snapshots)}</div>
            <div class="metric-label">Snapshots Totales</div>
        </div>
        <div class="metric">
            <div class="metric-value">{len({s.level_name for s in rollback.snapshots})}</div>
            <div class="metric-label">Niveles con Snapshots</div>
        </div>
        """
        return html

    def _generate_pruning_html(self, pruning) -> str:
        """Generar HTML para pruning."""
        html = f"""
        <div class="metric">
            <div class="metric-value">{len(pruning.rules)}</div>
            <div class="metric-label">Niveles Monitoreados</div>
        </div>
        <div class="status status-ok">
            <strong>Estado:</strong> Auto-pruning activo
        </div>
        """
        return html

    def _generate_status_html(self, unified) -> str:
        """Generar HTML para estado del sistema."""
        # Calcular carga del sistema
        try:
            import psutil

            cpu_load = psutil.cpu_percent()
            memory_load = psutil.virtual_memory().percent
        except Exception:
            cpu_load = 50
            memory_load = 50

        status_class = "status-ok" if cpu_load < 70 and memory_load < 70 else "status-warning"

        html = f"""
        <div class="status {status_class}">
            <strong>CPU:</strong> {cpu_load}% | <strong>Memoria:</strong> {memory_load}%<br>
            <strong>Niveles de Conciencia:</strong> 20 activos<br>
            <strong>Estado:</strong> {"Operativo" if cpu_load < 80 and memory_load < 80 else "Alta Carga"}
        </div>
        """
        return html

    def save_dashboard(self, output_path: Path = None):
        """Guardar dashboard HTML a archivo."""
        if output_path is None:
            output_path = Path.home() / ".ura" / "dashboard.html"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        html = self.generate_dashboard()
        with open(output_path, "w") as f:
            f.write(html)

        return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dashboard = URADashboard()

    # Generar y guardar dashboard
    output_path = dashboard.save_dashboard()
    print(f"Dashboard generado en: {output_path}")
    print("Abre el archivo en tu navegador para ver el dashboard de URA")
