#!/usr/bin/env python3
"""
URA - Sistema de Logging Mejorado
Structured logging with JSON format and automatic rotation
"""

import json
import logging
import logging.handlers
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class URALogger:
    """URA Logger with structured logging and rotation"""

    def __init__(self, name: str, log_dir: str = "./logs", log_level: str = "INFO"):
        """
        Initialize URA Logger

        Args:
            name: Logger name
            log_dir: Directory for log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler (human-readable)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler (JSON format with rotation)
        log_file = self.log_dir / f"{name}.json.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",  # 10MB
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)

        # Error log file (separate)
        error_log_file = self.log_dir / f"{name}_error.json.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",  # 5MB
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(error_handler)

    def debug(self, message: str, **kwargs):
        """Log debug message with extra fields"""
        self.logger.debug(message, extra={"extra": kwargs})

    def info(self, message: str, **kwargs):
        """Log info message with extra fields"""
        self.logger.info(message, extra={"extra": kwargs})

    def warning(self, message: str, **kwargs):
        """Log warning message with extra fields"""
        self.logger.warning(message, extra={"extra": kwargs})

    def error(self, message: str, **kwargs):
        """Log error message with extra fields"""
        self.logger.error(message, extra={"extra": kwargs})

    def critical(self, message: str, **kwargs):
        """Log critical message with extra fields"""
        self.logger.critical(message, extra={"extra": kwargs})

    def log_ollama_request(self, model: str, prompt: str, duration: float, success: bool):
        """Log Ollama request"""
        self.info(
            "Ollama request",
            model=model,
            prompt_length=len(prompt),
            duration_seconds=duration,
            success=success,
        )

    def log_security_event(self, event_type: str, details: dict[str, Any]):
        """Log security event"""
        self.warning(f"Security event: {event_type}", event_type=event_type, details=details)

    def log_performance(self, operation: str, duration: float, metadata: dict[str, Any] = None):
        """Log performance metric"""
        metadata = metadata or {}
        self.debug(
            f"Performance: {operation}", operation=operation, duration_seconds=duration, **metadata
        )


# Global logger instances
loggers = {}


def get_logger(name: str, log_dir: str = "./logs", log_level: str = "INFO") -> URALogger:
    """Get or create a logger instance"""
    if name not in loggers:
        loggers[name] = URALogger(name, log_dir, log_level)
    return loggers[name]


if __name__ == "__main__":
    # Test logging
    logger = get_logger("ura_test")
    logger.info("Test message", user="test_user")
    logger.log_ollama_request("llama3.2:1b", "test prompt", 1.5, True)
    logger.log_security_event("command_blocked", {"command": "rm -rf /"})
    logger.log_performance("test_operation", 0.5, {"cache_hit": True})
