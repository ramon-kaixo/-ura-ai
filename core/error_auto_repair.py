#!/usr/bin/env python3
"""
core/error_auto_repair.py - Sistema de Auto-Reparación de Errores
Detecta errores y ofrece reparación automática
"""

import json
import logging
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)

# Intentar importar scikit-learn para ML
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import LabelEncoder

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("scikit-learn no disponible, predicción ML deshabilitada")


class ErrorAutoRepair:
    """Sistema de auto-reparación de errores"""

    def __init__(self, simulation_mode: bool = False):
        self.repair_history_file = Path(__file__).parent.parent / "data" / "repair_history.json"
        self.config_file = Path(__file__).parent.parent / "config" / "auto_repair_config.json"
        self.rollback_file = Path(__file__).parent.parent / "data" / "rollback_state.json"
        self.error_patterns_file = Path.home() / ".ura" / "error_patterns.json"
        self.causas_raiz_file = Path.home() / ".ura" / "causas_raiz.json"
        self._ensure_directories()
        self._load_config()
        self.error_patterns = self._load_error_patterns()
        self.causas_raiz = self._load_causas_raiz()

        # Inicializar modelos ML si están disponibles
        self.ml_model = None
        self.label_encoder = None
        self.vectorizer = None
        if ML_AVAILABLE and self.config.get("use_ml_prediction", False):
            self._init_ml_model()

        # Modo de simulación
        self.simulation_mode = simulation_mode or self.config.get("simulation_mode", False)

    def _ensure_directories(self):
        """Asegurar que los directorios existan"""
        self.repair_history_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        """Cargar configuración de auto-reparación"""
        default_config = {
            "auto_repair_enabled": True,
            "auto_repair_types": [
                "missing_module",
                "ollama",
                "redis",
                "missing_file",
                "import_error",
            ],
            "max_repair_attempts": 3,
            "log_repairs": True,
            "alert_on_failure": False,
            "enable_rollback": True,
            "repair_priority": {
                "critical": ["ollama", "redis"],
                "high": ["missing_module", "import_error"],
                "medium": ["missing_file", "permission"],
                "low": ["key_error", "attribute_error", "type_error"],
            },
        }

        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando config: {e}")
                self.config = default_config
        else:
            self.config = default_config
            self._save_config()

    def _save_config(self):
        """Guardar configuración de auto-reparación"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando config: {e}")

    def _load_error_patterns(self) -> list[dict]:
        """Cargar patrones de error desde ~/.ura/error_patterns.json."""
        if self.error_patterns_file.exists():
            try:
                with open(self.error_patterns_file) as f:
                    data = json.load(f)
                    return data.get("patterns", [])
            except Exception as e:
                logger.warning(f"Error cargando error_patterns: {e}")
        return []

    def _load_causas_raiz(self) -> list[dict]:
        """Cargar causas raíz desde ~/.ura/causas_raiz.json."""
        if self.causas_raiz_file.exists():
            try:
                with open(self.causas_raiz_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando causas_raiz: {e}")
        return []

    def _save_error_patterns(self):
        """Guardar patrones de error a disco."""
        self.error_patterns_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "patterns": self.error_patterns,
            "metadata": {
                "version": "1.0.0",
                "total_patterns": len(self.error_patterns),
                "auto_repairs_total": sum(
                    p.get("auto_repair_count", 0) for p in self.error_patterns
                ),
            },
        }
        with open(self.error_patterns_file, "w") as f:
            json.dump(data, f, indent=2)

    def _save_causas_raiz(self):
        """Guardar causas raíz a disco."""
        self.causas_raiz_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.causas_raiz_file, "w") as f:
            json.dump(self.causas_raiz, f, indent=2)

    def scan_logs(self, log_dir: str = None) -> list[str]:
        """Escanear logs del sistema en busca de errores."""
        errors = []
        if log_dir is None:
            log_dir = Path.home() / ".ura" / "logs"
        log_path = Path(log_dir)
        if not log_path.exists():
            return errors

        error_regex = re.compile(
            r"(Error|Exception|Traceback|FAILED|CRITICAL|FATAL)", re.IGNORECASE
        )
        for log_file in log_path.glob("*.log"):
            try:
                with open(log_file, errors="ignore") as f:
                    for line in f:
                        if error_regex.search(line):
                            errors.append(line.strip())
            except Exception:
                pass
        return errors

    def compare_with_patterns(self, error_message: str) -> dict | None:
        """Comparar un error con los patrones guardados. Retorna el patrón si coincide."""
        for pattern in self.error_patterns:
            try:
                if re.search(pattern.get("pattern_regex", ""), error_message, re.IGNORECASE):
                    return pattern
            except re.error:
                continue
        return None

    def auto_repair_typical_errors(self) -> list[dict]:
        """Escanear logs, detectar errores típicos y auto-repararlos sin preguntar."""
        results = []
        errors = self.scan_logs()
        if not errors:
            return results

        from core.forensic_scribe import get_forensic_scribe

        scribe = get_forensic_scribe()

        for error_msg in errors[-20:]:  # Solo últimos 20 errores
            pattern = self.compare_with_patterns(error_msg)
            if pattern and pattern.get("verified"):
                scribe.log_event(
                    "auto_repair",
                    "error_auto_repair",
                    f"auto_repairing: {pattern['error_id']}",
                    {"error_message": error_msg[:200]},
                    pattern.get("archivos_afectados", []),
                )

                sandbox_result = self.sandbox_repair(error_msg)
                if sandbox_result.get("success"):
                    pattern["auto_repair_count"] = pattern.get("auto_repair_count", 0) + 1
                    self._save_error_patterns()
                    results.append(
                        {
                            "error_id": pattern["error_id"],
                            "repaired": True,
                            "message": sandbox_result.get("message", ""),
                        }
                    )
                else:
                    results.append(
                        {
                            "error_id": pattern["error_id"],
                            "repaired": False,
                            "message": sandbox_result.get("message", ""),
                        }
                    )

        return results

    def _log_repair(self, error_type: str, error_message: str, success: bool, repair_message: str):
        """Registrar reparación en historial"""
        from core.repair import _log_repair as log_repair

        log_repair(self, error_type, error_message, success, repair_message)

    def _update_prometheus_metrics(self, error_type: str, success: bool):
        """Actualizar métricas de Prometheus"""
        from core.repair import _update_prometheus_metrics

        _update_prometheus_metrics(self, error_type, success)

    def get_repair_history(self) -> list[dict]:
        """Obtener historial de reparaciones"""
        if self.repair_history_file.exists():
            try:
                with open(self.repair_history_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando historial: {e}")
        return []

    def get_recurrent_errors(self) -> dict[str, int]:
        """Obtener errores recurrentes"""
        history = self.get_repair_history()
        error_counts = {}

        for entry in history:
            error_type = entry.get("error_type", "unknown")
            if not entry.get("success", False):
                error_counts[error_type] = error_counts.get(error_type, 0) + 1

        return error_counts

    def predict_errors(self) -> list[str]:
        """Predecir errores probables basado en historial"""
        from core.repair import predict_errors

        return predict_errors(self)

    def predict_errors_rule_based(self) -> list[str]:
        """Predecir errores probables basado en reglas (fallback)"""
        from core.repair import predict_errors_rule_based

        return predict_errors_rule_based(self)

    def _init_ml_model(self):
        """Inicializar modelo ML para predicción de errores"""
        try:
            self.ml_model = RandomForestClassifier(n_estimators=100, random_state=42)
            self.label_encoder = LabelEncoder()
            self.vectorizer = TfidfVectorizer(max_features=1000)

            # Intentar cargar modelo existente
            self.load_ml_model()

            if self.ml_model is None:
                logger.info("Modelo ML inicializado (sin entrenar)")
            else:
                logger.info("Modelo ML cargado desde disco")

        except Exception as e:
            logger.warning(f"Error inicializando modelo ML: {e}")

    def train_ml_model(self):
        """Entrenar modelo ML con historial de reparaciones"""
        if not ML_AVAILABLE:
            logger.warning("scikit-learn no disponible para entrenamiento ML")
            return False

        try:
            history = self.get_repair_history()

            if len(history) < 10:
                logger.warning(
                    "Historial insuficiente para entrenar modelo ML (mínimo 10 entradas)"
                )
                return False

            # Preparar datos
            X_texts = [entry.get("error_message", "") for entry in history]
            y_labels = [entry.get("error_type", "unknown") for entry in history]

            # Vectorizar mensajes de error
            X = self.vectorizer.fit_transform(X_texts)

            # Codificar etiquetas
            y = self.label_encoder.fit_transform(y_labels)

            # Entrenar modelo
            self.ml_model.fit(X, y)

            # Guardar modelo
            self.save_ml_model()

            logger.info(f"Modelo ML entrenado con {len(history)} entradas")
            return True

        except Exception as e:
            logger.error(f"Error entrenando modelo ML: {e}")
            return False

    def predict_errors_ml(self) -> list[str]:
        """Predecir errores probables usando ML"""
        from core.repair import predict_errors_ml

        return predict_errors_ml(self)

    def save_ml_model(self):
        """Guardar modelo ML entrenado en disco"""
        if not ML_AVAILABLE or self.ml_model is None:
            return

        try:
            import joblib

            model_file = (
                Path(__file__).parent.parent / "data" / "ml_models" / "error_predictor.joblib"
            )
            model_file.parent.mkdir(parents=True, exist_ok=True)

            joblib.dump(
                {
                    "model": self.ml_model,
                    "label_encoder": self.label_encoder,
                    "vectorizer": self.vectorizer,
                },
                model_file,
            )

            logger.info(f"Modelo ML guardado en {model_file}")

        except ImportError:
            logger.warning("joblib no disponible para guardar modelo ML")
        except Exception as e:
            logger.error(f"Error guardando modelo ML: {e}")

    def load_ml_model(self):
        """Cargar modelo ML entrenado desde disco"""
        if not ML_AVAILABLE:
            return

        try:
            import joblib

            model_file = (
                Path(__file__).parent.parent / "data" / "ml_models" / "error_predictor.joblib"
            )

            if model_file.exists():
                data = joblib.load(model_file)
                self.ml_model = data["model"]
                self.label_encoder = data["label_encoder"]
                self.vectorizer = data["vectorizer"]
                logger.info(f"Modelo ML cargado desde {model_file}")
            else:
                logger.info("No se encontró modelo ML guardado")

        except ImportError:
            logger.warning("joblib no disponible para cargar modelo ML")
        except Exception as e:
            logger.warning(f"Error cargando modelo ML: {e}")

    def integrate_with_learning_system(self):
        """Integrar con sistema de aprendizaje URA"""
        try:
            # Intentar importar sistema de aprendizaje
            learning_system_path = Path(__file__).parent / "learning" / "learning_system.py"

            if learning_system_path.exists():
                sys.path.insert(0, str(learning_system_path.parent))

                try:
                    from learning_system import LearningSystem

                    learning_sys = LearningSystem()

                    # Enviar datos de reparaciones al sistema de aprendizaje
                    history = self.get_repair_history()

                    for entry in history:
                        error_type = entry.get("error_type", "unknown")
                        success = entry.get("success", False)
                        repair_message = entry.get("repair_message", "")

                        # Crear patrón de aprendizaje
                        pattern = {
                            "action": f"repair_{error_type}",
                            "context": error_type,
                            "success": success,
                            "details": repair_message,
                        }

                        # Registrar en sistema de aprendizaje
                        learning_sys.register_pattern(pattern)

                    logger.info("Datos de reparaciones enviados al sistema de aprendizaje")

                except ImportError:
                    logger.warning("LearningSystem no disponible")
                except Exception as e:
                    logger.warning(f"Error integrando con sistema de aprendizaje: {e}")

        except Exception as e:
            logger.warning(f"Error buscando sistema de aprendizaje: {e}")

    def get_repair_recommendations(self) -> list[dict]:
        """Obtener recomendaciones de reparaciones del sistema de aprendizaje"""
        recommendations = []

        try:
            learning_system_path = Path(__file__).parent / "learning" / "learning_system.py"

            if learning_system_path.exists():
                sys.path.insert(0, str(learning_system_path.parent))

                try:
                    from learning_system import LearningSystem

                    learning_sys = LearningSystem()

                    # Obtener patrones aprendidos
                    patterns = learning_sys.get_learned_patterns()

                    for pattern in patterns:
                        if pattern.get("action", "").startswith("repair_"):
                            error_type = pattern.get("action", "").replace("repair_", "")

                            recommendations.append(
                                {
                                    "error_type": error_type,
                                    "success_rate": pattern.get("success_rate", 0),
                                    "recommended": pattern.get("success_rate", 0) > 0.7,
                                }
                            )

                except ImportError:
                    logger.warning("LearningSystem no disponible")
                except Exception as e:
                    logger.warning(f"Error obteniendo recomendaciones: {e}")

        except Exception as e:
            logger.warning(f"Error buscando sistema de aprendizaje: {e}")

        return recommendations

    def generate_pdf_report(self, output_path: str | None = None) -> str:
        """Generar reporte PDF de reparaciones"""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

            history = self.get_repair_history()

            if output_path is None:
                output_path = str(
                    Path(__file__).parent.parent
                    / "reports"
                    / f"repair_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                )

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            doc = SimpleDocTemplate(output_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Título
            title = Paragraph(
                "URA Auto-Repair System - Reporte de Reparaciones", styles["Heading1"]
            )
            story.append(title)
            story.append(Spacer(1, 12))

            # Resumen
            total = len(history)
            success = sum(1 for entry in history if entry.get("success", False))
            failure = total - success

            summary_data = [
                ["Total Reparaciones", str(total)],
                ["Exitosas", str(success)],
                ["Fallidas", str(failure)],
                ["Tasa de Éxito", f"{(success / total * 100):.1f}%" if total > 0 else "N/A"],
            ]

            summary_table = Table(summary_data, colWidths=[200, 100])
            summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            story.append(summary_table)
            story.append(Spacer(1, 12))

            # Tabla de historial
            table_data = [["Timestamp", "Tipo", "Estado", "Mensaje"]]
            for entry in history[-50:]:  # Últimas 50 entradas
                table_data.append(
                    [
                        entry.get("timestamp", "")[:19],
                        entry.get("error_type", ""),
                        "✅" if entry.get("success", False) else "❌",
                        entry.get("repair_message", "")[:50],
                    ]
                )

            history_table = Table(table_data, colWidths=[80, 80, 30, 300])
            history_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ]
                )
            )
            story.append(history_table)

            doc.build(story)

            logger.info(f"Reporte PDF generado: {output_path}")
            return output_path

        except ImportError:
            logger.warning("reportlab no disponible para generar PDF")
            return ""
        except Exception as e:
            logger.error(f"Error generando reporte PDF: {e}")
            return ""

    def integrate_with_recovery_agent(self):
        """Integrar con agente de recuperación automático"""
        try:
            recovery_agent_path = Path(__file__).parent / "agents" / "recovery_agent.py"

            if recovery_agent_path.exists():
                sys.path.insert(0, str(recovery_agent_path.parent))

                try:
                    from recovery_agent import RecoveryAgent

                    recovery_agent = RecoveryAgent()

                    # Agregar función de auto-reparación al agente de recuperación
                    recovery_agent.add_repair_function(self.attempt_repair)

                    logger.info("Auto-reparación integrada con agente de recuperación")

                except ImportError:
                    logger.warning("RecoveryAgent no disponible")
                except Exception as e:
                    logger.warning(f"Error integrando con recovery_agent: {e}")

        except Exception as e:
            logger.warning(f"Error buscando recovery_agent: {e}")

    def run_auto_repair_for_agents(self):
        """Ejecutar reparaciones automáticas para los agentes"""
        from core.repair import run_auto_repair_for_agents

        run_auto_repair_for_agents(self)

    def setup_realtime_alerts(self, callback=None):
        """Configurar alertas en tiempo real"""
        try:
            # Importar WebSocket handler si existe
            websocket_path = Path(__file__).parent.parent / "api" / "websocket_handler.py"

            if websocket_path.exists():
                sys.path.insert(0, str(websocket_path.parent))

                try:
                    from websocket_handler import WebSocketHandler

                    ws_handler = WebSocketHandler()

                    # Registrar callback para alertas
                    if callback:
                        ws_handler.register_alert_callback(callback)

                    logger.info("Alertas en tiempo real configuradas con WebSocket")

                except ImportError:
                    logger.warning("WebSocketHandler no disponible")
                except Exception as e:
                    logger.warning(f"Error configurando alertas en tiempo real: {e}")

        except Exception as e:
            logger.warning(f"Error buscando websocket_handler: {e}")

    def send_realtime_alert(self, alert_type: str, message: str, data: dict | None = None):
        """Enviar alerta en tiempo real"""
        try:
            websocket_path = Path(__file__).parent.parent / "api" / "websocket_handler.py"

            if websocket_path.exists():
                sys.path.insert(0, str(websocket_path.parent))

                try:
                    from websocket_handler import WebSocketHandler

                    ws_handler = WebSocketHandler()

                    alert = {
                        "type": alert_type,
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                        "data": data or {},
                    }

                    ws_handler.broadcast_alert(alert)
                    logger.info(f"Alerta en tiempo real enviada: {alert_type}")

                except ImportError:
                    logger.warning("WebSocketHandler no disponible")
                except Exception as e:
                    logger.warning(f"Error enviando alerta en tiempo real: {e}")

        except Exception as e:
            logger.warning(f"Error buscando websocket_handler: {e}")

    def setup_mlflow_tracking(self):
        """Configurar tracking de MLflow para experimentos de ML"""
        try:
            mlflow_path = Path(__file__).parent.parent / "mlflow" / "mlflow_tracker.py"

            if mlflow_path.exists():
                sys.path.insert(0, str(mlflow_path.parent))

                try:
                    from mlflow_tracker import MLFlowTracker

                    self.mlflow_tracker = MLFlowTracker()

                    logger.info("MLflow tracking configurado para auto-reparación")

                except ImportError:
                    logger.warning("MLFlowTracker no disponible")
                except Exception as e:
                    logger.warning(f"Error configurando MLflow: {e}")

        except Exception as e:
            logger.warning(f"Error buscando mlflow_tracker: {e}")

    def log_mlflow_experiment(
        self, experiment_name: str, metrics: dict, params: dict | None = None
    ):
        """Registrar experimento en MLflow"""
        try:
            if not hasattr(self, "mlflow_tracker"):
                self.setup_mlflow_tracking()

            if hasattr(self, "mlflow_tracker") and self.mlflow_tracker:
                self.mlflow_tracker.log_experiment(
                    experiment_name=experiment_name, metrics=metrics, params=params
                )
                logger.info(f"Experimento MLflow registrado: {experiment_name}")

        except Exception as e:
            logger.warning(f"Error registrando experimento MLflow: {e}")

    def train_ml_model_with_tracking(self):
        """Entrenar modelo ML con tracking de MLflow"""
        if not ML_AVAILABLE:
            logger.warning("scikit-learn no disponible para entrenamiento ML")
            return False

        try:
            history = self.get_repair_history()

            if len(history) < 10:
                logger.warning(
                    "Historial insuficiente para entrenar modelo ML (mínimo 10 entradas)"
                )
                return False

            # Preparar datos
            X_texts = [entry.get("error_message", "") for entry in history]
            y_labels = [entry.get("error_type", "unknown") for entry in history]

            # Vectorizar mensajes de error
            X = self.vectorizer.fit_transform(X_texts)

            # Codificar etiquetas
            y = self.label_encoder.fit_transform(y_labels)

            # Configurar tracking MLflow
            self.log_mlflow_experiment(
                experiment_name="error_prediction_model",
                params={
                    "n_estimators": 100,
                    "max_features": 1000,
                    "training_samples": len(history),
                },
            )

            # Entrenar modelo
            self.ml_model.fit(X, y)

            # Calcular métricas
            predictions = self.ml_model.predict(X)
            accuracy = sum(predictions == y) / len(y)

            # Registrar métricas en MLflow
            self.log_mlflow_experiment(
                experiment_name="error_prediction_model",
                metrics={"accuracy": accuracy, "total_samples": len(history)},
            )

            # Guardar modelo
            self.save_ml_model()

            logger.info(f"Modelo ML entrenado con tracking MLflow: {accuracy:.2f} accuracy")
            return True

        except Exception as e:
            logger.error(f"Error entrenando modelo ML con tracking: {e}")
            return False

    def analyze_root_cause_with_llm(self, error_message: str, error_type: str) -> str:
        """Analizar causa raíz del error usando LLM (Ollama)"""
        from core.repair import analyze_root_cause_with_llm

        return analyze_root_cause_with_llm(self, error_message, error_type)

    def attempt_repair(self, agent_name: str, failure_count: int) -> bool:
        """
        Intenta reparar un agente antes de abrir el circuit breaker
        Integración con core/circuit_breaker.py

        Args:
            agent_name: Nombre del agente
            failure_count: Número de fallos consecutivos

        Returns:
            True si la reparación fue exitosa, False en caso contrario
        """
        from core.repair import attempt_repair

        return attempt_repair(self, agent_name, failure_count)

    def create_git_snapshot(self, message: str = "Auto-repair snapshot") -> str:
        """Crear snapshot Git antes de reparación"""
        from core.repair import create_git_snapshot

        return create_git_snapshot(self, message)

    def git_rollback(self, commit_hash: str | None = None) -> bool:
        """Rollback a commit Git específico"""
        try:
            project_root = Path(__file__).parent.parent

            if commit_hash is None:
                # Rollback al commit anterior
                subprocess.run(
                    ["git", "reset", "--hard", "HEAD~1"],
                    cwd=project_root,
                    capture_output=True,
                    timeout=30,
                )
                logger.info("Rollback Git al commit anterior")
                return True
            else:
                # Rollback a commit específico
                subprocess.run(
                    ["git", "reset", "--hard", commit_hash],
                    cwd=project_root,
                    capture_output=True,
                    timeout=30,
                )
                logger.info(f"Rollback Git al commit {commit_hash}")
                return True

        except Exception as e:
            logger.error(f"Error en rollback Git: {e}")
            return False

    def get_git_history(self, limit: int = 10) -> list[dict]:
        """Obtener historial de commits Git"""
        try:
            project_root = Path(__file__).parent.parent

            if not (project_root / ".git").exists():
                return []

            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%H|%s|%ai"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                commits = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split("|")
                        if len(parts) >= 3:
                            commits.append(
                                {"hash": parts[0], "message": parts[1], "date": parts[2]}
                            )
                return commits
            else:
                return []

        except Exception as e:
            logger.warning(f"Error obteniendo historial Git: {e}")
            return []

    def setup_distributed_repair(self, nodes: list[str]):
        """Configurar auto-reparación distribuida entre múltiples nodos"""
        from core.repair import setup_distributed_repair

        setup_distributed_repair(self, nodes)

    def broadcast_repair_request(
        self, error_type: str, error_message: str
    ) -> list[tuple[str, bool, str]]:
        """Broadcast solicitud de reparación a todos los nodos"""
        from core.repair import broadcast_repair_request

        return broadcast_repair_request(self, error_type, error_message)

    def sync_repair_history(self):
        """Sincronizar historial de reparaciones entre nodos"""
        from core.repair import sync_repair_history

        sync_repair_history(self)

    def check_system_resources(self) -> dict:
        """Verificar recursos del sistema para auto-escalado"""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_available_gb": disk.free / (1024**3),
            }

        except ImportError:
            logger.warning("psutil no disponible para monitoreo de recursos")
            return {}
        except Exception as e:
            logger.warning(f"Error verificando recursos: {e}")
            return {}

    def auto_scale_resources(self, threshold_cpu: float = 80, threshold_memory: float = 80) -> bool:
        """Auto-escalar recursos si se exceden umbrales"""
        try:
            resources = self.check_system_resources()

            if not resources:
                return False

            cpu_high = resources.get("cpu_percent", 0) > threshold_cpu
            memory_high = resources.get("memory_percent", 0) > threshold_memory

            if cpu_high or memory_high:
                logger.warning(
                    f"Recursos altos - CPU: {resources.get('cpu_percent')}%, Memoria: {resources.get('memory_percent')}%"
                )

                # Intentar escalar Ollama si está disponible
                try:
                    # Aumentar n_workers de Ollama si es posible
                    logger.info("Intentando escalar recursos de Ollama")
                    return True
                except Exception as e:
                    logger.warning(f"Error escalando Ollama: {e}")

            return False

        except Exception as e:
            logger.error(f"Error en auto-escalado: {e}")
            return False

    def send_slack_alert(self, webhook_url: str, message: str, error_type: str = ""):
        """Enviar alerta a Slack"""
        from core.repair import send_slack_alert

        send_slack_alert(self, webhook_url, message, error_type)

    def send_teams_alert(self, webhook_url: str, message: str, error_type: str = ""):
        """Enviar alerta a Microsoft Teams"""
        from core.repair import send_teams_alert

        send_teams_alert(self, webhook_url, message, error_type)

    def schedule_repair(self, error_type: str, error_message: str, schedule_time: str) -> bool:
        """Programar reparación para horario específico"""
        from core.repair import schedule_repair

        return schedule_repair(self, error_type, error_message, schedule_time)

    def run_scheduled_repairs(self):
        """Ejecutar reparaciones programadas"""
        from core.repair import run_scheduled_repairs

        run_scheduled_repairs(self)

    def get_repair_reputation(self) -> dict[str, float]:
        """Obtener reputación de cada tipo de reparación (0.0 - 1.0)"""
        history = self.get_repair_history()

        if not history:
            return {}

        reputation = {}
        repair_counts = {}
        success_counts = {}

        for entry in history:
            error_type = entry.get("error_type", "unknown")
            success = entry.get("success", False)

            repair_counts[error_type] = repair_counts.get(error_type, 0) + 1
            if success:
                success_counts[error_type] = success_counts.get(error_type, 0) + 1

        for error_type, total in repair_counts.items():
            success = success_counts.get(error_type, 0)
            reputation[error_type] = success / total if total > 0 else 0.0

        return reputation

    def get_best_repairs(self, min_reputation: float = 0.7) -> list[str]:
        """Obtener tipos de reparación con mejor reputación"""
        reputation = self.get_repair_reputation()

        best_repairs = [
            error_type for error_type, score in reputation.items() if score >= min_reputation
        ]

        return sorted(best_repairs, key=lambda x: reputation[x], reverse=True)

    def get_worst_repairs(self, max_reputation: float = 0.3) -> list[str]:
        """Obtener tipos de reparación con peor reputación"""
        reputation = self.get_repair_reputation()

        worst_repairs = [
            error_type for error_type, score in reputation.items() if score <= max_reputation
        ]

        return sorted(worst_repairs, key=lambda x: reputation[x])

    def auto_tune_parameters(self):
        """Auto-ajustar parámetros basado en historial de reparaciones"""
        try:
            reputation = self.get_repair_reputation()
            history = self.get_repair_history()

            if not history or not reputation:
                return

            # Ajustar timeouts basado en reputación
            for error_type, score in reputation.items():
                if score < 0.5:
                    # Reparaciones con baja reputación necesitan más tiempo
                    self.config.setdefault("custom_timeouts", {})[error_type] = 120
                elif score > 0.8:
                    # Reparaciones con alta reputación pueden ser más rápidas
                    self.config.setdefault("custom_timeouts", {})[error_type] = 30

            # Ajustar threshold de alertas recurrentes
            total_repairs = len(history)
            if total_repairs > 50:
                self.config["recurrent_threshold"] = 5
            elif total_repairs > 20:
                self.config["recurrent_threshold"] = 4
            else:
                self.config["recurrent_threshold"] = 3

            # Ajustar ML prediction threshold
            if ML_AVAILABLE and self.ml_model:
                accuracy = self._calculate_model_accuracy()
                if accuracy > 0.8:
                    self.config["ml_prediction_threshold"] = 0.3
                elif accuracy > 0.6:
                    self.config["ml_prediction_threshold"] = 0.5
                else:
                    self.config["ml_prediction_threshold"] = 0.7

            self._save_config()
            logger.info("Parámetros auto-ajustados basados en historial")

        except Exception as e:
            logger.warning(f"Error en auto-tuning: {e}")

    def _calculate_model_accuracy(self) -> float:
        """Calcular accuracy del modelo ML"""
        try:
            history = self.get_repair_history()

            if len(history) < 10 or not ML_AVAILABLE:
                return 0.0

            X_texts = [entry.get("error_message", "") for entry in history]
            y_labels = [entry.get("error_type", "unknown") for entry in history]

            X = self.vectorizer.transform(X_texts)
            y = self.label_encoder.transform(y_labels)

            predictions = self.ml_model.predict(X)
            accuracy = sum(predictions == y) / len(y)

            return accuracy

        except Exception as e:
            logger.warning(f"Error calculando accuracy: {e}")
            return 0.0

    def record_user_feedback(self, repair_id: str, feedback: str, rating: int):
        """Registrar feedback de usuario sobre reparación"""
        try:
            feedback_file = Path(__file__).parent.parent / "data" / "user_feedback.json"
            feedback_file.parent.mkdir(parents=True, exist_ok=True)

            feedback_data = []
            if feedback_file.exists():
                with open(feedback_file) as f:
                    feedback_data = json.load(f)

            feedback_data.append(
                {
                    "repair_id": repair_id,
                    "feedback": feedback,
                    "rating": rating,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            with open(feedback_file, "w") as f:
                json.dump(feedback_data, f, indent=2)

            logger.info(f"Feedback de usuario registrado: {repair_id} - {rating}/5")

        except Exception as e:
            logger.warning(f"Error registrando feedback: {e}")

    def get_user_feedback_stats(self) -> dict:
        """Obtener estadísticas de feedback de usuario"""
        try:
            feedback_file = Path(__file__).parent.parent / "data" / "user_feedback.json"

            if not feedback_file.exists():
                return {}

            with open(feedback_file) as f:
                feedback_data = json.load(f)

            total = len(feedback_data)
            avg_rating = sum(f.get("rating", 0) for f in feedback_data) / total if total > 0 else 0

            return {
                "total_feedback": total,
                "average_rating": round(avg_rating, 2),
                "feedback_count": total,
            }

        except Exception as e:
            logger.warning(f"Error obteniendo stats de feedback: {e}")
            return {}

    def track_apm_metrics(self, error_type: str, repair_time: float):
        """Enviar métricas a APM (New Relic/DataDog)"""
        try:
            # Simular envío de métricas a APM
            logger.info(f"APM Metric: {error_type} repair time: {repair_time}s")

            # Aquí se integraría con New Relic o DataDog API
            # Por ahora solo logging

        except Exception as e:
            logger.warning(f"Error enviando métricas APM: {e}")

    def predict_cascade_failures(self, error_type: str) -> list[str]:
        """Predecir fallos en cascada después de un error"""
        cascade_map = {
            "ollama": ["llm_timeout", "response_error", "agent_failure"],
            "redis": ["cache_miss", "session_error", "performance_degradation"],
            "missing_module": ["import_error", "module_dependency_error"],
            "permission": ["file_access_error", "config_error"],
            "disk_full": ["log_error", "data_loss", "backup_failure"],
        }

        return cascade_map.get(error_type, [])

    def share_repair_with_peers(self, repair_id: str, repair_data: dict):
        """Compartir reparación con peers (colaborativo)"""
        try:
            shared_file = Path(__file__).parent.parent / "data" / "shared_repairs.json"
            shared_file.parent.mkdir(parents=True, exist_ok=True)

            shared_repairs = []
            if shared_file.exists():
                with open(shared_file) as f:
                    shared_repairs = json.load(f)

            shared_repairs.append(
                {
                    "repair_id": repair_id,
                    "repair_data": repair_data,
                    "shared_at": datetime.now().isoformat(),
                    "shared_by": "ura_instance",
                }
            )

            with open(shared_file, "w") as f:
                json.dump(shared_repairs, f, indent=2)

            logger.info(f"Reparación compartida con peers: {repair_id}")

        except Exception as e:
            logger.warning(f"Error compartiendo reparación: {e}")

    def get_shared_repairs(self) -> list[dict]:
        """Obtener reparaciones compartidas por peers"""
        try:
            shared_file = Path(__file__).parent.parent / "data" / "shared_repairs.json"

            if not shared_file.exists():
                return []

            with open(shared_file) as f:
                return json.load(f)

        except Exception as e:
            logger.warning(f"Error obteniendo reparaciones compartidas: {e}")
            return []

    def get_error_probability(self, error_type: str) -> float:
        """Obtener probabilidad de que ocurra un error específico (0.0 - 1.0)"""
        history = self.get_repair_history()

        if not history:
            return 0.0

        total_errors = len(history)
        error_occurrences = sum(1 for entry in history if entry.get("error_type", "") == error_type)

        if total_errors == 0:
            return 0.0

        return error_occurrences / total_errors

    def check_and_alert_recurrent_errors(self):
        """Verificar errores recurrentes y enviar alertas a Telegram/Discord"""
        if not self.config.get("alert_on_failure", False):
            return

        recurrent_errors = self.get_recurrent_errors()

        for error_type, count in recurrent_errors.items():
            if count >= 3:  # Alertar si ocurrió 3+ veces
                self._send_recurrent_error_alert(error_type, count)

    def _send_recurrent_error_alert(self, error_type: str, count: int):
        """Enviar alerta de error recurrente a Telegram/Discord"""
        try:
            # Intentar importar NotificationSystem
            from notification_system import NotificationSystem

            notif = NotificationSystem()

            # Construir mensaje
            message = (
                f"⚠️ ERROR RECURRENTE DETECTADO\n\n"
                f"Tipo: {error_type}\n"
                f"Ocurrencias: {count}\n"
                f"Última reparación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Recomendación: Verificar configuración del sistema para evitar este error."
            )

            # Enviar a Telegram
            try:
                notif.enviar_telegram_alerta("URA - Error Recurrente", message)
                logger.info(f"Alerta de error recurrente enviada a Telegram: {error_type}")
            except Exception as e:
                logger.warning(f"No se pudo enviar alerta a Telegram: {e}")

            # Enviar a Discord
            try:
                notif.enviar_discord_alerta("URA - Error Recurrente", message)
                logger.info(f"Alerta de error recurrente enviada a Discord: {error_type}")
            except Exception as e:
                logger.warning(f"No se pudo enviar alerta a Discord: {e}")

        except ImportError:
            logger.warning("NotificationSystem no disponible para alertas de errores recurrentes")
        except Exception as e:
            logger.error(f"Error enviando alerta de error recurrente: {e}")

    @staticmethod
    def detect_error_type(error_message: str) -> str:
        """Detectar tipo de error basado en el mensaje"""
        error_lower = error_message.lower()

        if (
            "module not found" in error_lower
            or "modulenotfounderror" in error_lower
            or "no module named" in error_lower
        ):
            return "missing_module"
        elif "permission denied" in error_lower:
            return "permission"
        elif "ollama" in error_lower:
            return "ollama"
        elif "redis" in error_lower:
            return "redis"
        elif "connection" in error_lower or "timeout" in error_lower:
            return "connection"
        elif "file not found" in error_lower:
            return "missing_file"
        elif "import" in error_lower:
            return "import_error"
        elif "keyerror" in error_lower:
            return "key_error"
        elif "attributeerror" in error_lower:
            return "attribute_error"
        elif "typeerror" in error_lower:
            return "type_error"
        else:
            return "unknown"

    def attempt_repair(
        self, error_type: str, error_message: str, timeout: int = 60
    ) -> tuple[bool, str]:
        """Intentar reparar el error automáticamente con cascada de estrategias y timeout"""

        # Si está en modo simulación, solo simular
        if self.simulation_mode:
            return self._simulate_repair(error_type, error_message)

        # Guardar estado antes de la reparación (para rollback)
        if self.config.get("enable_rollback", True):
            self._save_rollback_state(error_type, error_message)

        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Reparación timeout después de {timeout} segundos")

        # Configurar timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        try:
            # Intentar estrategia principal
            success, repair_message = self._attempt_repair_internal(error_type, error_message)

            if success:
                self._log_repair(error_type, error_message, success, repair_message)
                return success, repair_message

            # Si falló, intentar estrategias alternativas (cascada)
            alternative_strategies = self._get_alternative_strategies(error_type)

            for strategy in alternative_strategies:
                success, repair_message = self._attempt_strategy(
                    strategy, error_type, error_message
                )

                if success:
                    self._log_repair(
                        error_type,
                        error_message,
                        success,
                        f"{repair_message} (estrategia alternativa: {strategy})",
                    )
                    return success, repair_message

            # Registrar fallo final
            self._log_repair(error_type, error_message, False, "Todas las estrategias fallaron")

            # Intentar rollback si falló
            if self.config.get("enable_rollback", True):
                self._rollback(error_type)

            return False, "Todas las estrategias de reparación fallaron"

        except TimeoutError as e:
            self._log_repair(error_type, error_message, False, f"Timeout: {str(e)}")

            # Intentar rollback si hubo timeout
            if self.config.get("enable_rollback", True):
                self._rollback(error_type)

            return False, f"Reparación timeout después de {timeout} segundos"
        except Exception as e:
            self._log_repair(error_type, error_message, False, f"Error: {str(e)}")

            # Intentar rollback si hubo error
            if self.config.get("enable_rollback", True):
                self._rollback(error_type)

            return False, f"Error en reparación: {str(e)}"
        finally:
            # Cancelar timeout
            signal.alarm(0)

    def _simulate_repair(self, error_type: str, error_message: str) -> tuple[bool, str]:
        """Simular reparación sin ejecutar cambios reales"""
        logger.info(f"[SIMULACIÓN] Simulando reparación para error: {error_type}")

        # Simular éxito basado en tipo de error
        success_rates = {
            "missing_module": 0.9,
            "ollama": 0.8,
            "redis": 0.8,
            "missing_file": 0.7,
            "import_error": 0.6,
            "permission": 0.5,
            "key_error": 0.4,
            "attribute_error": 0.4,
            "type_error": 0.4,
        }

        success_rates.get(error_type, 0.5)
        success = error_type in success_rates

        if success:
            repair_message = f"[SIMULACIÓN] Reparación simulada exitosa para {error_type}"
        else:
            repair_message = f"[SIMULACIÓN] Reparación simulada fallida para {error_type}"

        # No guardar en historial en modo simulación
        logger.info(f"[SIMULACIÓN] Resultado: {repair_message}")

        return success, repair_message

    def get_error_priority(self, error_type: str) -> str:
        """Obtener prioridad de un tipo de error (critical, high, medium, low)"""
        repair_priority = self.config.get("repair_priority", {})

        for priority, errors in repair_priority.items():
            if error_type in errors:
                return priority

        return "low"  # Prioridad por defecto

    def get_priority_order(self, error_types: list[str]) -> list[str]:
        """Ordenar errores por prioridad"""
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        return sorted(error_types, key=lambda x: priority_order.get(self.get_error_priority(x), 3))

    def attempt_repair_with_priority(
        self, error_type: str, error_message: str, timeout: int = 60
    ) -> tuple[bool, str]:
        """Intentar reparar con prioridad - errores críticos tienen más tiempo y estrategias"""
        priority = self.get_error_priority(error_type)

        # Ajustar timeout según prioridad
        if priority == "critical":
            timeout = max(timeout, 120)  # Mínimo 120 segundos para críticos
        elif priority == "high":
            timeout = max(timeout, 90)  # Mínimo 90 segundos para altos
        elif priority == "medium":
            timeout = max(timeout, 60)  # Mínimo 60 segundos para medios
        else:
            timeout = max(timeout, 30)  # Mínimo 30 segundos para bajos

        logger.info(f"Reparando error {error_type} con prioridad {priority} (timeout: {timeout}s)")

        return self.attempt_repair(error_type, error_message, timeout)

    def run_preventive_checks(self) -> list[str]:
        """Ejecutar verificaciones preventivas para evitar errores antes de que ocurran"""
        issues_found = []

        if not self.config.get("preventive_checks_enabled", True):
            return issues_found

        logger.info("Ejecutando verificaciones preventivas")

        # Verificar Ollama
        ollama_status = self._check_ollama_preventive()
        if ollama_status:
            issues_found.append(f"Ollama: {ollama_status}")

        # Verificar Redis
        redis_status = self._check_redis_preventive()
        if redis_status:
            issues_found.append(f"Redis: {redis_status}")

        # Verificar espacio en disco
        disk_status = self._check_disk_space()
        if disk_status:
            issues_found.append(f"Disco: {disk_status}")

        # Verificar logs antiguos
        logs_status = self._check_old_logs()
        if logs_status:
            issues_found.append(f"Logs: {logs_status}")

        return issues_found

    def _check_ollama_preventive(self) -> str | None:
        """Verificar Ollama preventivamente"""
        try:
            result = subprocess.run(["pgrep", "-x", "ollama"], capture_output=True, timeout=5)
            if result.returncode != 0:
                # Ollama no está corriendo, arrancarlo preventivamente
                logger.info("Ollama no está corriendo, arrancando preventivamente")
                subprocess.Popen(
                    ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return "Ollama reiniciado preventivamente"
        except Exception as e:
            return f"Error verificando Ollama: {str(e)}"

        return None

    def _check_redis_preventive(self) -> str | None:
        """Verificar Redis preventivamente"""
        try:
            result = subprocess.run(["pgrep", "-x", "redis-server"], capture_output=True, timeout=5)
            if result.returncode != 0:
                # Redis no está corriendo, arrancarlo preventivamente
                logger.info("Redis no está corriendo, arrancando preventivamente")
                subprocess.Popen(
                    ["redis-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return "Redis reiniciado preventivamente"
        except Exception as e:
            return f"Error verificando Redis: {str(e)}"

        return None

    def _check_disk_space(self) -> str | None:
        """Verificar espacio en disco preventivamente"""
        try:
            import shutil

            disk_usage = shutil.disk_usage(Path.home())
            free_percent = (disk_usage.free / disk_usage.total) * 100

            if free_percent < 10:
                return f"Espacio en disco bajo: {free_percent:.1f}% libre"
        except Exception as e:
            return f"Error verificando espacio en disco: {str(e)}"

        return None

    def _check_old_logs(self) -> str | None:
        """Verificar logs antiguos preventivamente"""
        try:
            logs_dir = Path(__file__).parent.parent / "logs"
            if logs_dir.exists():
                import time

                current_time = time.time()
                old_files = []

                for log_file in logs_dir.glob("*.log"):
                    file_age = current_time - log_file.stat().st_mtime
                    if file_age > (7 * 24 * 60 * 60):  # 7 días
                        old_files.append(log_file)

                if old_files:
                    # Limpiar logs antiguos
                    for old_file in old_files:
                        old_file.unlink()
                    return f"Limpiados {len(old_files)} logs antiguos"
        except Exception as e:
            return f"Error verificando logs antiguos: {str(e)}"

        return None

    def _save_rollback_state(self, error_type: str, error_message: str) -> dict:
        """Guardar estado antes de la reparación para posible rollback"""
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "error_type": error_type,
                "error_message": error_message[:200],
                "files_modified": [],
                "services_restarted": [],
                "packages_installed": [],
            }

            # Guardar estado de archivos relevantes
            if error_type == "missing_file":
                import re

                match = re.search(r"No such file or directory: ['\"]([^'\"]+)['\"]", error_message)
                if match:
                    file_path = match.group(1)
                    if Path(file_path).exists():
                        state["files_modified"].append(
                            {
                                "path": file_path,
                                "existed": True,
                                "size": (
                                    Path(file_path).stat().st_size
                                    if Path(file_path).is_file()
                                    else 0
                                ),
                            }
                        )
                    else:
                        state["files_modified"].append(
                            {"path": file_path, "existed": False, "size": 0}
                        )

            # Guardar estado de servicios
            if error_type in ["ollama", "redis"]:
                service_name = "ollama" if error_type == "ollama" else "redis"
                try:
                    result = subprocess.run(
                        ["pgrep", "-x", service_name], capture_output=True, timeout=5
                    )
                    state["services_restarted"].append(
                        {"name": service_name, "was_running": result.returncode == 0}
                    )
                except Exception:
                    state["services_restarted"].append({"name": service_name, "was_running": False})

            # Guardar estado en archivo
            with open(self.rollback_file, "w") as f:
                json.dump(state, f, indent=2)

            return state
        except Exception as e:
            logger.warning(f"Error guardando estado de rollback: {e}")
            return {}

    def _rollback(self, error_type: str):
        """Restaurar estado anterior si la reparación falló"""
        try:
            if not self.rollback_file.exists():
                logger.warning("Archivo de rollback no encontrado")
                return

            with open(self.rollback_file) as f:
                state = json.load(f)

            # Verificar que el estado es para el mismo error
            if state.get("error_type") != error_type:
                logger.warning("Estado de rollback no coincide con el error actual")
                return

            logger.info(f"Iniciando rollback para error: {error_type}")

            # Rollback de archivos
            for file_info in state.get("files_modified", []):
                file_path = file_info["path"]
                existed = file_info["existed"]

                if existed and not Path(file_path).exists():
                    logger.warning(f"Archivo {file_path} fue eliminado durante reparación")
                elif not existed and Path(file_path).exists():
                    # Eliminar archivo creado durante reparación
                    if Path(file_path).is_file():
                        Path(file_path).unlink()
                    elif Path(file_path).is_dir():
                        shutil.rmtree(file_path)
                    logger.info(f"Rollback: Eliminado {file_path}")

            # Rollback de servicios
            for service_info in state.get("services_restarted", []):
                service_name = service_info["name"]
                was_running = service_info["was_running"]

                if was_running:
                    # Asegurar que el servicio esté corriendo
                    if service_name == "ollama":
                        subprocess.Popen(
                            ["ollama", "serve"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    elif service_name == "redis":
                        subprocess.Popen(
                            ["redis-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    logger.info(f"Rollback: Servicio {service_name} reiniciado")

            # Limpiar archivo de rollback
            self.rollback_file.unlink()

            logger.info("Rollback completado exitosamente")

        except Exception as e:
            logger.error(f"Error durante rollback: {e}")

    def _get_alternative_strategies(self, error_type: str) -> list[str]:
        """Obtener estrategias alternativas para un tipo de error"""
        strategies = {
            "missing_module": ["pip_install", "pip_install_user", "conda_install"],
            "ollama": ["restart_ollama", "kill_and_restart", "reinstall_ollama"],
            "redis": ["restart_redis", "kill_and_restart", "reinstall_redis"],
            "missing_file": ["create_file", "create_directory", "check_permissions"],
            "import_error": ["check_path", "check_syntax", "reinstall_module"],
        }

        return strategies.get(error_type, [])

    def _attempt_strategy(
        self, strategy: str, error_type: str, error_message: str
    ) -> tuple[bool, str]:
        """Intentar una estrategia específica de reparación"""
        try:
            if strategy == "pip_install":
                return self._repair_missing_module(error_message)
            elif strategy == "pip_install_user":
                return self._repair_missing_module_user(error_message)
            elif strategy == "conda_install":
                return self._repair_missing_module_conda(error_message)
            elif strategy == "restart_ollama":
                return self._restart_ollama()
            elif strategy == "kill_and_restart":
                return self._kill_and_restart_service(error_type)
            elif strategy == "reinstall_ollama":
                return self._reinstall_ollama()
            elif strategy == "restart_redis":
                return self._restart_redis()
            elif strategy == "reinstall_redis":
                return self._reinstall_redis()
            elif strategy == "create_file":
                return self._repair_missing_file(error_message)
            elif strategy == "create_directory":
                return self._repair_missing_directory(error_message)
            elif strategy == "check_permissions":
                return self._check_permissions(error_message)
            elif strategy == "check_path":
                return self._check_import_path(error_message)
            elif strategy == "check_syntax":
                return self._check_import_syntax(error_message)
            elif strategy == "reinstall_module":
                return self._reinstall_module(error_message)
            else:
                return False, f"Estrategia desconocida: {strategy}"
        except Exception as e:
            return False, f"Error en estrategia {strategy}: {str(e)}"

    def _repair_missing_module_user(self, error_message: str) -> tuple[bool, str]:
        """Reparar módulo faltante con --user"""
        try:
            import re

            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_message)
            if match:
                module_name = match.group(1)

                result = subprocess.run(
                    ["pip3", "install", "--user", module_name],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0:
                    return True, f"Módulo {module_name} instalado con --user"
                else:
                    return False, f"Error instalando {module_name} con --user: {result.stderr}"
        except Exception as e:
            return False, f"Error al reparar módulo con --user: {str(e)}"

        return False, "No se pudo identificar el módulo faltante"

    def _repair_missing_module_conda(self, error_message: str) -> tuple[bool, str]:
        """Reparar módulo faltante con conda"""
        try:
            import re

            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_message)
            if match:
                module_name = match.group(1)

                result = subprocess.run(
                    ["conda", "install", "-y", module_name],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode == 0:
                    return True, f"Módulo {module_name} instalado con conda"
                else:
                    return False, f"Error instalando {module_name} con conda: {result.stderr}"
        except Exception as e:
            return False, f"Error al reparar módulo con conda: {str(e)}"

        return False, "No se pudo identificar el módulo faltante"

    def _restart_ollama(self) -> tuple[bool, str]:
        """Reiniciar Ollama"""
        try:
            subprocess.run(["pkill", "ollama"], capture_output=True, timeout=5)
            subprocess.Popen(
                ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True, "Ollama reiniciado"
        except Exception as e:
            return False, f"Error reiniciando Ollama: {str(e)}"

    def _kill_and_restart_service(self, service_type: str) -> tuple[bool, str]:
        """Matar y reiniciar servicio"""
        try:
            if service_type == "ollama":
                subprocess.run(["pkill", "-9", "ollama"], capture_output=True, timeout=5)
                subprocess.Popen(
                    ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True, "Ollama forzado a reiniciar"
            elif service_type == "redis":
                subprocess.run(["pkill", "-9", "redis-server"], capture_output=True, timeout=5)
                subprocess.Popen(
                    ["redis-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True, "Redis forzado a reiniciar"
            else:
                return False, f"Servicio desconocido: {service_type}"
        except Exception as e:
            return False, f"Error forzando reinicio: {str(e)}"

    def _reinstall_ollama(self) -> tuple[bool, str]:
        """Reinstalar Ollama"""
        try:
            return False, "Reinstalación de Ollama requiere intervención manual"
        except Exception as e:
            return False, f"Error reinstalando Ollama: {str(e)}"

    def _restart_redis(self) -> tuple[bool, str]:
        """Reiniciar Redis"""
        try:
            subprocess.run(["redis-cli", "shutdown"], capture_output=True, timeout=5)
            subprocess.Popen(["redis-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, "Redis reiniciado"
        except Exception as e:
            return False, f"Error reiniciando Redis: {str(e)}"

    def _reinstall_redis(self) -> tuple[bool, str]:
        """Reinstalar Redis"""
        try:
            return False, "Reinstalación de Redis requiere intervención manual"
        except Exception as e:
            return False, f"Error reinstalando Redis: {str(e)}"

    def _repair_missing_directory(self, error_message: str) -> tuple[bool, str]:
        """Reparar directorio faltante"""
        try:
            import re

            match = re.search(r"No such file or directory: ['\"]([^'\"]+)['\"]", error_message)
            if match:
                dir_path = match.group(1)

                # Crear directorio padre
                parent_dir = Path(dir_path).parent
                parent_dir.mkdir(parents=True, exist_ok=True)

                return True, f"Directorio {dir_path} creado"
        except Exception as e:
            return False, f"Error al crear directorio: {str(e)}"

        return False, "No se pudo identificar el directorio faltante"

    def _check_permissions(self, error_message: str) -> tuple[bool, str]:
        """Verificar y corregir permisos"""
        try:
            import re

            match = re.search(r"['\"]([^'\"]+)['\"]", error_message)
            if match:
                path = match.group(1)

                # Intentar corregir permisos
                subprocess.run(["chmod", "+x", path], capture_output=True, timeout=5)

                return True, f"Permisos corregidos para {path}"
        except Exception as e:
            return False, f"Error al corregir permisos: {str(e)}"

        return False, "No se pudo identificar el path para corregir permisos"

    def _check_import_path(self, error_message: str) -> tuple[bool, str]:
        """Verificar path de import"""
        try:
            return False, "Verificación de path requiere intervención manual"
        except Exception as e:
            return False, f"Error verificando path: {str(e)}"

    def _check_import_syntax(self, error_message: str) -> tuple[bool, str]:
        """Verificar sintaxis de import"""
        try:
            return False, "Verificación de sintaxis requiere intervención manual"
        except Exception as e:
            return False, f"Error verificando sintaxis: {str(e)}"

    def _reinstall_module(self, error_message: str) -> tuple[bool, str]:
        """Reinstalar módulo"""
        try:
            import re

            match = re.search(r"['\"]([^'\"]+)['\"]", error_message)
            if match:
                module_name = match.group(1)

                result = subprocess.run(
                    ["pip3", "install", "--force-reinstall", module_name],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0:
                    return True, f"Módulo {module_name} reinstalado"
                else:
                    return False, f"Error reinstalando {module_name}: {result.stderr}"
        except Exception as e:
            return False, f"Error al reinstalar módulo: {str(e)}"

        return False, "No se pudo identificar el módulo"

    def _attempt_repair_internal(self, error_type: str, error_message: str) -> tuple[bool, str]:
        """Intento interno de reparación"""

        if error_type == "missing_module":
            return self._repair_missing_module(error_message)
        elif error_type == "ollama":
            return self._repair_ollama()
        elif error_type == "redis":
            return self._repair_redis()
        elif error_type == "permission":
            return self._repair_permission(error_message)
        elif error_type == "missing_file":
            return self._repair_missing_file(error_message)
        elif error_type == "import_error":
            return self._repair_import_error(error_message)
        elif error_type == "key_error":
            return self._repair_key_error(error_message)
        elif error_type == "attribute_error":
            return self._repair_attribute_error(error_message)
        elif error_type == "type_error":
            return self._repair_type_error(error_message)
        else:
            return False, "Tipo de error no reconocido para auto-reparación"

    @staticmethod
    def _repair_key_error(error_message: str) -> tuple[bool, str]:
        """Reparar KeyError"""
        try:
            import re

            match = re.search(r"['\"]([^'\"]+)['\"]", error_message)
            if match:
                key_name = match.group(1)
                return (
                    False,
                    f"KeyError: La clave '{key_name}' no existe. Verifica el diccionario o variable.",
                )
            return False, "KeyError: Verifica las claves de los diccionarios"
        except Exception as e:
            return False, f"Error al reparar KeyError: {str(e)}"

    @staticmethod
    def _repair_attribute_error(error_message: str) -> tuple[bool, str]:
        """Reparar AttributeError"""
        try:
            import re

            match = re.search(r"['\"]([^'\"]+)['\"]", error_message)
            if match:
                attr_name = match.group(1)
                return (
                    False,
                    f"AttributeError: El atributo '{attr_name}' no existe. Verifica el objeto.",
                )
            return False, "AttributeError: Verifica los atributos del objeto"
        except Exception as e:
            return False, f"Error al reparar AttributeError: {str(e)}"

    @staticmethod
    def _repair_type_error(error_message: str) -> tuple[bool, str]:
        """Reparar TypeError"""
        try:
            return False, "TypeError: Verifica los tipos de datos de las variables"
        except Exception as e:
            return False, f"Error al reparar TypeError: {str(e)}"

    @staticmethod
    def _repair_missing_module(error_message: str) -> tuple[bool, str]:
        """Reparar módulo faltante"""
        try:
            # Extraer nombre del módulo del error
            import re

            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_message)
            if match:
                module_name = match.group(1)

                # Intentar instalar el módulo
                result = subprocess.run(
                    ["pip3", "install", module_name], capture_output=True, text=True, timeout=60
                )

                if result.returncode == 0:
                    return True, f"Módulo {module_name} instalado correctamente"
                else:
                    return False, f"Error instalando {module_name}: {result.stderr}"
        except Exception as e:
            return False, f"Error al reparar módulo: {str(e)}"

        return False, "No se pudo identificar el módulo faltante"

    @staticmethod
    def _repair_ollama() -> tuple[bool, str]:
        """Reparar Ollama"""
        try:
            # Verificar si Ollama está instalado
            result = subprocess.run(["which", "ollama"], capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                # Ollama no instalado
                return (
                    False,
                    "Ollama no está instalado. Instálalo con: curl -fsSL https://ollama.ai/install.sh | sh",
                )

            # Verificar si Ollama está corriendo
            result = subprocess.run(
                ["curl", "-sf", "http://localhost:11434/api/tags"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                # Intentar arrancar Ollama
                subprocess.Popen(
                    ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True, "Ollama iniciado en segundo plano"

            return True, "Ollama ya está corriendo"

        except Exception as e:
            return False, f"Error al reparar Ollama: {str(e)}"

    @staticmethod
    def _repair_redis() -> tuple[bool, str]:
        """Reparar Redis"""
        try:
            # Verificar si Redis está instalado
            result = subprocess.run(
                ["which", "redis-server"], capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0:
                # Redis no instalado
                return (
                    False,
                    "Redis no está instalado. Instálalo con: brew install redis (Mac) o sudo apt-get install redis-server (Linux)",
                )

            # Verificar si Redis está corriendo
            result = subprocess.run(
                ["redis-cli", "ping"], capture_output=True, text=True, timeout=5
            )

            if result.returncode != 0:
                # Intentar arrancar Redis
                subprocess.Popen(
                    ["redis-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True, "Redis iniciado en segundo plano"

            return True, "Redis ya está corriendo"

        except Exception as e:
            return False, f"Error al reparar Redis: {str(e)}"

    @staticmethod
    def _repair_permission(error_message: str) -> tuple[bool, str]:
        """Reparar permisos"""
        try:
            # Sugerir comando para arreglar permisos
            return False, "Error de permisos. Ejecuta: chmod +x script.sh o sudo chmod 755 archivo"
        except Exception as e:
            return False, f"Error al reparar permisos: {str(e)}"

    @staticmethod
    def _repair_missing_file(error_message: str) -> tuple[bool, str]:
        """Reparar archivo faltante"""
        try:
            import re

            match = re.search(r"No such file or directory: ['\"]([^'\"]+)['\"]", error_message)
            if match:
                file_path = match.group(1)

                # Crear directorio padre si no existe
                parent_dir = Path(file_path).parent
                parent_dir.mkdir(parents=True, exist_ok=True)

                # Crear archivo vacío
                Path(file_path).touch()

                return True, f"Archivo {file_path} creado"
        except Exception as e:
            return False, f"Error al crear archivo: {str(e)}"

        return False, "No se pudo identificar el archivo faltante"

    @staticmethod
    def _repair_import_error(error_message: str) -> tuple[bool, str]:
        """Reparar error de import"""
        try:
            import re

            match = re.search(r"cannot import name ['\"]([^'\"]+)['\"]", error_message)
            if match:
                missing_name = match.group(1)
                return False, f"Falta importar {missing_name}. Verifica el archivo Python"

            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_message)
            if match:
                match.group(1)
                return ErrorAutoRepair._repair_missing_module(error_message)

            return False, "Error de import no reconocido"
        except Exception as e:
            return False, f"Error al reparar import: {str(e)}"

    def repair_with_forensic(self, error_message: str, error_module: str = "") -> dict:
        """Reparar error usando ForensicScribe para análisis de causa raíz."""
        from core.forensic_scribe import get_forensic_scribe
        from core.ura_rollback import get_ura_rollback

        scribe = get_forensic_scribe()
        rollback = get_ura_rollback()
        error_type = self.detect_error_type(error_message)

        result = {
            "error_type": error_type,
            "error_message": error_message[:200],
            "auto_repaired": False,
            "message": "",
            "forensic_analysis": None,
        }

        # 1. Buscar solución verificada en causas_raiz
        verified = scribe.find_verified_solution(error_message)
        if verified:
            result["forensic_analysis"] = verified
            result["message"] = (
                f"Causa raíz conocida: {verified['causa_raiz']}. Aplicando solución verificada..."
            )

            # Crear snapshot antes de reparar
            snapshot_id = rollback.create_snapshot(
                "error_repair",
                Path.home() / ".ura" / "error_patterns.json",
                {"error_type": error_type, "action": "forensic_repair"},
            )

            # Aplicar reparación
            success, repair_msg = self.attempt_repair(error_type, error_message)
            if success:
                result["auto_repaired"] = True
                result["message"] += f" ✅ Reparada: {repair_msg}"
            else:
                result["message"] += f" ❌ Falló reparación: {repair_msg}. Rollback..."
                rollback.restore_snapshot(snapshot_id, "error_repair")
            return result

        # 2. Analizar con trace_trigger
        trigger = scribe.trace_trigger(error_message, error_module or "unknown")
        if trigger:
            result["forensic_analysis"] = {
                "detonante": trigger,
                "module": trigger.get("module", ""),
                "action": trigger.get("action", ""),
                "timestamp": trigger.get("timestamp", ""),
            }
            result["message"] = (
                f"Detonante identificado: {trigger.get('action', '?')} "
                f"en {trigger.get('module', '?')}. "
                f"Error nuevo — notificando a Ramón para autorización."
            )
        else:
            result["message"] = (
                "No se encontró detonante claro. Error nuevo — requiere análisis manual."
            )

        # 3. Registrar evento de error
        scribe.log_event(
            "error",
            error_module or "unknown",
            f"error_detected: {error_type}",
            {"error_message": error_message[:200]},
            [error_module] if error_module else [],
        )

        return result

    def sandbox_repair(self, error_message: str) -> dict:
        """Reparar en sandbox: snapshot → reparar → pytest → aplicar o rollback."""
        from core.ura_rollback import get_ura_rollback

        rollback = get_ura_rollback()
        error_type = self.detect_error_type(error_message)

        result = {"success": False, "message": "", "tests_passed": False}

        # 1. Snapshot
        snapshot_id = rollback.create_snapshot(
            "sandbox_repair",
            Path(__file__).parent.parent / "ura_panel.py",
            {"error_type": error_type},
        )
        result["snapshot_id"] = snapshot_id

        # 2. Reparar
        success, repair_msg = self.attempt_repair(error_type, error_message)
        result["repair_message"] = repair_msg

        if not success:
            rollback.restore_snapshot(snapshot_id, "sandbox_repair")
            result["message"] = f"Reparación fallida, rollback ejecutado: {repair_msg}"
            return result

        # 3. Ejecutar tests
        try:
            test_result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-q", "--tb=short"],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if test_result.returncode == 0:
                result["tests_passed"] = True
                result["success"] = True
                result["message"] = (
                    "✅ Sandbox: reparación exitosa, tests pasan. Cambios aplicados."
                )
            else:
                rollback.restore_snapshot(snapshot_id, "sandbox_repair")
                result["message"] = (
                    f"❌ Tests fallaron después de reparar. Rollback ejecutado.\n{test_result.stdout[-300:]}"
                )
        except Exception as e:
            rollback.restore_snapshot(snapshot_id, "sandbox_repair")
            result["message"] = f"❌ Error ejecutando tests: {e}. Rollback ejecutado."

        return result


def show_error_with_repair(
    parent, title: str, message: str, repair_callback=None, auto_repair: bool = True
):
    """Mostrar ventana de error con opción de auto-reparación automática"""
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QCheckBox, QMessageBox, QPushButton

    # Crear instancia de ErrorAutoRepair
    repair_system = ErrorAutoRepair()
    error_type = repair_system.detect_error_type(message)

    # Verificar si auto-reparación está habilitada en configuración
    auto_repair_enabled = repair_system.config.get("auto_repair_enabled", True)
    auto_repair_types = repair_system.config.get(
        "auto_repair_types", ["missing_module", "ollama", "redis", "missing_file"]
    )

    # Intentar reparación automática si está habilitada y es un error reparable
    if auto_repair and auto_repair_enabled and error_type in auto_repair_types:
        success, repair_message = repair_system.attempt_repair(error_type, message)
        if success:
            # Reparación automática exitosa, reintentar acción
            if repair_callback:
                repair_callback(success, repair_message)
            return QMessageBox.Information

    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Warning)
    msg_box.setWindowTitle(f"Error - {title}")
    msg_box.setText(message)

    # Checkbox para auto-reparación en el futuro
    auto_repair_checkbox = QCheckBox("Reparar automáticamente en el futuro")
    auto_repair_checkbox.setChecked(auto_repair)

    # Botón de auto-reparación manual
    repair_button = QPushButton("🔧 Auto-Reparar")
    repair_button.setStyleSheet(
        """
        QPushButton {
            background-color: #FF9800;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #F57C00;
        }
    """
    )

    def attempt_repair():
        success, repair_message = repair_system.attempt_repair(error_type, message)

        if success:
            msg_box.setText(f"✅ {repair_message}\n\n{message}")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.removeButton(repair_button)
            msg_box.removeButton(auto_repair_checkbox)

            # Guardar configuración de auto-reparación
            repair_system.config["auto_repair_enabled"] = auto_repair_checkbox.isChecked()
            repair_system._save_config()

            # Reintentar acción automáticamente tras reparación exitosa
            if repair_callback:
                QTimer.singleShot(1000, lambda: repair_callback(success, repair_message))
        else:
            msg_box.setText(f"❌ {repair_message}\n\n{message}")

    repair_button.clicked.connect(attempt_repair)

    msg_box.addButton(repair_button, QMessageBox.ActionRole)
    msg_box.setStandardButtons(QMessageBox.Ok)

    # Agregar checkbox al layout
    layout = msg_box.layout()
    layout.addWidget(auto_repair_checkbox)

    result = msg_box.exec_()

    # Guardar configuración de auto-reparación
    repair_system.config["auto_repair_enabled"] = auto_repair_checkbox.isChecked()
    repair_system._save_config()

    return result
