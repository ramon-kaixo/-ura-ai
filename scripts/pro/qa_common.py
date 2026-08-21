#!/usr/bin/env python3
"""
Common QA functions for URA's deterministic QA pipeline.

This module contains shared utilities used across different stages of the
QA process. It ensures consistency and reduces code duplication in QA scripts.
"""

import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("/tmp/qa_common.log"), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

# Constant definitions
QA_DIR = Path("/home/ramon/URA/ura_ia_1972/docs/audit/qa")
LOGS_DIR = QA_DIR / "logs"
ENGINEERING_DIR = Path("/home/ramon/URA/ura_ia_1972/docs/engineering")

# Ensure directories exist
QA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ENGINEERING_DIR.mkdir(parents=True, exist_ok=True)


def get_qa_logs_dir() -> Path:
    """Return the QA logs directory path."""
    return LOGS_DIR


def get_engineering_dir() -> Path:
    """Return the engineering documentation directory path."""
    return ENGINEERING_DIR


def get_script_name() -> str:
    """Get the name of the current script."""
    return Path(sys.argv[0]).name


def run_shell_command(command: str, check: bool = True) -> str | None:
    """
    Execute a shell command and return its output.

    Args:
        command (str): The shell command to execute
        check (bool): Whether to raise an exception on non-zero exit code

    Returns:
        Optional[str]: The stdout of the command if successful, None otherwise
    """
    logger.info(f"Executing command: {command}")
    try:
        import subprocess

        result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)  # noqa: S602 - utilidad QA interna
        logger.info(f"Command output: {result.stdout}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}: {e.stderr}")
        return None


def get_repo_status() -> str:
    """Get current git repository status."""
    return run_shell_command("git status --short")


def get_latest_commits(n: int = 5) -> str:
    """Get latest n commits from git log."""
    return run_shell_command(f"git log --oneline -{n}")


def is_branch_clean() -> bool:
    """Check if current branch is clean (no uncommitted changes)."""
    status = get_repo_status()
    return status.strip() == ""


def get_current_branch() -> str:
    """Get the name of the current git branch."""
    return run_shell_command("git rev-parse --abbrev-ref HEAD").strip()


def get_snapshot_path(prefix: str) -> Path:
    """
    Get path for a snapshot file with given prefix.

    Args:
        prefix (str): Prefix for the snapshot filename

    Returns:
        Path: Path to the snapshot file
    """
    branch = get_current_branch()
    timestamp = run_shell_command("date +%Y%m%d_%H%M%S").strip()
    filename = f"{prefix}_{branch}_{timestamp}.json"
    return QA_DIR / filename


def backup_snapshot(snapshot_path: Path, data: dict) -> None:
    """
    Backup data to a snapshot file.

    Args:
        snapshot_path (Path): Path to the snapshot file
        data (dict): Data to backup
    """
    import json

    logger.info(f"Backing up snapshot to {snapshot_path}")
    with snapshot_path.open("w") as f:
        json.dump(data, f, indent=2)


def load_snapshot(snapshot_path: Path) -> dict | None:
    """
    Load data from a snapshot file.

    Args:
        snapshot_path (Path): Path to the snapshot file

    Returns:
        Optional[dict]: Loaded data or None if failed
    """
    import json

    logger.info(f"Loading snapshot from {snapshot_path}")
    if not snapshot_path.exists():
        logger.warning(f"Snapshot file {snapshot_path} does not exist")
        return None

    try:
        with snapshot_path.open() as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load snapshot: {e}")
        return None


def send_notification(message: str) -> None:
    """
    Send notification using core/notifier.

    Args:
        message (str): Message content to send
    """
    try:
        from core.notifier import send_message

        logger.info("Sending notification")
        send_message("QA Pipeline", message)
    except ImportError as e:
        logger.warning(f"Notification not sent due to import error: {e}")


def get_git_diff() -> str:
    """Get the git diff of current changes."""
    return run_shell_command("git diff")


def get_untracked_files() -> list[str]:
    """Get list of untracked files in the repository."""
    result = run_shell_command("git ls-files --others --exclude-standard")
    if result:
        return [line.strip() for line in result.split("\n") if line.strip()]
    return []


if __name__ == "__main__":
    # Example usage
    logger.info("qa_common.py executed directly")

    print(f"QA Dir: {QA_DIR}")
    print(f"Logs Dir: {LOGS_DIR}")
    print(f"Engineering Dir: {ENGINEERING_DIR}")
    print(f"Current Branch: {get_current_branch()}")
    print(f"Repo Status:\n{get_repo_status()}")
