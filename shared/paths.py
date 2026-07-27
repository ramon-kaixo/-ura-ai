"""Canonical path definitions for URA project.

Single source of truth for URA_ROOT and derived paths.
All modules should import from here instead of duplicating paths.
"""

from __future__ import annotations

import os
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))
SCRIPTS = URA_ROOT / "scripts"
SCRIPTS_PRO = URA_ROOT / "scripts/pro"
NERVIOSO = URA_ROOT / ".nervioso"
DEPLOY = URA_ROOT / "deploy"
TESTS = URA_ROOT / "tests"
LOGS = URA_ROOT / "logs"
CONFIG = URA_ROOT / "config"
DOCS = URA_ROOT / "docs"
