#!/usr/bin/env python3
"""
core/repair/__init__.py - Reexport everything for compatibility
"""

# Import all functions from submodules for easy access
from .auto_repair import (
    _attempt_clear_cache,
    _attempt_model_fallback,
    _attempt_restart_service,
    _log_repair,
    _update_prometheus_metrics,
    attempt_repair,
    run_auto_repair_for_agents,
)
from .alerting import send_slack_alert, send_teams_alert
from .distributed import (
    broadcast_repair_request,
    setup_distributed_repair,
    sync_repair_history,
)
from .git_snapshots import create_git_snapshot
from .root_cause import (
    _get_fallback_root_cause,
    analyze_root_cause_with_llm,
    predict_errors,
    predict_errors_ml,
    predict_errors_rule_based,
)
from .scheduler import run_scheduled_repairs, schedule_repair

__all__ = [
    # auto_repair
    "attempt_repair",
    "run_auto_repair_for_agents",
    "_log_repair",
    "_update_prometheus_metrics",
    "_attempt_restart_service",
    "_attempt_clear_cache",
    "_attempt_model_fallback",
    # root_cause
    "analyze_root_cause_with_llm",
    "_get_fallback_root_cause",
    "predict_errors",
    "predict_errors_ml",
    "predict_errors_rule_based",
    # git_snapshots
    "create_git_snapshot",
    # alerting
    "send_slack_alert",
    "send_teams_alert",
    # scheduler
    "schedule_repair",
    "run_scheduled_repairs",
    # distributed
    "setup_distributed_repair",
    "broadcast_repair_request",
    "sync_repair_history",
]
