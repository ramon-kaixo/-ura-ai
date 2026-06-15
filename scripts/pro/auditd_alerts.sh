#!/bin/bash
# Wrapper para auditd_alerts.py (se puede llamar desde systemd)
cd "$(dirname "$0")/../.."
python3 scripts/pro/auditd_alerts.py "$@"
