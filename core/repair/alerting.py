#!/usr/bin/env python3
"""
core/repair/alerting.py - Alerting functionality for auto-repair
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def send_slack_alert(instance, webhook_url: str, message: str, error_type: str = ""):
    """Enviar alerta a Slack"""
    try:
        import requests

        payload = {
            "text": "⚠️ URA Auto-Repair Alert",
            "attachments": [
                {
                    "color": "danger" if error_type else "warning",
                    "title": f"Error: {error_type}" if error_type else "Alerta de Sistema",
                    "text": message,
                    "footer": "URA Auto-Repair System",
                    "ts": datetime.now().timestamp(),
                }
            ],
        }

        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info("Alerta Slack enviada exitosamente")
        else:
            logger.warning(f"Error enviando alerta Slack: HTTP {response.status_code}")

    except Exception as e:
        logger.warning(f"Error enviando alerta Slack: {e}")


def send_teams_alert(instance, webhook_url: str, message: str, error_type: str = ""):
    """Enviar alerta a Microsoft Teams"""
    try:
        import requests

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": "URA Auto-Repair Alert",
            "themeColor": "FF0000" if error_type else "FFA500",
            "title": f"Error: {error_type}" if error_type else "Alerta de Sistema",
            "text": message,
            "sections": [
                {
                    "activityTitle": "URA Auto-Repair System",
                    "activitySubtitle": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            ],
        }

        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info("Alerta Teams enviada exitosamente")
        else:
            logger.warning(f"Error enviando alerta Teams: HTTP {response.status_code}")

    except Exception as e:
        logger.warning(f"Error enviando alerta Teams: {e}")
